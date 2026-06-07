from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.database import get_db
from app.models import ResidentMaster, Housing
from app.schemas import ResponseModel, ResidentOut, ResidentMasked, ResidentListResponse
from app.encryption import decrypt_field, mask_phone, mask_id_card, mask_name

router = APIRouter(prefix="/residents", tags=["Residents"])

@router.get("/list", response_model=ResponseModel)
async def list_residents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    grid_name: Optional[str] = None,
    keyword: Optional[str] = None,
    gender: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    is_key_population: Optional[bool] = None,
    is_living_alone: Optional[bool] = None,
    is_disabled: Optional[bool] = None,
    is_low_income: Optional[bool] = None,
    is_left_behind_child: Optional[bool] = None,
    building_unit: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List residents with filters, return masked data"""
    query = db.query(ResidentMaster)
    
    # Apply filters
    if grid_name:
        query = query.filter(ResidentMaster.grid_name == grid_name)
    if gender:
        query = query.filter(ResidentMaster.gender == gender)
    if age_min is not None:
        query = query.filter(ResidentMaster.age >= age_min)
    if age_max is not None:
        query = query.filter(ResidentMaster.age <= age_max)
    if is_key_population is not None:
        query = query.filter(ResidentMaster.is_key_population == is_key_population)
    if is_living_alone is not None:
        query = query.filter(ResidentMaster.is_living_alone == is_living_alone)
    if is_disabled is not None:
        query = query.filter(ResidentMaster.is_disabled == is_disabled)
    if is_low_income is not None:
        query = query.filter(ResidentMaster.is_low_income == is_low_income)
    if is_left_behind_child is not None:
        query = query.filter(ResidentMaster.is_left_behind_child == is_left_behind_child)
    if building_unit:
        query = query.filter(ResidentMaster.building_unit.contains(building_unit))
    
    # Keyword search (on masked fields)
    if keyword:
        query = query.filter(
            or_(
                ResidentMaster.name_masked.contains(keyword),
                ResidentMaster.phone_masked.contains(keyword),
                ResidentMaster.id_card_masked.contains(keyword),
                ResidentMaster.residence_address.contains(keyword),
                ResidentMaster.grid_name.contains(keyword)
            )
        )
    
    total = query.count()
    residents = query.order_by(ResidentMaster.id.desc()).offset(skip).limit(limit).all()
    
    items = []
    for r in residents:
        items.append({
            "id": r.id,
            "name_masked": r.name_masked,
            "gender": r.gender,
            "id_card_masked": r.id_card_masked,
            "phone_masked": r.phone_masked,
            "age": r.age,
            "grid_name": r.grid_name,
            "residence_address": r.residence_address,
            "building_unit": r.building_unit,
            "is_key_population": r.is_key_population,
            "is_living_alone": r.is_living_alone,
            "is_disabled": r.is_disabled,
            "is_low_income": r.is_low_income,
            "custom_fields": r.custom_fields or {},
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    return ResponseModel(code=200, message="success", data={"total": total, "items": items})


@router.get("/detail/{resident_id}", response_model=ResponseModel)
async def get_resident_detail(resident_id: int, db: Session = Depends(get_db)):
    """Get resident detail - with decrypted sensitive data for authorized users"""
    resident = db.query(ResidentMaster).filter(ResidentMaster.id == resident_id).first()
    if not resident:
        return ResponseModel(code=404, message="居民不存在", data=None)
    
    # Decrypt sensitive fields
    data = {
        "id": resident.id,
        "name": resident.name_masked,  # Still masked for safety
        "name_decrypted": decrypt_field(resident.name_encrypted) if resident.name_encrypted else None,
        "gender": resident.gender,
        "id_card": resident.id_card_masked,
        "id_card_decrypted": decrypt_field(resident.id_card_encrypted) if resident.id_card_encrypted else None,
        "phone": resident.phone_masked,
        "phone_decrypted": decrypt_field(resident.phone_encrypted) if resident.phone_encrypted else None,
        "birth_date": resident.birth_date,
        "age": resident.age,
        "ethnicity": resident.ethnicity,
        "marital_status": resident.marital_status,
        "employment_status": resident.employment_status,
        "medical_insurance": resident.medical_insurance,
        "residence_address": resident.residence_address,
        "household_address": resident.household_address,
        "grid_name": resident.grid_name,
        "building_unit": resident.building_unit,
        "household_number": resident.household_number,
        "is_low_income": resident.is_low_income,
        "is_disabled": resident.is_disabled,
        "disability_type": resident.disability_type,
        "is_living_alone": resident.is_living_alone,
        "is_left_behind_child": resident.is_left_behind_child,
        "is_key_population": resident.is_key_population,
        "key_population_type": resident.key_population_type,
        "is_special_support": resident.is_special_support,
        "custom_fields": resident.custom_fields or {},
        "created_at": resident.created_at.isoformat() if resident.created_at else None,
        "updated_at": resident.updated_at.isoformat() if resident.updated_at else None
    }
    
    return ResponseModel(code=200, message="success", data=data)


@router.put("/update/{resident_id}", response_model=ResponseModel)
async def update_resident(resident_id: int, payload: dict, db: Session = Depends(get_db)):
    """Update resident info"""
    resident = db.query(ResidentMaster).filter(ResidentMaster.id == resident_id).first()
    if not resident:
        return ResponseModel(code=404, message="居民不存在", data=None)
    
    data = payload
    
    # Update fields
    if "name" in data and data["name"]:
        resident.name_encrypted = decrypt_field.__module__  # Will encrypt
        from app.encryption import encrypt_field
        resident.name_encrypted = encrypt_field(data["name"])
        resident.name_masked = mask_name(data["name"])
    
    if "id_card" in data and data["id_card"]:
        from app.encryption import encrypt_field
        resident.id_card_encrypted = encrypt_field(data["id_card"])
        resident.id_card_masked = mask_id_card(data["id_card"])
    
    if "phone" in data and data["phone"]:
        from app.encryption import encrypt_field
        resident.phone_encrypted = encrypt_field(data["phone"])
        resident.phone_masked = mask_phone(data["phone"])
    
    for field in ["gender", "birth_date", "age", "ethnicity", "marital_status",
                  "employment_status", "medical_insurance", "residence_address",
                  "household_address", "grid_name", "building_unit", "household_number",
                  "disability_type", "key_population_type", "housing_id"]:
        if field in data:
            setattr(resident, field, data[field])
    
    for field in ["is_low_income", "is_disabled", "is_living_alone",
                  "is_left_behind_child", "is_key_population", "is_special_support"]:
        if field in data:
            setattr(resident, field, bool(data[field]))
    
    if "custom_fields" in data:
        resident.custom_fields = data["custom_fields"]
    
    db.commit()
    db.refresh(resident)
    
    return ResponseModel(code=200, message="居民信息更新成功", data={"id": resident.id})


@router.delete("/delete/{resident_id}", response_model=ResponseModel)
async def delete_resident(resident_id: int, db: Session = Depends(get_db)):
    """Delete resident"""
    resident = db.query(ResidentMaster).filter(ResidentMaster.id == resident_id).first()
    if not resident:
        return ResponseModel(code=404, message="居民不存在", data=None)
    
    db.delete(resident)
    db.commit()
    
    return ResponseModel(code=200, message="居民已删除", data=None)


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_residents(payload: dict, db: Session = Depends(get_db)):
    """Batch delete residents by IDs"""
    ids = payload.get("ids", [])
    if not ids:
        return ResponseModel(code=400, message="未选择要删除的居民", data=None)
    
    deleted = 0
    for rid in ids:
        resident = db.query(ResidentMaster).filter(ResidentMaster.id == rid).first()
        if resident:
            db.delete(resident)
            deleted += 1
    
    db.commit()
    return ResponseModel(code=200, message=f"已删除 {deleted} 位居民", data={"deleted_count": deleted})


@router.get("/grids", response_model=ResponseModel)
async def get_grid_list(db: Session = Depends(get_db)):
    """Get all grid names"""
    grids = db.query(ResidentMaster.grid_name).distinct().filter(
        ResidentMaster.grid_name.isnot(None)
    ).all()
    
    return ResponseModel(code=200, message="success", data=[g[0] for g in grids if g[0]])


@router.get("/statistics", response_model=ResponseModel)
async def get_statistics(db: Session = Depends(get_db)):
    """Get resident statistics"""
    total = db.query(ResidentMaster).count()
    key_pop = db.query(ResidentMaster).filter(ResidentMaster.is_key_population == True).count()
    elderly_alone = db.query(ResidentMaster).filter(
        ResidentMaster.is_living_alone == True,
        ResidentMaster.age >= 60
    ).count()
    disabled = db.query(ResidentMaster).filter(ResidentMaster.is_disabled == True).count()
    low_income = db.query(ResidentMaster).filter(ResidentMaster.is_low_income == True).count()
    left_behind = db.query(ResidentMaster).filter(ResidentMaster.is_left_behind_child == True).count()
    elderly_60 = db.query(ResidentMaster).filter(ResidentMaster.age >= 60).count()
    elderly_80 = db.query(ResidentMaster).filter(ResidentMaster.age >= 80).count()
    grids = db.query(ResidentMaster.grid_name).distinct().filter(
        ResidentMaster.grid_name.isnot(None)
    ).count()
    
    # Grid breakdown
    grid_stats = []
    grid_names = db.query(ResidentMaster.grid_name).distinct().filter(
        ResidentMaster.grid_name.isnot(None)
    ).all()
    
    for g in grid_names:
        if not g[0]:
            continue
        count = db.query(ResidentMaster).filter(ResidentMaster.grid_name == g[0]).count()
        key_count = db.query(ResidentMaster).filter(
            ResidentMaster.grid_name == g[0],
            ResidentMaster.is_key_population == True
        ).count()
        elderly_count = db.query(ResidentMaster).filter(
            ResidentMaster.grid_name == g[0],
            ResidentMaster.age >= 60
        ).count()
        grid_stats.append({
            "grid_name": g[0],
            "resident_count": count,
            "key_population_count": key_count,
            "elderly_count": elderly_count
        })
    
    return ResponseModel(code=200, message="success", data={
        "total_residents": total,
        "total_grids": grids,
        "key_populations": key_pop,
        "elderly_alone": elderly_alone,
        "disabled_persons": disabled,
        "low_income": low_income,
        "left_behind_children": left_behind,
        "elderly_60_plus": elderly_60,
        "elderly_80_plus": elderly_80,
        "grid_breakdown": sorted(grid_stats, key=lambda x: x["resident_count"], reverse=True)
    })
