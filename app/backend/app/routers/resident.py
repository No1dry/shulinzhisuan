"""
Resident Portal API - 居民端接口
"""
from sqlalchemy import desc
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ResidentMaster, Housing, ProblemReport
from app.schemas import ResponseModel
from app.encryption import encrypt_field, decrypt_field

router = APIRouter(prefix="/resident", tags=["Resident"])


# ── 公告 ──────────────────────────────────────────

@router.get("/notices", response_model=ResponseModel)
async def list_notices(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """获取通知公告列表"""
    from app.models import Notice
    total = db.query(Notice).filter(Notice.is_active == True).count()
    items = db.query(Notice).filter(Notice.is_active == True).order_by(
        desc(Notice.is_top), desc(Notice.created_at)
    ).offset(skip).limit(limit).all()
    return ResponseModel(code=200, message="success", data={
        "total": total,
        "items": [{"id": n.id, "title": n.title, "content": n.content,
                    "category": n.category, "is_top": n.is_top,
                    "created_at": n.created_at.isoformat() if n.created_at else None}
                   for n in items]
    })


@router.get("/notices/{notice_id}", response_model=ResponseModel)
async def get_notice(notice_id: int, db: Session = Depends(get_db)):
    from app.models import Notice
    n = db.query(Notice).filter(Notice.id == notice_id).first()
    if not n:
        return ResponseModel(code=404, message="公告不存在", data=None)
    return ResponseModel(code=200, message="success", data={
        "id": n.id, "title": n.title, "content": n.content,
        "category": n.category, "created_at": n.created_at.isoformat() if n.created_at else None
    })


# ── 新闻 ──────────────────────────────────────────

@router.get("/news", response_model=ResponseModel)
async def list_news(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    from app.models import NewsItem
    total = db.query(NewsItem).filter(NewsItem.is_active == True).count()
    items = db.query(NewsItem).filter(NewsItem.is_active == True).order_by(
        desc(NewsItem.created_at)
    ).offset(skip).limit(limit).all()
    return ResponseModel(code=200, message="success", data={
        "total": total,
        "items": [{"id": n.id, "title": n.title, "summary": n.summary,
                    "source": n.source, "cover_image": n.cover_image,
                    "created_at": n.created_at.isoformat() if n.created_at else None}
                   for n in items]
    })


@router.get("/news/{news_id}", response_model=ResponseModel)
async def get_news(news_id: int, db: Session = Depends(get_db)):
    from app.models import NewsItem
    n = db.query(NewsItem).filter(NewsItem.id == news_id).first()
    if not n:
        return ResponseModel(code=404, message="新闻不存在", data=None)
    return ResponseModel(code=200, message="success", data={
        "id": n.id, "title": n.title, "content": n.content,
        "summary": n.summary, "source": n.source,
        "created_at": n.created_at.isoformat() if n.created_at else None
    })


# ── 政策 ──────────────────────────────────────────

@router.get("/policies", response_model=ResponseModel)
async def list_policies(skip: int = 0, limit: int = 10, category: str = None, db: Session = Depends(get_db)):
    from app.models import Policy
    query = db.query(Policy).filter(Policy.is_active == True)
    if category:
        query = query.filter(Policy.category == category)
    total = query.count()
    items = query.order_by(desc(Policy.created_at)).offset(skip).limit(limit).all()
    return ResponseModel(code=200, message="success", data={
        "total": total,
        "items": [{"id": p.id, "title": p.title, "summary": p.summary,
                    "category": p.category,
                    "created_at": p.created_at.isoformat() if p.created_at else None}
                   for p in items]
    })


@router.get("/policies/{policy_id}", response_model=ResponseModel)
async def get_policy(policy_id: int, db: Session = Depends(get_db)):
    from app.models import Policy
    p = db.query(Policy).filter(Policy.id == policy_id).first()
    if not p:
        return ResponseModel(code=404, message="政策不存在", data=None)
    return ResponseModel(code=200, message="success", data={
        "id": p.id, "title": p.title, "content": p.content,
        "summary": p.summary, "category": p.category,
        "created_at": p.created_at.isoformat() if p.created_at else None
    })


# ── 信息上报 ──────────────────────────────────────

@router.post("/report-issue", response_model=ResponseModel)
async def report_issue(payload: dict, db: Session = Depends(get_db)):
    """居民问题上报 - 写入网格员端的 problem_reports 表"""
    try:
        data = payload
        if not data.get("title") or not data.get("description"):
            return ResponseModel(code=400, message="标题和描述不能为空", data=None)

        issue = ProblemReport(
            title=data["title"],
            description=data["description"],
            problem_type=data.get("category", "其他"),
            location=data.get("location", ""),
            grid_name=data.get("grid_name", ""),
            reporter_name=data.get("reporter_name", ""),
            reporter_phone=data.get("reporter_phone", ""),
            status="pending",
            images=data.get("images") or [],
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)

        return ResponseModel(
            code=200,
            message="上报成功，网格员会尽快处理",
            data={"id": issue.id, "title": issue.title, "status": issue.status}
        )
    except Exception as e:
        return ResponseModel(code=500, message=f"上报失败: {str(e)}", data=None)


@router.get("/my-reports", response_model=ResponseModel)
async def my_reports(
    phone: str = None,
    name: str = None,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db)
):
    """查询我的上报记录"""
    query = db.query(ProblemReport)
    if phone:
        query = query.filter(ProblemReport.reporter_phone == phone)
    elif name:
        query = query.filter(ProblemReport.reporter_name == name)
    else:
        return ResponseModel(code=400, message="请提供手机号或姓名查询", data=None)

    total = query.count()
    items = query.order_by(desc(ProblemReport.created_at)).offset(skip).limit(limit).all()

    return ResponseModel(code=200, message="success", data={
        "total": total,
        "items": [{"id": r.id, "title": r.title, "description": r.description,
                    "problem_type": r.problem_type, "status": r.status,
                    "status_label": {"pending": "待处理", "processing": "处理中", "resolved": "已解决",
                                     "rejected": "已驳回", "closed": "已关闭"}.get(r.status, r.status),
                    "location": r.location, "reply": r.resolution,
                    "reporter_name": r.reporter_name,
                    "replies": r.replies or [],
                    "created_at": r.created_at.isoformat() if r.created_at else None}
                   for r in items]
    })


# ── 诉求也走 problem_reports 表 ──────────────────

@router.post("/submit-appeal", response_model=ResponseModel)
async def submit_appeal(payload: dict, db: Session = Depends(get_db)):
    """居民提交诉求 - 也用 problem_reports 表存储"""
    try:
        data = payload
        if not data.get("title") or not data.get("content"):
            return ResponseModel(code=400, message="标题和内容不能为空", data=None)

        issue = ProblemReport(
            title=data["title"],
            description=data["content"],
            problem_type=data.get("category", "居民诉求"),
            location=data.get("location", ""),
            grid_name=data.get("grid_name", ""),
            reporter_name=data.get("submitter_name", ""),
            reporter_phone=data.get("submitter_phone", ""),
            status="pending",
            images=data.get("images") or [],
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)

        return ResponseModel(
            code=200,
            message="诉求提交成功",
            data={"id": issue.id, "title": issue.title, "status": issue.status}
        )
    except Exception as e:
        return ResponseModel(code=500, message=f"提交失败: {str(e)}", data=None)


@router.get("/my-appeals", response_model=ResponseModel)
async def my_appeals(
    phone: str = None,
    name: str = None,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db)
):
    """查询我的诉求记录"""
    query = db.query(ProblemReport).filter(ProblemReport.problem_type == "居民诉求")
    if phone:
        query = query.filter(ProblemReport.reporter_phone == phone)
    elif name:
        query = query.filter(ProblemReport.reporter_name == name)
    else:
        return ResponseModel(code=400, message="请提供手机号或姓名查询", data=None)

    total = query.count()
    items = query.order_by(desc(ProblemReport.created_at)).offset(skip).limit(limit).all()

    return ResponseModel(code=200, message="success", data={
        "total": total,
        "items": [{"id": a.id, "title": a.title, "content": a.description,
                    "status": a.status,
                    "status_label": {"pending": "待处理", "processing": "处理中", "resolved": "已解决",
                                     "rejected": "已驳回", "closed": "已关闭"}.get(a.status, a.status),
                    "reply": a.resolution,
                    "created_at": a.created_at.isoformat() if a.created_at else None}
                   for a in items]
    })


# ── 居民登录 ─────────────────────────────────────

@router.post("/login", response_model=ResponseModel)
async def resident_login(payload: dict, db: Session = Depends(get_db)):
    """居民登录：手机号 + 身份证后六位"""
    try:
        phone = payload.get("phone", "").strip()
        password = payload.get("password", "").strip()  # 身份证后六位
        if not phone or not password:
            return ResponseModel(code=400, message="请输入手机号和密码", data=None)
        
        # Find resident by phone
        from app.encryption import encrypt_field
        encrypted_phone = encrypt_field(phone)
        r = db.query(ResidentMaster).filter(ResidentMaster.phone_encrypted == encrypted_phone).first()
        if not r:
            return ResponseModel(code=404, message="未找到该手机号对应的居民信息，请联系网格员录入", data=None)
        
        # Verify password (id card last 6 digits)
        if r.id_card_encrypted:
            id_card = decrypt_field(r.id_card_encrypted)
            if len(id_card) >= 6 and password == id_card[-6:]:
                # Decrypt name for resident view (their own info)
                name = decrypt_field(r.name_encrypted) if r.name_encrypted else (r.name_masked or '未知')
                return ResponseModel(code=200, message="登录成功", data={
                    "token": f"resident_{r.id}",
                    "resident": {
                        "id": r.id, "name": name,
                        "phone": phone, "phone_masked": r.phone_masked,
                        "gender": r.gender, "age": r.age,
                        "residence_address": r.residence_address,
                        "grid_name": r.grid_name,
                        "id_card_last6": password,
                    }
                })
        
        return ResponseModel(code=401, message="密码错误（请输入身份证后六位）", data=None)
    except Exception as e:
        return ResponseModel(code=500, message=f"登录失败: {str(e)}", data=None)


# ── 居民信息 ──────────────────────────────────────

@router.get("/profile", response_model=ResponseModel)
async def get_profile(phone: str = None, db: Session = Depends(get_db)):
    """根据手机号查询居民信息"""
    if not phone:
        return ResponseModel(code=400, message="请提供手机号", data=None)
    encrypted_phone = encrypt_field(phone)
    r = db.query(ResidentMaster).filter(ResidentMaster.phone_encrypted == encrypted_phone).first()
    if not r:
        return ResponseModel(code=404, message="未找到该手机号对应的居民信息", data=None)
    # Decrypt name for resident view (their own info)
    name = decrypt_field(r.name_encrypted) if r.name_encrypted else (r.name_masked or '未知')
    return ResponseModel(code=200, message="success", data={
        "id": r.id,
        "name": name,
        "gender": r.gender,
        "age": r.age,
        "grid_name": r.grid_name,
        "residence_address": r.residence_address,
        "is_key_population": r.is_key_population,
        "is_disabled": r.is_disabled,
        "is_low_income": r.is_low_income,
    })
