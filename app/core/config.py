from pydantic import EmailStr
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "SoulTalk"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str
    
    # Keycloak
    KEYCLOAK_SERVER_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str
    KEYCLOAK_ADMIN_USERNAME: str
    KEYCLOAK_ADMIN_PASSWORD: str
    KEYCLOAK_MOBILE_CLIENT_ID: str
    KEYCLOAK_MOBILE_CLIENT_SECRET: str
    
    # Redis
    REDIS_URL: str
    
    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:19006",
        "http://127.0.0.1:19006"
    ]
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()