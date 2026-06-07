import os
import json
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.models import SystemSetting, FieldMapping, UploadRecord, ResidentMaster, DataError, Housing, ProblemReport
from app.schemas import ResponseModel, SettingItem
from app.config import settings as app_settings

router = APIRouter(prefix="/settings", tags=["Settings"])

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

@router.get("/list", response_model=ResponseModel)
async def get_settings(db: Session = Depends(get_db)):
    """Get all system settings"""
    settings_list = db.query(SystemSetting).all()
    
    result = {}
    for s in settings_list:
        result[s.key] = {
            "value": s.value,
            "description": s.description
        }
    
    # Ensure default settings exist
    defaults = {
        "community_name": {"value": "示例社区", "description": "社区名称"},
        "encryption_enabled": {"value": "true", "description": "是否启用数据加密"},
        "auto_masking": {"value": "true", "description": "是否自动脱敏显示"},
        "llm_api_url": {"value": "", "description": "LLM API地址"},
        "llm_api_key": {"value": "", "description": "LLM API密钥"},
        "llm_model": {"value": "", "description": "LLM模型名称"},
        "data_retention_days": {"value": "365", "description": "数据保留天数"},
    }
    
    for key, config in defaults.items():
        if key not in result:
            setting = SystemSetting(key=key, value=config["value"], description=config["description"])
            db.add(setting)
            result[key] = config
    
    db.commit()
    
    return ResponseModel(code=200, message="success", data=result)


@router.post("/save", response_model=ResponseModel)
async def save_setting(payload: dict, db: Session = Depends(get_db)):
    """Save a system setting"""
    key = payload.get("key")
    value = payload.get("value")
    description = payload.get("description", "")
    
    if not key:
        return ResponseModel(code=400, message="设置项Key不能为空", data=None)
    
    existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if existing:
        existing.value = value
        if description:
            existing.description = description
    else:
        setting = SystemSetting(key=key, value=value, description=description)
        db.add(setting)
    
    db.commit()
    
    return ResponseModel(code=200, message="设置已保存", data={"key": key})


@router.get("/mappings", response_model=ResponseModel)
async def get_field_mappings(
    community_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get field mappings for a community"""
    query = db.query(FieldMapping)
    
    if community_name:
        query = query.filter(FieldMapping.community_name == community_name)
    
    mappings = query.order_by(FieldMapping.community_name, FieldMapping.id).all()
    
    items = []
    for m in mappings:
        items.append({
            "id": m.id,
            "community_name": m.community_name,
            "original_header": m.original_header,
            "standard_field": m.standard_field,
            "confidence": m.confidence,
            "is_confirmed": m.is_confirmed,
            "is_active": m.is_active,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    
    # Get community list
    communities = db.query(FieldMapping.community_name).distinct().all()
    community_list = [c[0] for c in communities if c[0]]
    
    return ResponseModel(code=200, message="success", data={
        "mappings": items,
        "communities": community_list
    })


@router.post("/mappings/update", response_model=ResponseModel)
async def update_field_mapping(payload: dict, db: Session = Depends(get_db)):
    """Update a field mapping"""
    mapping_id = payload.get("id")
    standard_field = payload.get("standard_field")
    is_active = payload.get("is_active")
    
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        return ResponseModel(code=404, message="映射规则不存在", data=None)
    
    if standard_field is not None:
        mapping.standard_field = standard_field
        mapping.is_confirmed = True
    if is_active is not None:
        mapping.is_active = is_active
    
    db.commit()
    
    return ResponseModel(code=200, message="映射规则已更新", data={"id": mapping_id})


@router.delete("/mappings/delete/{mapping_id}", response_model=ResponseModel)
async def delete_field_mapping(mapping_id: int, db: Session = Depends(get_db)):
    """Delete a field mapping"""
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        return ResponseModel(code=404, message="映射规则不存在", data=None)
    
    db.delete(mapping)
    db.commit()
    
    return ResponseModel(code=200, message="映射规则已删除", data=None)


@router.post("/mappings/deactivate-community", response_model=ResponseModel)
async def deactivate_community_mappings(payload: dict, db: Session = Depends(get_db)):
    """Deactivate all mappings for a community"""
    community_name = payload.get("community_name")
    
    db.query(FieldMapping).filter(FieldMapping.community_name == community_name).update(
        {"is_active": False}
    )
    db.commit()
    
    return ResponseModel(code=200, message=f"社区[{community_name}]的映射规则已全部停用", data=None)


@router.get("/backup/list", response_model=ResponseModel)
async def list_backups():
    """List available backups"""
    backups = []
    
    if os.path.exists(BACKUP_DIR):
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.endswith(".db"):
                fpath = os.path.join(BACKUP_DIR, f)
                size = os.path.getsize(fpath)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                backups.append({
                    "filename": f,
                    "size_bytes": size,
                    "size_mb": round(size / 1024 / 1024, 2),
                    "created_at": mtime.isoformat()
                })
    
    return ResponseModel(code=200, message="success", data={"backups": backups})


@router.post("/backup/create", response_model=ResponseModel)
async def create_backup():
    """Create database backup"""
    try:
        db_path = app_settings.DATABASE_URL.replace("sqlite://", "")
        if not os.path.exists(db_path):
            return ResponseModel(code=404, message="数据库文件不存在", data=None)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        shutil.copy2(db_path, backup_path)
        
        size = os.path.getsize(backup_path)
        
        return ResponseModel(
            code=200,
            message="备份创建成功",
            data={
                "filename": backup_filename,
                "size_mb": round(size / 1024 / 1024, 2),
                "path": backup_path
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"备份失败: {str(e)}", data=None)


@router.post("/backup/restore", response_model=ResponseModel)
async def restore_backup(payload: dict):
    """Restore database from backup"""
    try:
        filename = payload.get("filename")
        backup_path = os.path.join(BACKUP_DIR, filename)
        
        if not os.path.exists(backup_path):
            return ResponseModel(code=404, message="备份文件不存在", data=None)
        
        db_path = app_settings.DATABASE_URL.replace("sqlite://", "")
        
        # Create safety backup of current
        safety_filename = f"safety_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        safety_path = os.path.join(BACKUP_DIR, safety_filename)
        if os.path.exists(db_path):
            shutil.copy2(db_path, safety_path)
        
        shutil.copy2(backup_path, db_path)
        
        return ResponseModel(
            code=200,
            message="数据库恢复成功，原数据已保存为安全备份",
            data={"safety_backup": safety_filename}
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"恢复失败: {str(e)}", data=None)


@router.get("/statistics/overview", response_model=ResponseModel)
async def get_system_statistics(db: Session = Depends(get_db)):
    """Get system overview statistics"""
    stats = {
        "resident_count": db.query(ResidentMaster).count(),
        "housing_count": db.query(Housing).count(),
        "upload_count": db.query(UploadRecord).count(),
        "problem_count": db.query(ProblemReport).count(),
        "mapping_count": db.query(FieldMapping).count(),
        "pending_problems": db.query(ProblemRecord).filter(ProblemReport.status == "pending").count() if hasattr(ProblemReport, 'status') else 0,
    }
    
    return ResponseModel(code=200, message="success", data=stats)
