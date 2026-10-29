import json
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "Enterprise-Intelligence-Automation-API"
    APP_VERSION: str = "1.0.0"

    # API Security
    API_KEY: str = Field(default="dev_insecure_local_api_key_replace_for_real_work_32chars")
    WEBHOOK_SECRET: str = Field(default="dev_webhook_signing_secret_replace_in_prod_32chars")
    CORS_ORIGINS: List[str] = ["http://localhost:5678", "http://127.0.0.1:5678"]

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://eiap_admin:eiap_local_secure_pass_2026_x9@postgres:5432/business_analytics"
    )
    LOCAL_DATABASE_URL: str = Field(
        default="postgresql+psycopg://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/business_analytics"
    )

    # Feature Flags & Adapters
    FEATURE_FLAG_POWERBI_ENABLED: bool = False
    FEATURE_FLAG_AI_SUMMARY_ENABLED: bool = False
    AI_PROVIDER: str = "mock"
    POWERBI_ADAPTER: str = "mock"

    # SMTP & Email Dispatch (Defaults to Local Mailpit Catcher)
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "eiap-reports@internal.local"
    LOCAL_SMTP_HOST: str = "127.0.0.1"
    LOCAL_SMTP_PORT: int = 1025
    RUNNING_IN_DOCKER: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

