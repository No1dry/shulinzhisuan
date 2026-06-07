import re
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Housing, ResidentMaster
from app.schemas import ResponseModel, HousingCreate, HousingOut
from app.encryption import decrypt_field

router = APIRouter(prefix="/housing", tags=["Housing"])


def _extract_sort_key(address: str) -> tuple:
    """Extract numeric parts from address for natural sorting.
    e.g. '2-1-103' -> (2, 1, 103), '10号楼2单元301' -> (10, 2, 301)
    """
    if not address:
        return (999999,)
    # Extract all numbers from the address
    numbers = [int(n) for n in re.findall(r'\d+', str(address))]
    if numbers:
        return tuple(numbers)
    # Fallback: alphabetical sorting for addresses without numbers
    return (999999, str(address))

@router.get("/list", response_model=ResponseModel)
async def list_housing(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    grid_name: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List housing records sorted by address numbers naturally."""
    query = db.query(Housing)
    
    if grid_name:
        query = query.filter(Housing.grid_name == grid_name)
    if keyword:
        query = query.filter(
            Housing.address.contains(keyword) | 
            Housing.building_name.contains(keyword)
        )
    
    total = query.count()
    # Fetch all matching houses (for in-memory natural sort)
    houses = query.all()
    
    # Sort by address numeric parts: 2-1-103 comes before 10-1-101
    houses.sort(key=lambda h: _extract_sort_key(h.address))
    
    # Apply pagination after sorting
    paginated = houses[skip:skip + limit]
    
    items = []
    for h in paginated:
        # Get associated residents with full details
        residents = db.query(ResidentMaster).filter(ResidentMaster.housing_id == h.id).all()
        resident_list = []
        for r in residents:
            # Build full resident info
            resident_info = {
                "id": r.id,
                "name_decrypted": decrypt_field(r.name_encrypted) if r.name_encrypted else None,
                "name_masked": r.name_masked,
                "gender": r.gender,
                "age": r.age,
                "birth_date": r.birth_date,
                "id_card_decrypted": decrypt_field(r.id_card_encrypted) if r.id_card_encrypted else None,
                "id_card_masked": r.id_card_masked,
                "phone_decrypted": decrypt_field(r.phone_encrypted) if r.phone_encrypted else None,
                "phone_masked": r.phone_masked,
                "ethnicity": r.ethnicity,
                "is_key_population": r.is_key_population,
                "key_population_type": r.key_population_type,
                "is_living_alone": r.is_living_alone,
                "is_disabled": r.is_disabled,
                "disability_type": r.disability_type,
                "is_low_income": r.is_low_income,
                "is_left_behind_child": r.is_left_behind_child,
                "is_special_support": r.is_special_support,
                "employment_status": r.employment_status,
                "medical_insurance": r.medical_insurance,
                "grid_name": r.grid_name,
                "building_unit": r.building_unit,
                "residence_address": r.residence_address,
            }
            resident_list.append(resident_info)
        
        items.append({
            "id": h.id,
            "address": h.address,
            "building_name": h.building_name,
            "unit_number": h.unit_number,
            "room_number": h.room_number,
            "grid_name": h.grid_name,
            "housing_type": h.housing_type,
            "area_sqm": h.area_sqm,
            "owner_name": h.owner_name,
            "owner_phone": h.owner_phone,
            "resident_count": len(residents),
            "residents": resident_list,
            "created_at": h.created_at.isoformat() if h.created_at else None
        })
    
    return ResponseModel(code=200, message="success", data={"total": total, "items": items})


@router.post("/create", response_model=ResponseModel)
async def create_housing(payload: dict, db: Session = Depends(get_db)):
    """Create housing record"""
    try:
        house = Housing(
            address=payload.get("address", ""),
            building_name=payload.get("building_name"),
            unit_number=payload.get("unit_number"),
            room_number=payload.get("room_number"),
            grid_name=payload.get("grid_name"),
            housing_type=payload.get("housing_type", "住宅"),
            area_sqm=payload.get("area_sqm"),
            owner_name=payload.get("owner_name"),
            owner_phone=payload.get("owner_phone"),
        )
        db.add(house)
        db.commit()
        db.refresh(house)
        
        return ResponseModel(code=200, message="房屋信息创建成功", data={"id": house.id})
    
    except Exception as e:
        return ResponseModel(code=500, message=f"创建失败: {str(e)}", data=None)


@router.put("/update/{house_id}", response_model=ResponseModel)
async def update_housing(house_id: int, payload: dict, db: Session = Depends(get_db)):
    """Update housing record"""
    house = db.query(Housing).filter(Housing.id == house_id).first()
    if not house:
        return ResponseModel(code=404, message="房屋不存在", data=None)
    
    for field in ["address", "building_name", "unit_number", "room_number", 
                   "grid_name", "housing_type", "area_sqm", "owner_name", "owner_phone"]:
        if field in payload:
            setattr(house, field, payload[field])
    
    db.commit()
    db.refresh(house)
    
    return ResponseModel(code=200, message="房屋信息更新成功", data={"id": house.id})


@router.delete("/delete/{house_id}", response_model=ResponseModel)
async def delete_housing(house_id: int, db: Session = Depends(get_db)):
    """Delete housing record"""
    house = db.query(Housing).filter(Housing.id == house_id).first()
    if not house:
        return ResponseModel(code=404, message="房屋不存在", data=None)
    
    # Unlink residents
    db.query(ResidentMaster).filter(ResidentMaster.housing_id == house_id).update({"housing_id": None})
    
    db.delete(house)
    db.commit()
    
    return ResponseModel(code=200, message="房屋已删除", data=None)


@router.post("/link-resident", response_model=ResponseModel)
async def link_resident_to_housing(payload: dict, db: Session = Depends(get_db)):
    """Link a resident to a housing"""
    resident_id = payload.get("resident_id")
    housing_id = payload.get("housing_id")
    
    resident = db.query(ResidentMaster).filter(ResidentMaster.id == resident_id).first()
    if not resident:
        return ResponseModel(code=404, message="居民不存在", data=None)
    
    house = db.query(Housing).filter(Housing.id == housing_id).first()
    if not house:
        return ResponseModel(code=404, message="房屋不存在", data=None)
    
    resident.housing_id = housing_id
    db.commit()
    
    # Update resident count
    count = db.query(ResidentMaster).filter(ResidentMaster.housing_id == housing_id).count()
    house.resident_count = count
    db.commit()
    
    return ResponseModel(code=200, message="关联成功", data=None)


@router.post("/sync-from-address", response_model=ResponseModel)
async def sync_housing_from_address(payload: dict, db: Session = Depends(get_db)):
    """Auto-sync housing from resident addresses"""
    try:
        grid_name = payload.get("grid_name")
        
        query = db.query(ResidentMaster)
        if grid_name:
            query = query.filter(ResidentMaster.grid_name == grid_name)
        
        residents = query.all()
        
        created_count = 0
        linked_count = 0
        
        for resident in residents:
            address = resident.residence_address
            if not address:
                continue
            
            # Find or create housing by address
            house = db.query(Housing).filter(Housing.address == address).first()
            
            if not house:
                house = Housing(
                    address=address,
                    building_name=resident.building_unit,
                    grid_name=resident.grid_name,
                    resident_count=0
                )
                db.add(house)
                db.commit()
                db.refresh(house)
                created_count += 1
            
            # Link resident if not already linked
            if resident.housing_id != house.id:
                resident.housing_id = house.id
                linked_count += 1
        
        db.commit()
        
        # Update all resident counts
        houses = db.query(Housing).all()
        for house in houses:
            count = db.query(ResidentMaster).filter(ResidentMaster.housing_id == house.id).count()
            house.resident_count = count
        
        db.commit()
        
        return ResponseModel(
            code=200,
            message=f"同步完成：新建房屋{created_count}条，关联居民{linked_count}条",
            data={
                "created_houses": created_count,
                "linked_residents": linked_count,
                "total_houses": db.query(Housing).count()
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"同步失败: {str(e)}", data=None)


@router.get("/grids", response_model=ResponseModel)
async def get_housing_grids(db: Session = Depends(get_db)):
    """Get grid names with housing"""
    grids = db.query(Housing.grid_name).distinct().filter(Housing.grid_name.isnot(None)).all()
    return ResponseModel(code=200, message="success", data=[g[0] for g in grids if g[0]])
