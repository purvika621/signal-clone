from pathlib import Path

from pydantic import field_validator
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "Signal Desktop Clone API"
    database_url: str = "sqlite:///./data/signal.db"
    frontend_origin: str = "http://localhost:3000"
    websocket_origin: str | None = None
    port: int = Field(default=8000, ge=1, le=65535)
    sqlite_busy_timeout_ms: int = 5000
    mock_otp: str = "123456"
    session_days: int = 7
    session_cookie_secure: bool = False

    @field_validator("mock_otp")
    @classmethod
    def validate_otp(cls, value: str) -> str:
        if len(value) != 6 or not value.isascii() or not value.isdigit():
            raise ValueError("MOCK_OTP must contain six digits")
        return value

    @field_validator("session_days")
    @classmethod
    def validate_session_days(cls, value: int) -> int:
        if not 1 <= value <= 30:
            raise ValueError("SESSION_DAYS must be between 1 and 30")
        return value

    @field_validator("frontend_origin", "websocket_origin")
    @classmethod
    def validate_origin(cls, value: str | None) -> str | None:
        from urllib.parse import urlsplit

        if value is None:
            return None
        origin = urlsplit(value)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path not in {"", "/"} or origin.query or origin.fragment:
            raise ValueError("FRONTEND_ORIGIN must be a single HTTP(S) origin")
        return value.rstrip("/")

    @field_validator("sqlite_busy_timeout_ms")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if not 0 < value <= 60000:
            raise ValueError("SQLite busy timeout must be between 1 and 60000 ms")
        return value


settings = Settings()

