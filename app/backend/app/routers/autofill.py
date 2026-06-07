import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ResidentMaster
from app.schemas import ResponseModel
from app.services.file_parser import parse_all_sheets
from app.services.template_filler import (
    match_template_headers,
    fill_template,
    generate_excel,
    generate_csv,
    REVERSE_FIELD_MAP,
)
from app.encryption import decrypt_field

router = APIRouter(prefix="/autofill", tags=["AutoFill"])

EXPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "exports"))
os.makedirs(EXPORT_DIR, exist_ok=True)


def _read_template_headers(file_path: str, ext: str) -> list:
    """Read headers directly from first row - for template files (headers only)."""
    if ext == 'csv':
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            first_row = next(reader, [])
            return [str(c).strip() for c in first_row if c is not None and str(c).strip()]
    else:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if len(cells) >= 2:  # At least 2 non-empty cells = header row
                wb.close()
                return cells
        wb.close()
        return []


@router.post("/upload-template", response_model=ResponseModel)
async def upload_template(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a template file (headers only) and match to resident fields."""
    try:
        filename = file.filename or "template.xlsx"
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        
        if ext not in ["xlsx", "xls", "csv"]:
            return ResponseModel(code=400, message=f"不支持的格式: {ext}", data=None)
        
        tmp_path = os.path.join(EXPORT_DIR, f"tmp_{uuid.uuid4()}_{filename}")
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        # For template files, read first non-empty row directly as headers
        # (don't use parse_all_sheets which has complex title/header detection)
        headers = _read_template_headers(tmp_path, ext)
        
        # Also try parse_all_sheets as fallback for multi-row templates
        if not headers:
            sheets = parse_all_sheets(tmp_path, ext)
            if sheets and sheets[0].headers:
                headers = sheets[0].headers
        
        try:
            os.remove(tmp_path)
        except:
            pass
        
        if not headers:
            return ResponseModel(code=400, message="无法从文件中读取表头，请确保文件第一行包含表头", data=None)
        
        matched = match_template_headers(headers)
        
        available_fields = []
        for std_field, aliases in REVERSE_FIELD_MAP.items():
            available_fields.append({
                "field": std_field,
                "label": aliases[0] if aliases else std_field,
                "aliases": aliases
            })
        
        matched_count = sum(1 for m in matched if m['matched'])
        
        return ResponseModel(
            code=200,
            message=f"模板解析成功，共{len(headers)}个字段，匹配{matched_count}个",
            data={
                "filename": filename,
                "headers": headers,
                "matched_fields": matched,
                "available_fields": available_fields,
                "sheet_count": 1,
            }
        )
    
    except Exception as e:
        import traceback
        return ResponseModel(code=500, message=f"模板解析失败: {str(e)}", data=None)


@router.post("/fill-template", response_model=ResponseModel)
async def fill_template_endpoint(payload: dict, db: Session = Depends(get_db)):
    """Fill template with resident data."""
    try:
        headers = payload.get("headers", [])
        field_mapping = payload.get("field_mapping", [])
        grid_name = payload.get("grid_name")
        filters = payload.get("filters", {})
        fmt = payload.get("format", "excel")
        output_filename = payload.get("filename", f"filled_{uuid.uuid4().hex[:8]}")
        
        if not headers or not field_mapping:
            return ResponseModel(code=400, message="请提供表头和字段映射", data=None)
        
        filled_rows = fill_template(db, headers, field_mapping, grid_name, filters)
        
        if not filled_rows:
            return ResponseModel(code=200, message="查询条件下没有居民数据", data={"rows": [], "count": 0})
        
        ext = ".xlsx" if fmt == "excel" else ".csv"
        final_filename = f"{output_filename}{ext}"
        output_path = os.path.join(EXPORT_DIR, final_filename)
        
        if fmt == "excel":
            generate_excel(headers, filled_rows, output_path)
        else:
            generate_csv(headers, filled_rows, output_path)
        
        return ResponseModel(
            code=200,
            message=f"表格生成成功，共{len(filled_rows)}条记录",
            data={
                "total_count": len(filled_rows),
                "headers": headers,
                "preview": filled_rows[:20],
                "download_url": f"/api/autofill/download/{final_filename}",
                "filename": final_filename,
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"填表失败: {str(e)}", data=None)


@router.post("/generate-custom-table", response_model=ResponseModel)
async def generate_custom_table(payload: dict, db: Session = Depends(get_db)):
    """Generate custom table from selected fields."""
    try:
        fields = payload.get("fields", [])
        grid_name = payload.get("grid_name")
        filters = payload.get("filters", {})
        fmt = payload.get("format", "excel")
        table_name = payload.get("table_name", "自定义表格")
        
        if not fields:
            return ResponseModel(code=400, message="请至少选择一个字段", data=None)
        
        headers = [f["header"] for f in fields]
        field_mapping = [
            {"template_header": f["header"], "standard_field": f.get("standard_field", "")}
            for f in fields
        ]
        
        filled_rows = fill_template(db, headers, field_mapping, grid_name, filters)
        
        if not filled_rows:
            return ResponseModel(code=200, message="查询条件下没有居民数据", data={"rows": [], "count": 0})
        
        ext = ".xlsx" if fmt == "excel" else ".csv"
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in table_name)
        final_filename = f"{safe_name}_{uuid.uuid4().hex[:6]}{ext}"
        output_path = os.path.join(EXPORT_DIR, final_filename)
        
        if fmt == "excel":
            generate_excel(headers, filled_rows, output_path, sheet_name=table_name[:31])
        else:
            generate_csv(headers, filled_rows, output_path)
        
        return ResponseModel(
            code=200,
            message=f"表格「{table_name}」生成成功，共{len(filled_rows)}条记录",
            data={
                "total_count": len(filled_rows),
                "headers": headers,
                "preview": filled_rows[:20],
                "download_url": f"/api/autofill/download/{final_filename}",
                "filename": final_filename,
            }
        )
    
    except Exception as e:
        return ResponseModel(code=500, message=f"生成失败: {str(e)}", data=None)


@router.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download generated file via API endpoint.
    This ensures files are served with correct Content-Type regardless of static file routing.
    """
    file_path = os.path.join(EXPORT_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # Determine content type based on extension
    if filename.endswith('.xlsx'):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith('.csv'):
        media_type = "text/csv; charset=utf-8-sig"
    elif filename.endswith('.xls'):
        media_type = "application/vnd.ms-excel"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@router.get("/available-fields", response_model=ResponseModel)
async def get_available_fields():
    """Get list of available resident fields for custom table creation."""
    fields = []
    for std_field, aliases in REVERSE_FIELD_MAP.items():
        fields.append({
            "field": std_field,
            "label": aliases[0] if aliases else std_field,
            "aliases": aliases,
        })
    
    return ResponseModel(code=200, message="success", data=fields)


@router.get("/grids", response_model=ResponseModel)
async def get_grids(db: Session = Depends(get_db)):
    """Get all grid names."""
    grids = db.query(ResidentMaster.grid_name).distinct().filter(
        ResidentMaster.grid_name.isnot(None)
    ).all()
    return ResponseModel(code=200, message="success", data=[g[0] for g in grids if g[0]])
