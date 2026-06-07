import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import UploadRecord, ResidentMaster, FieldMapping, Housing
from app.services.file_parser import parse_all_sheets, extract_community_from_filename, SheetData
from app.services.header_recognizer import LLMHeaderRecognizer
from app.services.data_validator import DataValidator
from app.services.id_parser import infer_from_id_card
from app.encryption import encrypt_field, decrypt_field, mask_phone, mask_id_card, mask_name
from app.schemas import ResponseModel

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


class SaveAndImportRequest(BaseModel):
    upload_id: int
    community_name: str
    mappings: list
    rows: list


def _recognize_single_sheet(
    sheet: SheetData,
    community_name: str,
    db: Session
) -> dict:
    """Recognize headers for a single sheet."""
    existing_mappings = db.query(FieldMapping).filter(
        FieldMapping.community_name == community_name,
        FieldMapping.is_active == True
    ).all()
    existing_map = {m.original_header: m.standard_field for m in existing_mappings}
    
    llm_results = LLMHeaderRecognizer.recognize_headers(
        sheet.headers, sheet.rows[:3] if sheet.rows else []
    )
    
    final_mappings = []
    for r in llm_results:
        orig = r["original_header"]
        std = r["standard_field"]
        conf = r["confidence"]
        
        if orig in existing_map:
            final_mappings.append({
                "original_header": orig,
                "standard_field": existing_map[orig],
                "confidence": 1.0,
                "is_confirmed": True
            })
        else:
            final_mappings.append({
                "original_header": orig,
                "standard_field": std,
                "confidence": conf,
                "is_confirmed": False
            })
    
    explanation = LLMHeaderRecognizer.generate_mapping_explanation(final_mappings)
    
    return {
        "sheet_name": sheet.name,
        "title": sheet.title,
        "header_row_index": 1 if sheet.title else 0,
        "mappings": final_mappings,
        "explanation": explanation,
        "total_headers": len(sheet.headers),
        "matched_count": sum(1 for m in final_mappings if m["standard_field"]),
        "unmapped_headers": [m["original_header"] for m in final_mappings if not m["standard_field"]],
        "row_count": sheet.row_count,
        "all_rows": sheet.rows,
    }


@router.post("/file", response_model=ResponseModel)
async def upload_file(
    file: UploadFile = File(...),
    community_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload Excel/CSV with multi-sheet support."""
    try:
        filename = file.filename or "unknown"
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        
        if ext not in ["xlsx", "xls", "csv"]:
            return ResponseModel(
                code=400, 
                message=f"不支持的文件格式: {ext}，请上传 .xlsx、.xls 或 .csv 文件", 
                data=None
            )
        
        # Auto-extract community from filename
        if not community_name:
            extracted = extract_community_from_filename(filename)
            community_name = extracted or "默认社区"
        
        # Save file
        unique_name = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Parse ALL sheets
        try:
            sheets = parse_all_sheets(file_path, ext)
        except ValueError as ve:
            error_msg = str(ve)
            if "zip" in error_msg.lower() or "xls" in error_msg.lower():
                return ResponseModel(code=400, message=error_msg, data=None)
            return ResponseModel(code=400, message=f"文件解析失败: {error_msg}", data=None)
        except ImportError as ie:
            return ResponseModel(code=500, message=f"缺少依赖: {str(ie)}", data=None)
        
        if not sheets:
            return ResponseModel(code=400, message="文件中没有有效数据", data=None)
        
        # Recognize headers for each sheet
        recognized_sheets = []
        total_rows = 0
        
        for sheet in sheets:
            recognized = _recognize_single_sheet(sheet, community_name, db)
            total_rows += recognized["row_count"]
            recognized_sheets.append(recognized)
        
        # Create upload record
        upload_record = UploadRecord(
            filename=filename,
            file_type=ext,
            community_name=community_name,
            total_rows=total_rows,
            status="pending"
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        
        return ResponseModel(
            code=200,
            message="文件上传成功",
            data={
                "upload_id": upload_record.id,
                "filename": filename,
                "file_type": ext,
                "community_name": community_name,
                "auto_extracted_community": extract_community_from_filename(filename) is not None,
                "sheet_count": len(sheets),
                "total_rows": total_rows,
                "sheets": [
                    {
                        "sheet_name": s["sheet_name"],
                        "title": s["title"],
                        "header_row_index": s["header_row_index"],
                        "row_count": s["row_count"],
                        "matched_count": s["matched_count"],
                        "total_headers": s["total_headers"],
                        "mappings": s["mappings"],
                        "explanation": s["explanation"],
                        "all_rows": s["all_rows"],
                    }
                    for s in recognized_sheets
                ],
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"文件上传失败: {str(e)}", data=None)


@router.post("/validate", response_model=ResponseModel)
async def validate_data(payload: dict, db: Session = Depends(get_db)):
    """Validate uploaded data for a specific sheet."""
    try:
        rows = payload.get("rows", [])
        mappings = payload.get("mappings", [])
        
        standard_map = {m["original_header"]: m["standard_field"] 
                       for m in mappings if m.get("standard_field")}
        
        validation_result = DataValidator.validate_batch(rows, standard_map)
        duplicates = DataValidator.check_duplicates(rows, standard_map)
        
        return ResponseModel(
            code=200,
            message="数据校验完成",
            data={
                "is_valid": validation_result["is_valid"] and len(duplicates) == 0,
                "validation_errors": validation_result["errors"],
                "duplicates": duplicates,
                "summary": {
                    "total_rows": len(rows),
                    "error_count": len(validation_result["errors"]),
                    "duplicate_count": len(duplicates),
                    "error_rows": validation_result["summary"]["error_rows"]
                }
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"数据校验失败: {str(e)}", data=None)


@router.post("/save-and-import", response_model=ResponseModel)
async def save_and_import(payload: SaveAndImportRequest, db: Session = Depends(get_db)):
    """Save mappings and import all data in one step with dedup, ID inference, auto housing."""
    try:
        data = payload.dict()
        upload_id = data["upload_id"]
        community_name = data.get("community_name", "默认社区")
        mappings = data["mappings"]
        rows = data["rows"]
        
        standard_map = {}
        header_to_standard = {}
        for m in mappings:
            if m.get("standard_field"):
                standard_map[m["original_header"]] = m["standard_field"]
                header_to_standard[m["standard_field"]] = m["original_header"]
        
        # Save/Update field mappings
        for m in mappings:
            if not m.get("standard_field"):
                continue
            existing = db.query(FieldMapping).filter(
                FieldMapping.community_name == community_name,
                FieldMapping.original_header == m["original_header"]
            ).first()
            
            if existing:
                existing.standard_field = m["standard_field"]
                existing.is_confirmed = True
                existing.confidence = m.get("confidence", 1.0)
            else:
                new_mapping = FieldMapping(
                    community_name=community_name,
                    original_header=m["original_header"],
                    standard_field=m["standard_field"],
                    confidence=m.get("confidence", 1.0),
                    is_confirmed=True,
                    is_active=True
                )
                db.add(new_mapping)
        db.commit()
        
        # Update upload record
        upload_record = db.query(UploadRecord).filter(UploadRecord.id == upload_id).first()
        if upload_record:
            upload_record.status = "processing"
            db.commit()
        
        success_count = 0
        error_count = 0
        duplicate_count = 0
        housing_linked_count = 0
        
        # Build existing dedup key set: (name + id_card) for duplicate detection
        existing_dedup_keys = set()
        for r in db.query(ResidentMaster).all():
            name_part = r.name_masked or ""
            id_part = ""
            if r.id_card_encrypted:
                try:
                    id_part = decrypt_field(r.id_card_encrypted)
                except:
                    pass
            if name_part or id_part:
                existing_dedup_keys.add((name_part, id_part))
        
        imported_dedup_keys = set()
        
        # Cache for housing auto-creation: address -> housing_id
        housing_cache = {}
        # Track current address for merged-cell inheritance (same household)
        current_address = ""
        current_household_number = ""
        
        for row in rows:
            try:
                def get_val(standard_field):
                    orig_header = header_to_standard.get(standard_field)
                    return row.get(orig_header, "") if orig_header else ""
                
                name = str(get_val("name") or "").strip()
                id_card = str(get_val("id_card") or "").strip()
                phone = str(get_val("phone") or "").strip()
                
                if not name and not id_card:
                    continue
                
                # Deduplication: check by (name + id_card)
                dedup_key = (name, id_card)
                if id_card and dedup_key in existing_dedup_keys:
                    duplicate_count += 1
                    continue
                if id_card and dedup_key in imported_dedup_keys:
                    duplicate_count += 1
                    continue
                if id_card:
                    imported_dedup_keys.add(dedup_key)
                
                def parse_bool(val):
                    if not val:
                        return False
                    return str(val).strip().lower() in ["是", "yes", "true", "1", "y", "有"]
                
                # Start with basic data
                resident_data = {
                    "name": name,
                    "id_card": id_card,
                    "phone": phone,
                    "gender": str(get_val("gender") or "").strip(),
                    "birth_date": str(get_val("birth_date") or "").strip(),
                    "age": None,
                    "ethnicity": str(get_val("ethnicity") or "").strip(),
                    "marital_status": str(get_val("marital_status") or "").strip(),
                    "employment_status": str(get_val("employment_status") or "").strip(),
                    "medical_insurance": str(get_val("medical_insurance") or "").strip(),
                    "residence_address": str(get_val("residence_address") or "").strip(),
                    "household_address": str(get_val("household_address") or "").strip(),
                    "grid_name": str(get_val("grid_name") or "").strip(),
                    "building_unit": str(get_val("building_unit") or "").strip(),
                    "household_number": str(get_val("household_number") or "").strip(),
                    "is_low_income": parse_bool(get_val("is_low_income")),
                    "is_disabled": parse_bool(get_val("is_disabled")),
                    "disability_type": str(get_val("disability_type") or "").strip(),
                    "is_living_alone": parse_bool(get_val("is_living_alone")),
                    "is_left_behind_child": parse_bool(get_val("is_left_behind_child")),
                    "is_key_population": parse_bool(get_val("is_key_population")),
                    "key_population_type": str(get_val("key_population_type") or "").strip(),
                    "is_special_support": parse_bool(get_val("is_special_support")),
                }
                
                # Parse age from data if available
                age_val = get_val("age")
                if age_val:
                    try:
                        resident_data["age"] = int(float(str(age_val)))
                    except:
                        pass
                
                # Infer gender, birth_date, age from ID card
                if id_card:
                    inferred = infer_from_id_card(id_card, {
                        "gender": resident_data["gender"],
                        "birth_date": resident_data["birth_date"],
                        "age": resident_data["age"]
                    })
                    resident_data["gender"] = inferred.get("gender", resident_data["gender"])
                    resident_data["birth_date"] = inferred.get("birth_date", resident_data["birth_date"])
                    resident_data["age"] = inferred.get("age", resident_data["age"])
                
                # Collect custom fields (non-mapped columns)
                custom_fields = {}
                for key, val in row.items():
                    if key and key not in header_to_standard and val is not None and str(val).strip():
                        custom_fields[key] = str(val)
                
                # Address inheritance for merged cells (same household)
                raw_address = resident_data["residence_address"]
                raw_household_num = resident_data["household_number"]
                
                if raw_address:
                    # New address encountered, update current tracker
                    current_address = raw_address
                    if raw_household_num:
                        current_household_number = raw_household_num
                elif current_address:
                    # Empty address + we have a current address = same household (merged cell)
                    # Inherit the address from previous row
                    resident_data["residence_address"] = current_address
                    if not raw_household_num and current_household_number:
                        resident_data["household_number"] = current_household_number
                
                # Use sheet_name or community as grid_name if available
                grid_name = resident_data["grid_name"]
                if not grid_name and row.get("__sheet_name__"):
                    grid_name = row["__sheet_name__"]
                if not grid_name:
                    grid_name = community_name
                
                # Create resident
                resident = ResidentMaster(
                    name_encrypted=encrypt_field(name) if name else None,
                    id_card_encrypted=encrypt_field(id_card) if id_card else None,
                    phone_encrypted=encrypt_field(phone) if phone else None,
                    name_masked=mask_name(name) if name else None,
                    id_card_masked=mask_id_card(id_card) if id_card else None,
                    phone_masked=mask_phone(phone) if phone else None,
                    gender=resident_data["gender"],
                    birth_date=resident_data["birth_date"],
                    age=resident_data["age"],
                    ethnicity=resident_data["ethnicity"],
                    marital_status=resident_data["marital_status"],
                    employment_status=resident_data["employment_status"],
                    medical_insurance=resident_data["medical_insurance"],
                    residence_address=resident_data["residence_address"],
                    household_address=resident_data["household_address"],
                    grid_name=grid_name,
                    building_unit=resident_data["building_unit"],
                    household_number=resident_data["household_number"],
                    is_low_income=resident_data["is_low_income"],
                    is_disabled=resident_data["is_disabled"],
                    disability_type=resident_data["disability_type"],
                    is_living_alone=resident_data["is_living_alone"],
                    is_left_behind_child=resident_data["is_left_behind_child"],
                    is_key_population=resident_data["is_key_population"],
                    key_population_type=resident_data["key_population_type"],
                    is_special_support=resident_data["is_special_support"],
                    source_upload_id=upload_id,
                    custom_fields=custom_fields if custom_fields else {}
                )
                
                db.add(resident)
                db.flush()  # Get resident.id before commit
                success_count += 1
                
                # Auto housing association from residence_address
                address = resident_data["residence_address"]
                if address:
                    housing_id = housing_cache.get(address)
                    if housing_id is None:
                        house = db.query(Housing).filter(Housing.address == address).first()
                        if not house:
                            # Parse building/unit/room from address and building_unit
                            building_name = resident_data["building_unit"] or ""
                            house = Housing(
                                address=address,
                                building_name=building_name,
                                grid_name=grid_name,
                                resident_count=0
                            )
                            db.add(house)
                            db.flush()
                            db.refresh(house)
                        housing_cache[address] = house.id
                        housing_id = house.id
                    
                    # Link resident to housing
                    resident.housing_id = housing_id
                    housing_linked_count += 1
                
            except Exception:
                error_count += 1
                continue
        
        # Update housing resident counts
        for address, hid in housing_cache.items():
            count = db.query(ResidentMaster).filter(ResidentMaster.housing_id == hid).count()
            house = db.query(Housing).filter(Housing.id == hid).first()
            if house:
                house.resident_count = count
        
        db.commit()
        
        if upload_record:
            upload_record.status = "completed"
            upload_record.success_count = success_count
            upload_record.error_count = error_count
            upload_record.duplicate_count = duplicate_count
            total_standard = len([m for m in mappings if m.get("standard_field")])
            upload_record.field_coverage_rate = round(total_standard / len(mappings) * 100, 1) if mappings else 0
            db.commit()
        
        return ResponseModel(
            code=200,
            message=f"导入完成：成功{success_count}条，重复{duplicate_count}条，错误{error_count}条，房屋关联{housing_linked_count}条",
            data={
                "upload_id": upload_id,
                "success_count": success_count,
                "error_count": error_count,
                "duplicate_count": duplicate_count,
                "housing_linked_count": housing_linked_count,
                "total_rows": len(rows),
                "field_coverage_rate": upload_record.field_coverage_rate if upload_record else 0
            }
        )
    
    except Exception as e:
        import traceback
        return ResponseModel(code=500, message=f"导入失败: {str(e)}\n{traceback.format_exc()}", data=None)


@router.get("/status/{upload_id}", response_model=ResponseModel)
async def get_upload_status(upload_id: int, db: Session = Depends(get_db)):
    """Get upload processing status"""
    upload = db.query(UploadRecord).filter(UploadRecord.id == upload_id).first()
    if not upload:
        return ResponseModel(code=404, message="上传记录不存在", data=None)
    
    return ResponseModel(
        code=200,
        message="success",
        data={
            "id": upload.id,
            "filename": upload.filename,
            "status": upload.status,
            "total_rows": upload.total_rows,
            "success_count": upload.success_count,
            "error_count": upload.error_count,
            "duplicate_count": upload.duplicate_count,
            "field_coverage_rate": upload.field_coverage_rate,
            "created_at": upload.created_at.isoformat() if upload.created_at else None
        }
    )


@router.get("/records", response_model=ResponseModel)
async def get_upload_records(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get upload history records"""
    records = db.query(UploadRecord).order_by(UploadRecord.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(UploadRecord).count()
    
    return ResponseModel(
        code=200,
        message="success",
        data={
            "total": total,
            "items": [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "file_type": r.file_type,
                    "community_name": r.community_name,
                    "total_rows": r.total_rows,
                    "success_count": r.success_count,
                    "error_count": r.error_count,
                    "duplicate_count": r.duplicate_count,
                    "field_coverage_rate": r.field_coverage_rate,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in records
            ]
        }
    )
