import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, ForeignKey, Index
from app.database import Base

class ResidentMaster(Base):
    """居民主表 - 总表数据"""
    __tablename__ = "resident_master"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Encrypted sensitive fields
    name_encrypted = Column(String(255), nullable=True, index=True)
    id_card_encrypted = Column(String(500), nullable=True, unique=True, index=True)
    phone_encrypted = Column(String(500), nullable=True, index=True)
    
    # Masked fields for display (duplicate storage for query performance)
    name_masked = Column(String(100), nullable=True, index=True)
    id_card_masked = Column(String(100), nullable=True, index=True)
    phone_masked = Column(String(50), nullable=True, index=True)
    
    # Standard fields
    gender = Column(String(10), nullable=True, index=True)
    birth_date = Column(String(20), nullable=True)
    age = Column(Integer, nullable=True, index=True)
    ethnicity = Column(String(50), nullable=True)
    marital_status = Column(String(20), nullable=True)
    employment_status = Column(String(50), nullable=True)
    medical_insurance = Column(String(50), nullable=True)
    
    # Address fields
    residence_address = Column(String(500), nullable=True)
    household_address = Column(String(500), nullable=True)
    
    # Grid info
    grid_name = Column(String(100), nullable=True, index=True)
    building_unit = Column(String(100), nullable=True)
    household_number = Column(String(100), nullable=True)
    
    # Special status flags
    is_low_income = Column(Boolean, default=False, index=True)
    is_disabled = Column(Boolean, default=False, index=True)
    disability_type = Column(String(100), nullable=True)
    is_living_alone = Column(Boolean, default=False, index=True)
    is_left_behind_child = Column(Boolean, default=False, index=True)
    is_key_population = Column(Boolean, default=False, index=True)
    key_population_type = Column(String(100), nullable=True)
    is_special_support = Column(Boolean, default=False, index=True)
    
    # Housing association
    housing_id = Column(Integer, ForeignKey("housing.id"), nullable=True, index=True)
    
    # Metadata
    source_upload_id = Column(Integer, ForeignKey("upload_records.id"), nullable=True)
    custom_fields = Column(JSON, default=dict)  # For fields not in standard set
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    __table_args__ = (
        Index('idx_resident_grid', 'grid_name'),
        Index('idx_resident_age', 'age'),
        Index('idx_resident_key_pop', 'is_key_population'),
    )

class Housing(Base):
    """房屋信息表 - 人房关联"""
    __tablename__ = "housing"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    address = Column(String(500), nullable=False, index=True)
    building_name = Column(String(100), nullable=True)
    unit_number = Column(String(50), nullable=True)
    room_number = Column(String(50), nullable=True)
    grid_name = Column(String(100), nullable=True, index=True)
    housing_type = Column(String(50), nullable=True)  # 住宅/商铺/车库等
    area_sqm = Column(Float, nullable=True)
    owner_name = Column(String(100), nullable=True)
    owner_phone = Column(String(50), nullable=True)
    resident_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class FieldMapping(Base):
    """表头映射规则表 - 核心功能"""
    __tablename__ = "field_mapping"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    community_name = Column(String(200), nullable=False, index=True)
    original_header = Column(String(200), nullable=False)  # 原始表头
    standard_field = Column(String(100), nullable=False)   # 标准字段名
    confidence = Column(Float, default=1.0)  # LLM匹配置信度
    is_confirmed = Column(Boolean, default=False)  # 用户是否已确认
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    __table_args__ = (
        Index('idx_mapping_community', 'community_name', 'original_header'),
    )

class UploadRecord(Base):
    """上传日志表"""
    __tablename__ = "upload_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # xlsx/xls/csv/image
    community_name = Column(String(200), nullable=True)
    total_rows = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    field_coverage_rate = Column(Float, default=0.0)
    status = Column(String(50), default="pending")  # pending/processing/completed/failed
    mapping_config = Column(JSON, default=dict)
    error_details = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DataError(Base):
    """数据错误日志表"""
    __tablename__ = "data_errors"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    upload_id = Column(Integer, ForeignKey("upload_records.id"), nullable=True)
    resident_id = Column(Integer, ForeignKey("resident_master.id"), nullable=True)
    error_type = Column(String(100), nullable=False)  # id_card/phone/required/format
    error_field = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    original_value = Column(Text, nullable=True)
    row_number = Column(Integer, nullable=True)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ProblemReport(Base):
    """问题上报表 - 同时存储信息上报和协商"""
    __tablename__ = "problem_reports"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    problem_type = Column(String(100), nullable=False)  # 安全隐患/居民纠纷/设施损坏/环境卫生/其他/协商事项
    description = Column(Text, nullable=False)
    location = Column(String(500), nullable=True)
    grid_name = Column(String(100), nullable=True)
    reporter_name = Column(String(100), nullable=True)
    reporter_phone = Column(String(50), nullable=True)
    images = Column(JSON, default=list)
    status = Column(String(50), default="pending")  # pending/processing/resolved/closed/negotiating
    priority = Column(String(20), default="normal")
    assigned_to = Column(String(100), nullable=True)
    resolution = Column(Text, nullable=True)  # 处理结果/协商结论
    # 对话记录 [{role:'resident'|'worker', content:'', time:'', author:''}, ...]
    replies = Column(JSON, default=list)
    # 协商相关
    is_negotiation = Column(Boolean, default=False)
    topic = Column(String(500), nullable=True)  # 协商议题
    # 参与人 [{name:'', phone:'', role:'', status:'pending'|'accepted'|'rejected', address:''}, ...]
    participants = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class AutoFillRecord(Base):
    """自动填表记录"""
    __tablename__ = "auto_fill_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    table_type = Column(String(100), nullable=False)  # 走访表/排查表/重点人员表/台账表
    resident_id = Column(Integer, ForeignKey("resident_master.id"), nullable=False)
    filled_data = Column(JSON, default=dict)
    is_synced_to_master = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class SystemSetting(Base):
    """系统设置表"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ── 居民端模型 ────────────────────────────────────

class Notice(Base):
    """通知公告"""
    __tablename__ = "notices"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), default="通知")  # 通知/公告/活动/紧急
    is_top = Column(Boolean, default=False)  # 置顶
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class NewsItem(Base):
    """新闻资讯"""
    __tablename__ = "news_items"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    source = Column(String(100), nullable=True)
    cover_image = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Policy(Base):
    """便民政策"""
    __tablename__ = "policies"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    category = Column(String(50), default="综合")  # 综合/民政/医保/住房/就业/教育
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ResidentUser(Base):
    """居民用户（登录用）"""
    __tablename__ = "resident_users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    avatar = Column(String(500), nullable=True)  # 头像URL
    id_card_last4 = Column(String(10), nullable=True)  # 身份证后4位
    grid_name = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
