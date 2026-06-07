import time
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.models import ResidentMaster
from app.schemas import ResponseModel, NLQRequest, NLQResponse
from app.services.header_recognizer import LLMNLQEngine
from app.encryption import decrypt_field

router = APIRouter(prefix="/query", tags=["Natural Language Query"])

@router.post("/nlq", response_model=ResponseModel)
async def natural_language_query(payload: dict, db: Session = Depends(get_db)):
    """Natural language query - converts question to structured query"""
    try:
        question = payload.get("question", "").strip()
        grid_name = payload.get("grid_name", None)
        
        if not question:
            return ResponseModel(code=400, message="请输入查询内容", data=None)
        
        start_time = time.time()
        
        # Parse natural language
        parse_result = LLMNLQEngine.parse_natural_language(question, grid_name)
        conditions = parse_result["conditions"]
        
        # Build database query
        db_query = db.query(ResidentMaster)
        
        # Apply conditions
        if "age__gte" in conditions:
            db_query = db_query.filter(ResidentMaster.age >= conditions["age__gte"])
        if "age__lte" in conditions:
            db_query = db_query.filter(ResidentMaster.age <= conditions["age__lte"])
        if "is_living_alone" in conditions:
            db_query = db_query.filter(ResidentMaster.is_living_alone == conditions["is_living_alone"])
        if "is_disabled" in conditions:
            db_query = db_query.filter(ResidentMaster.is_disabled == conditions["is_disabled"])
        if "is_low_income" in conditions:
            db_query = db_query.filter(ResidentMaster.is_low_income == conditions["is_low_income"])
        if "is_left_behind_child" in conditions:
            db_query = db_query.filter(ResidentMaster.is_left_behind_child == conditions["is_left_behind_child"])
        if "is_key_population" in conditions:
            db_query = db_query.filter(ResidentMaster.is_key_population == conditions["is_key_population"])
        if "is_special_support" in conditions:
            db_query = db_query.filter(ResidentMaster.is_special_support == conditions["is_special_support"])
        if "gender" in conditions:
            db_query = db_query.filter(ResidentMaster.gender == conditions["gender"])
        if "grid_name" in conditions:
            db_query = db_query.filter(ResidentMaster.grid_name == conditions["grid_name"])
        
        residents = db_query.limit(1000).all()
        execution_time = int((time.time() - start_time) * 1000)
        
        # Format results with masked data
        results = []
        for r in residents:
            name = decrypt_field(r.name_encrypted) if r.name_encrypted else ""
            results.append({
                "id": r.id,
                "name": name,
                "name_masked": r.name_masked,
                "gender": r.gender,
                "age": r.age,
                "id_card_masked": r.id_card_masked,
                "phone_masked": r.phone_masked,
                "grid_name": r.grid_name,
                "residence_address": r.residence_address,
                "building_unit": r.building_unit,
                "is_key_population": r.is_key_population,
                "key_population_type": r.key_population_type,
                "is_living_alone": r.is_living_alone,
                "is_disabled": r.is_disabled,
                "is_low_income": r.is_low_income,
                "marital_status": r.marital_status,
                "employment_status": r.employment_status,
            })
        
        return ResponseModel(
            code=200,
            message=f"查询完成，共找到 {len(results)} 条记录",
            data={
                "question": question,
                "detected_type": parse_result["detected_type"],
                "conditions": conditions,
                "generated_sql": parse_result["mock_sql"],
                "explanation": parse_result["explanation"],
                "results": results,
                "total_count": len(results),
                "execution_time_ms": execution_time
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"查询失败: {str(e)}", data=None)


@router.get("/advanced", response_model=ResponseModel)
async def advanced_query(
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    gender: Optional[str] = None,
    grid_name: Optional[str] = None,
    is_key_population: Optional[bool] = None,
    is_living_alone: Optional[bool] = None,
    is_disabled: Optional[bool] = None,
    is_low_income: Optional[bool] = None,
    is_left_behind_child: Optional[bool] = None,
    is_special_support: Optional[bool] = None,
    marital_status: Optional[str] = None,
    employment_status: Optional[str] = None,
    medical_insurance: Optional[str] = None,
    building_unit: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Advanced query with multiple filter conditions"""
    try:
        db_query = db.query(ResidentMaster)
        
        filters = []
        if age_min is not None:
            filters.append(ResidentMaster.age >= age_min)
        if age_max is not None:
            filters.append(ResidentMaster.age <= age_max)
        if gender:
            filters.append(ResidentMaster.gender == gender)
        if grid_name:
            filters.append(ResidentMaster.grid_name == grid_name)
        if is_key_population is not None:
            filters.append(ResidentMaster.is_key_population == is_key_population)
        if is_living_alone is not None:
            filters.append(ResidentMaster.is_living_alone == is_living_alone)
        if is_disabled is not None:
            filters.append(ResidentMaster.is_disabled == is_disabled)
        if is_low_income is not None:
            filters.append(ResidentMaster.is_low_income == is_low_income)
        if is_left_behind_child is not None:
            filters.append(ResidentMaster.is_left_behind_child == is_left_behind_child)
        if is_special_support is not None:
            filters.append(ResidentMaster.is_special_support == is_special_support)
        if marital_status:
            filters.append(ResidentMaster.marital_status == marital_status)
        if employment_status:
            filters.append(ResidentMaster.employment_status.contains(employment_status))
        if medical_insurance:
            filters.append(ResidentMaster.medical_insurance.contains(medical_insurance))
        if building_unit:
            filters.append(ResidentMaster.building_unit.contains(building_unit))
        
        if filters:
            db_query = db_query.filter(and_(*filters))
        
        residents = db_query.limit(1000).all()
        
        results = []
        for r in residents:
            name = decrypt_field(r.name_encrypted) if r.name_encrypted else ""
            results.append({
                "id": r.id,
                "name": name,
                "name_masked": r.name_masked,
                "gender": r.gender,
                "age": r.age,
                "id_card_masked": r.id_card_masked,
                "phone_masked": r.phone_masked,
                "grid_name": r.grid_name,
                "residence_address": r.residence_address,
                "building_unit": r.building_unit,
                "is_key_population": r.is_key_population,
                "is_living_alone": r.is_living_alone,
                "is_disabled": r.is_disabled,
                "is_low_income": r.is_low_income,
            })
        
        return ResponseModel(
            code=200,
            message=f"查询完成，共 {len(results)} 条记录",
            data={"total": len(results), "items": results}
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"查询失败: {str(e)}", data=None)
