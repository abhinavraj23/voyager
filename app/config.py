from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # FastAPI settings
    app_name: str = "Tour Recommendation Service"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # ClickHouse settings
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_db: str = "default"
    clickhouse_secure: bool = False
    
    # OpenAI settings
    openai_api_key: Optional[str] = None
    
    # Weather API settings
    weather_api_key: Optional[str] = None
    
    # API settings
    api_prefix: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings() 