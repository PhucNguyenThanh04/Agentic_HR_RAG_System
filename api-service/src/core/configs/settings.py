import http
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi_mail import ConnectionConfig
BASE_DIR = Path(__file__).resolve().parents[3]


class Setting(BaseSettings):
    # App
    app_name: str = "API Service"
    environment: str = "development"
    debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Rag service 

    rag_api_url: str
    rag_api_key: str

    # AI service
    ai_service_base_url: str
    face_service_api_key: str

    session_ttl_seconds: int

    # Database
    database_url: str
    database_port: int
    database_host: str
    database_name: str
    database_user: str
    database_password: str
    database_timezone: str = "Asia/Ho_Chi_Minh"

    # Redis
    redis_host: str
    redis_port: int
    redis_password: str = ""
    redis_url: str
    redis_db_session: int = 0
    redis_db_attendance: int = 1

    # Mail
    mail_username: str
    mail_password: str
    mail_from: str
    mail_port: int
    mail_server: str
    mail_tls: bool
    mail_ssl: bool

    @property
    def email_config(self):
        return ConnectionConfig(
            MAIL_USERNAME=self.mail_username,
            MAIL_PASSWORD=self.mail_password,
            MAIL_FROM=self.mail_from,
            MAIL_PORT=self.mail_port,
            MAIL_SERVER=self.mail_server,
            MAIL_STARTTLS=self.mail_tls,
            MAIL_SSL_TLS=self.mail_ssl,
            USE_CREDENTIALS=bool(self.mail_username and self.mail_password),
        )

    # JWT / Auth
    jwt_secret_key: str
    refresh_token_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int

    # Auth rate limit
    login_rate_limit_ip_max_attempts: int 
    login_rate_limit_user_max_attempts: int
    login_rate_limit_window_seconds: int

    # Password reset / OTP
    password_reset_token_expire_minutes: int = 15
    otp_expire_minutes: int = 5
    otp_max_attempts: int = 5
    otp_lock_minutes: int = 3

    # Bootstrap admin
    bootstrap_admin_enabled: bool = True
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_full_name: str = ""

    # CORS
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def redis_session_url(self) -> str:
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db_session}"
            )

        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_session}"

    @property
    def redis_attendance_url(self) -> str:
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db_attendance}"
            )

        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_attendance}"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Setting:
    return Setting()


settings = get_settings()
