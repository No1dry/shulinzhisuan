import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / ".." / "db"
DB_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "数邻智算-网格员端"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = f"sqlite:///{DB_DIR}/community_governance.db"
    
    # Security
    SECRET_KEY: str = "shu-lin-zhi-suan-secret-key-2024-community-governance"
    AES_KEY: str = "shu-lin-zhisuan-aes256-key-2024!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: set = {"xlsx", "xls", "csv"}
    
    # LLM Configuration (for Smart Assistant)
    # 支持 Kimi / 智谱 / 通义千问 / OpenAI 等兼容 OpenAI API 格式的模型
    LLM_API_URL: str = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    LLM_API_KEY: str = "tp-cp8luqgxbkjgvztt5nksqfnbv7cqqvkzm7otqg7ppmiz1keu"
    LLM_MODEL: str = "mimo-v2.5"         # 例: moonshot-v1-8k / glm-4 / qwen-max / gpt-4o
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:4173", "http://localhost:4174"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
