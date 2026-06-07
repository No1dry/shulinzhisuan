"""
Appeals Router - 处理居民诉求
包含信息上报查看、回复、大模型生成方案、发起协商等功能
"""
import json
import httpx
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ResponseModel
from app.models import ProblemReport, ResidentMaster
from app.config import settings
from app.websocket import manager as ws_manager

router = APIRouter(prefix="/appeals", tags=["Appeals"])


STATUS_LABELS = {
    "pending": "待处理", "processing": "处理中",
    "resolved": "已解决", "closed": "已关闭", "negotiating": "协商中"
}


def _build_report_dict(r: ProblemReport) -> dict:
    """Convert ProblemReport to dict for API response."""
    return {
        "id": r.id, "title": r.title, "problem_type": r.problem_type,
        "description": r.description, "location": r.location,
        "grid_name": r.grid_name, "reporter_name": r.reporter_name,
        "reporter_phone": r.reporter_phone,
        "status": r.status, "status_label": STATUS_LABELS.get(r.status, r.status),
        "priority": r.priority, "resolution": r.resolution,
        "replies": r.replies or [],
        "is_negotiation": r.is_negotiation,
        "topic": r.topic, "participants": r.participants or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ── 信息上报列表 ──────────────────────────────────

@router.get("/reports", response_model=ResponseModel)
async def list_reports(
    status: Optional[str] = None,
    problem_type: Optional[str] = None,
    grid_name: Optional[str] = None,
    is_negotiation: bool = False,
    db: Session = Depends(get_db)
):
    """List reports from residents (not from worker self-reporting)."""
    try:
        query = db.query(ProblemReport).filter(ProblemReport.is_negotiation == is_negotiation)
        if status:
            query = query.filter(ProblemReport.status == status)
        if problem_type:
            query = query.filter(ProblemReport.problem_type == problem_type)
        if grid_name:
            query = query.filter(ProblemReport.grid_name == grid_name)
        
        items = query.order_by(ProblemReport.created_at.desc()).limit(200).all()
        return ResponseModel(code=200, message="success", data={
            "total": len(items),
            "items": [_build_report_dict(r) for r in items]
        })
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


@router.get("/reports/{rid}", response_model=ResponseModel)
async def get_report(rid: int, db: Session = Depends(get_db)):
    """Get a single report detail."""
    r = db.query(ProblemReport).filter(ProblemReport.id == rid).first()
    if not r:
        return ResponseModel(code=404, message="记录不存在", data=None)
    return ResponseModel(code=200, message="success", data=_build_report_dict(r))


# ── 回复 / 处理 ──────────────────────────────────

@router.post("/reports/{rid}/reply", response_model=ResponseModel)
async def reply_report(rid: int, payload: dict, db: Session = Depends(get_db)):
    """Add a reply to a report. Updates status to processing if pending."""
    try:
        r = db.query(ProblemReport).filter(ProblemReport.id == rid).first()
        if not r:
            return ResponseModel(code=404, message="记录不存在", data=None)
        
        content = payload.get("content", "").strip()
        if not content:
            return ResponseModel(code=400, message="回复内容不能为空", data=None)
        
        author = payload.get("author", "网格员")
        role = payload.get("role", "worker")  # worker / resident / ai
        
        replies = list(r.replies or [])
        from datetime import datetime
        replies.append({
            "role": role, "content": content, "author": author,
            "time": datetime.now().isoformat()
        })
        r.replies = replies
        # Explicitly mark JSON field as modified for SQLite
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(r, "replies")
        
        if r.status == "pending":
            r.status = "processing"
        
        db.commit()

        # Build response data
        result_data = _build_report_dict(r)

        # Notify all connected clients about the new reply
        try:
            await ws_manager.notify_report_update(rid, result_data)
        except Exception:
            pass  # WebSocket failure should not block the API response

        return ResponseModel(code=200, message="回复成功", data=result_data)
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


@router.put("/reports/{rid}/status", response_model=ResponseModel)
async def update_status(rid: int, payload: dict, db: Session = Depends(get_db)):
    """Update report status and resolution."""
    try:
        r = db.query(ProblemReport).filter(ProblemReport.id == rid).first()
        if not r:
            return ResponseModel(code=404, message="记录不存在", data=None)
        
        if "status" in payload:
            r.status = payload["status"]
        if "resolution" in payload:
            r.resolution = payload["resolution"]
        
        db.commit()
        return ResponseModel(code=200, message="更新成功", data=_build_report_dict(r))
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


# ── 大模型生成处理方案 ────────────────────────────

@router.post("/reports/{rid}/generate-plan", response_model=ResponseModel)
async def generate_plan(rid: int, db: Session = Depends(get_db)):
    """Use LLM to generate a handling plan for a report."""
    r = db.query(ProblemReport).filter(ProblemReport.id == rid).first()
    if not r:
        return ResponseModel(code=404, message="记录不存在", data=None)
    
    api_url = settings.LLM_API_URL
    api_key = settings.LLM_API_KEY
    model = settings.LLM_MODEL
    
    if not api_url or not api_key:
        return ResponseModel(code=500, message="大模型未配置", data=None)
    
    try:
        prompt = (
            f"你是社区治理专家。请根据以下居民诉求，生成一份专业的处理方案。\n\n"
            f"【诉求标题】{r.title}\n"
            f"【诉求类型】{r.problem_type}\n"
            f"【诉求描述】{r.description}\n"
            f"【位置】{r.location or '未提供'}\n"
            f"【上报人】{r.reporter_name or '匿名'}\n\n"
            f"请生成包含以下内容的处理方案：\n"
            f"1. 问题分析\n"
            f"2. 处理步骤（具体可执行）\n"
            f"3. 责任分工\n"
            f"4. 预计完成时间\n"
            f"5. 注意事项\n"
            f"用中文回答，格式清晰。"
        )
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(api_url, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }, json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2048})
            
            if res.status_code != 200:
                return ResponseModel(code=500, message=f"大模型请求失败: {res.status_code}", data=None)
            
            result = res.json()
            plan = result["choices"][0]["message"]["content"] if "choices" in result else "生成失败"
        
        # Save plan as a reply
        from datetime import datetime
        replies = r.replies or []
        replies.append({"role": "ai", "content": plan, "author": "AI助手", "time": datetime.now().isoformat()})
        r.replies = replies
        if r.status == "pending":
            r.status = "processing"
        db.commit()
        
        return ResponseModel(code=200, message="方案生成成功", data={"plan": plan, "report": _build_report_dict(r)})
    except Exception as e:
        return ResponseModel(code=500, message=f"生成失败: {str(e)}", data=None)


# ── 协商功能 ─────────────────────────────────────

@router.post("/negotiation", response_model=ResponseModel)
async def create_negotiation(payload: dict, db: Session = Depends(get_db)):
    """Create a negotiation."""
    try:
        data = payload
        
        # Validate
        if not data.get("topic"):
            return ResponseModel(code=400, message="协商议题不能为空", data=None)
        if not data.get("description"):
            return ResponseModel(code=400, message="协商描述不能为空", data=None)
        
        # Build participants list with status
        participants = data.get("participants", [])
        for p in participants:
            p["status"] = "pending"  # pending / accepted / rejected
            if "role" not in p:
                p["role"] = "参与者"
        
        r = ProblemReport(
            title=data["topic"],  # Use topic as title
            problem_type="协商事项",
            description=data["description"],
            location=data.get("location", ""),
            grid_name=data.get("grid_name", ""),
            reporter_name=data.get("reporter_name", ""),
            reporter_phone=data.get("reporter_phone", ""),
            status="negotiating",
            is_negotiation=True,
            topic=data["topic"],
            participants=participants,
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return ResponseModel(code=200, message="协商发起成功", data=_build_report_dict(r))
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


@router.put("/negotiation/{nid}/participant-status", response_model=ResponseModel)
async def update_participant_status(nid: int, payload: dict, db: Session = Depends(get_db)):
    """Update participant status (accept/reject negotiation)."""
    try:
        r = db.query(ProblemReport).filter(ProblemReport.id == nid).first()
        if not r:
            return ResponseModel(code=404, message="协商不存在", data=None)
        
        phone = payload.get("phone")
        name = payload.get("name")
        new_status = payload.get("status")  # accepted / rejected
        
        if not phone and not name:
            return ResponseModel(code=400, message="请提供姓名或手机号", data=None)
        if new_status not in ("accepted", "rejected"):
            return ResponseModel(code=400, message="状态只能是 accepted 或 rejected", data=None)
        
        participants = list(r.participants or [])
        found = False
        for p in participants:
            match = False
            if phone and p.get("phone") == phone:
                match = True
            elif name and p.get("name") == name:
                match = True
            if match:
                p["status"] = new_status
                found = True
                break
        
        if not found:
            return ResponseModel(code=404, message="未找到该参与人", data=None)
        
        r.participants = participants
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(r, "participants")
        db.commit()
        
        result = _build_report_dict(r)
        # Notify via WebSocket
        try:
            await ws_manager.notify_report_update(nid, result)
        except Exception:
            pass
        
        return ResponseModel(code=200, message="状态更新成功", data=result)
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


@router.get("/negotiations", response_model=ResponseModel)
async def list_negotiations(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all negotiations."""
    try:
        query = db.query(ProblemReport).filter(ProblemReport.is_negotiation == True)
        if status:
            query = query.filter(ProblemReport.status == status)
        items = query.order_by(ProblemReport.created_at.desc()).limit(100).all()
        return ResponseModel(code=200, message="success", data={
            "total": len(items),
            "items": [_build_report_dict(r) for r in items]
        })
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


@router.get("/residents-for-selection", response_model=ResponseModel)
async def get_residents_for_selection(
    building: Optional[str] = None,
    unit: Optional[str] = None,
    grid_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get residents for participant selection (by building/unit)."""
    try:
        query = db.query(ResidentMaster).filter(ResidentMaster.name_masked.isnot(None))
        
        if grid_name:
            query = query.filter(ResidentMaster.grid_name == grid_name)
        if building:
            query = query.filter(ResidentMaster.building_unit.like(f"%{building}%"))
        if unit:
            query = query.filter(ResidentMaster.building_unit.like(f"%{unit}%"))
        
        residents = query.limit(200).all()
        
        result = []
        for r in residents:
            result.append({
                "id": r.id,
                "name": r.name_masked or "",
                "phone": r.phone_masked or "",
                "address": r.residence_address or "",
                "building_unit": r.building_unit or "",
                "grid_name": r.grid_name or "",
                "gender": r.gender or "",
                "age": r.age,
            })
        
        return ResponseModel(code=200, message="success", data={"items": result, "total": len(result)})
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


@router.get("/buildings", response_model=ResponseModel)
async def get_buildings(grid_name: Optional[str] = None, db: Session = Depends(get_db)):
    """Get unique building list from residents."""
    try:
        query = db.query(ResidentMaster.building_unit).filter(ResidentMaster.building_unit.isnot(None))
        if grid_name:
            query = query.filter(ResidentMaster.grid_name == grid_name)
        
        units = query.distinct().limit(200).all()
        buildings = set()
        for u in units:
            bu = u[0] or ""
            # Extract building number (e.g., "1号楼-1单元" -> "1号楼")
            parts = bu.split("-")
            if parts:
                buildings.add(parts[0].strip())
        
        return ResponseModel(code=200, message="success", data={"buildings": sorted(buildings)})
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


# ── AI Chat ──────────────────────────────────────

@router.post("/ai-chat", response_model=ResponseModel)
async def ai_chat(payload: dict):
    """General AI chat for negotiation (can be @mentioned)."""
    question = payload.get("question", "").strip()
    if not question:
        return ResponseModel(code=400, message="请输入问题", data=None)
    
    api_url = settings.LLM_API_URL
    api_key = settings.LLM_API_KEY
    model = settings.LLM_MODEL
    
    if not api_url or not api_key:
        return ResponseModel(code=500, message="大模型未配置", data=None)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(api_url, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }, json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是社区治理协商助手。帮助各方理解问题、提供政策依据、建议解决方案。回答简洁、公正、专业。"},
                    {"role": "user", "content": question},
                ],
                "temperature": 0.7, "max_tokens": 2048,
            })
            if res.status_code != 200:
                return ResponseModel(code=500, message="请求失败", data=None)
            result = res.json()
            answer = result["choices"][0]["message"]["content"] if "choices" in result else "失败"
            return ResponseModel(code=200, message="success", data={"answer": answer})
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)


# ── 统计 ─────────────────────────────────────────

@router.get("/statistics", response_model=ResponseModel)
async def get_statistics(db: Session = Depends(get_db)):
    """Get appeal statistics."""
    try:
        total = db.query(ProblemReport).filter(ProblemReport.is_negotiation == False).count()
        pending = db.query(ProblemReport).filter(
            ProblemReport.is_negotiation == False, ProblemReport.status == "pending"
        ).count()
        processing = db.query(ProblemReport).filter(
            ProblemReport.is_negotiation == False, ProblemReport.status == "processing"
        ).count()
        neg_total = db.query(ProblemReport).filter(ProblemReport.is_negotiation == True).count()
        neg_active = db.query(ProblemReport).filter(
            ProblemReport.is_negotiation == True, ProblemReport.status == "negotiating"
        ).count()
        return ResponseModel(code=200, message="success", data={
            "reports": {"total": total, "pending": pending, "processing": processing},
            "negotiations": {"total": neg_total, "active": neg_active},
        })
    except Exception as e:
        return ResponseModel(code=500, message=str(e), data=None)
