from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# ==================== Response Wrapper ====================
class ResponseModel(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None

# ==================== Resident Schemas ====================
class ResidentBase(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    id_card: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None
    ethnicity: Optional[str] = None
    marital_status: Optional[str] = None
    employment_status: Optional[str] = None
    medical_insurance: Optional[str] = None
    residence_address: Optional[str] = None
    household_address: Optional[str] = None
    grid_name: Optional[str] = None
    building_unit: Optional[str] = None
    household_number: Optional[str] = None
    is_low_income: Optional[bool] = False
    is_disabled: Optional[bool] = False
    disability_type: Optional[str] = None
    is_living_alone: Optional[bool] = False
    is_left_behind_child: Optional[bool] = False
    is_key_population: Optional[bool] = False
    key_population_type: Optional[str] = None
    is_special_support: Optional[bool] = False
    housing_id: Optional[int] = None
    custom_fields: Optional[Dict[str, Any]] = {}

class ResidentCreate(ResidentBase):
    pass

class ResidentUpdate(ResidentBase):
    pass

class ResidentOut(ResidentBase):
    id: int
    source_upload_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ResidentListResponse(BaseModel):
    total: int
    items: List[ResidentOut]

# ==================== Masked Resident (for display) ====================
class ResidentMasked(BaseModel):
    id: int
    name_masked: Optional[str] = None
    gender: Optional[str] = None
    id_card_masked: Optional[str] = None
    phone_masked: Optional[str] = None
    age: Optional[int] = None
    grid_name: Optional[str] = None
    residence_address: Optional[str] = None
    building_unit: Optional[str] = None
    is_key_population: Optional[bool] = False
    is_living_alone: Optional[bool] = False
    is_disabled: Optional[bool] = False
    is_low_income: Optional[bool] = False
    custom_fields: Optional[Dict[str, Any]] = {}
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ==================== Upload Schemas ====================
class UploadResponse(BaseModel):
    upload_id: int
    filename: str
    status: str
    message: str

class UploadStatus(BaseModel):
    id: int
    filename: str
    file_type: str
    community_name: Optional[str] = None
    total_rows: int
    success_count: int
    error_count: int
    duplicate_count: int
    field_coverage_rate: float
    status: str
    created_at: Optional[datetime] = None

# ==================== Field Mapping Schemas ====================
class FieldMappingItem(BaseModel):
    original_header: str
    standard_field: Optional[str] = None
    confidence: Optional[float] = 1.0
    is_confirmed: bool = False

class FieldMappingCreate(BaseModel):
    community_name: str
    mappings: List[FieldMappingItem]

class FieldMappingOut(BaseModel):
    id: int
    community_name: str
    original_header: str
    standard_field: str
    confidence: float
    is_confirmed: bool
    is_active: bool
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class HeaderRecognitionResponse(BaseModel):
    detected_headers: List[str]
    suggested_mappings: List[FieldMappingItem]
    community_name: Optional[str] = None

# ==================== Data Validation Schemas ====================
class ValidationError(BaseModel):
    row_number: int
    field: str
    error_type: str
    error_message: str
    original_value: Optional[str] = None

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[ValidationError]
    summary: Dict[str, int]

# ==================== Auto Fill Schemas ====================
class AutoFillRequest(BaseModel):
    query: str  # name/phone/id_card/address
    query_type: Optional[str] = "auto"  # auto/name/phone/id_card/address
    table_type: str = "general"  # 走访表/排查表/重点人员表/台账表

class AutoFillMatch(BaseModel):
    resident_id: int
    name: str
    name_masked: Optional[str] = None
    id_card_masked: Optional[str] = None
    phone_masked: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    grid_name: Optional[str] = None
    residence_address: Optional[str] = None
    building_unit: Optional[str] = None
    is_key_population: Optional[bool] = False
    key_population_type: Optional[str] = None
    match_score: float = 1.0

class AutoFillResponse(BaseModel):
    matches: List[AutoFillMatch]
    total_matches: int
    filled_data: Optional[Dict[str, Any]] = None

class AutoFillSaveRequest(BaseModel):
    resident_id: int
    table_type: str
    filled_data: Dict[str, Any]
    sync_to_master: bool = False

# ==================== NLQ Schemas ====================
class NLQRequest(BaseModel):
    question: str
    grid_name: Optional[str] = None

class NLQResponse(BaseModel):
    question: str
    generated_sql: Optional[str] = None
    results: List[Dict[str, Any]]
    total_count: int
    execution_time_ms: int

# ==================== Report Schemas ====================
class ReportRequest(BaseModel):
    report_type: str  # population_summary/grid_statistics/key_populations/etc
    grid_name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = {}
    format: str = "excel"  # excel/pdf

class ReportResponse(BaseModel):
    report_id: str
    report_type: str
    download_url: str
    summary: str
    generated_at: Optional[datetime] = None

# ==================== Housing Schemas ====================
class HousingBase(BaseModel):
    address: str
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    room_number: Optional[str] = None
    grid_name: Optional[str] = None
    housing_type: Optional[str] = "住宅"
    area_sqm: Optional[float] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None

class HousingCreate(HousingBase):
    pass

class HousingOut(HousingBase):
    id: int
    resident_count: int = 0
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class HousingResidentLink(BaseModel):
    resident_id: int
    housing_id: int

# ==================== Problem Report Schemas ====================
class ProblemBase(BaseModel):
    title: str
    problem_type: str
    description: str
    location: Optional[str] = None
    grid_name: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    priority: Optional[str] = "normal"

class ProblemCreate(ProblemBase):
    pass

class ProblemUpdate(BaseModel):
    status: Optional[str] = None
    resolution: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None

class ProblemOut(ProblemBase):
    id: int
    images: List[str] = []
    status: str
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ==================== Dashboard Schemas ====================
class DashboardStats(BaseModel):
    total_residents: int
    total_households: int
    total_grids: int
    key_populations: int
    elderly_alone: int
    disabled_persons: int
    low_income: int
    left_behind_children: int
    recent_uploads: int
    pending_problems: int

class GridStat(BaseModel):
    grid_name: str
    resident_count: int
    key_population_count: int
    elderly_count: int

# ==================== Settings Schemas ====================
class SettingItem(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
