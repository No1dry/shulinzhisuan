from typing import Optional, List
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProblemReport
from app.schemas import ResponseModel, ProblemCreate, ProblemUpdate, ProblemOut

router = APIRouter(prefix="/problems", tags=["Problems"])

@router.get("/list", response_model=ResponseModel)
async def list_problems(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    status: Optional[str] = None,
    problem_type: Optional[str] = None,
    priority: Optional[str] = None,
    grid_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List problem reports"""
    query = db.query(ProblemReport)
    
    if status:
        query = query.filter(ProblemReport.status == status)
    if problem_type:
        query = query.filter(ProblemReport.problem_type == problem_type)
    if priority:
        query = query.filter(ProblemReport.priority == priority)
    if grid_name:
        query = query.filter(ProblemReport.grid_name == grid_name)
    
    total = query.count()
    problems = query.order_by(ProblemReport.created_at.desc()).offset(skip).limit(limit).all()
    
    items = []
    for p in problems:
        items.append({
            "id": p.id,
            "title": p.title,
            "problem_type": p.problem_type,
            "description": p.description,
            "location": p.location,
            "grid_name": p.grid_name,
            "reporter_name": p.reporter_name,
            "reporter_phone": p.reporter_phone,
            "images": p.images or [],
            "status": p.status,
            "priority": p.priority,
            "assigned_to": p.assigned_to,
            "resolution": p.resolution,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        })
    
    return ResponseModel(code=200, message="success", data={"total": total, "items": items})


@router.post("/create", response_model=ResponseModel)
async def create_problem(payload: dict, db: Session = Depends(get_db)):
    """Create problem report"""
    try:
        problem = ProblemReport(
            title=payload.get("title", ""),
            problem_type=payload.get("problem_type", "其他"),
            description=payload.get("description", ""),
            location=payload.get("location"),
            grid_name=payload.get("grid_name"),
            reporter_name=payload.get("reporter_name"),
            reporter_phone=payload.get("reporter_phone"),
            images=payload.get("images", []),
            priority=payload.get("priority", "normal"),
            status="pending"
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)
        
        return ResponseModel(code=200, message="问题上报成功", data={"id": problem.id})
    
    except Exception as e:
        return ResponseModel(code=500, message=f"上报失败: {str(e)}", data=None)


@router.put("/update/{problem_id}", response_model=ResponseModel)
async def update_problem(problem_id: int, payload: dict, db: Session = Depends(get_db)):
    """Update problem report status/resolution"""
    problem = db.query(ProblemReport).filter(ProblemReport.id == problem_id).first()
    if not problem:
        return ResponseModel(code=404, message="问题不存在", data=None)
    
    for field in ["status", "resolution", "assigned_to", "priority"]:
        if field in payload:
            setattr(problem, field, payload[field])
    
    db.commit()
    db.refresh(problem)
    
    return ResponseModel(code=200, message="更新成功", data={"id": problem.id})


@router.delete("/delete/{problem_id}", response_model=ResponseModel)
async def delete_problem(problem_id: int, db: Session = Depends(get_db)):
    """Delete problem report"""
    problem = db.query(ProblemReport).filter(ProblemReport.id == problem_id).first()
    if not problem:
        return ResponseModel(code=404, message="问题不存在", data=None)
    
    db.delete(problem)
    db.commit()
    
    return ResponseModel(code=200, message="问题已删除", data=None)


@router.get("/statistics", response_model=ResponseModel)
async def get_problem_statistics(db: Session = Depends(get_db)):
    """Get problem statistics"""
    total = db.query(ProblemReport).count()
    pending = db.query(ProblemReport).filter(ProblemReport.status == "pending").count()
    processing = db.query(ProblemReport).filter(ProblemReport.status == "processing").count()
    resolved = db.query(ProblemReport).filter(ProblemReport.status == "resolved").count()
    
    # By type
    types = db.query(ProblemReport.problem_type).distinct().all()
    type_stats = []
    for t in types:
        if t[0]:
            count = db.query(ProblemReport).filter(ProblemReport.problem_type == t[0]).count()
            type_stats.append({"type": t[0], "count": count})
    
    return ResponseModel(code=200, message="success", data={
        "total": total,
        "pending": pending,
        "processing": processing,
        "resolved": resolved,
        "by_type": type_stats
    })


@router.get("/types", response_model=ResponseModel)
async def get_problem_types():
    """Get problem type options"""
    types = [
        {"value": "安全隐患", "label": "安全隐患"},
        {"value": "居民纠纷", "label": "居民纠纷"},
        {"value": "设施损坏", "label": "设施损坏"},
        {"value": "环境卫生", "label": "环境卫生"},
        {"value": "违建违规", "label": "违建违规"},
        {"value": "噪音扰民", "label": "噪音扰民"},
        {"value": "其他", "label": "其他"},
    ]
    return ResponseModel(code=200, message="success", data=types)
