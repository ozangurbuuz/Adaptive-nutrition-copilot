import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
Port = Annotated[int, Field(ge=1, le=65535)]


class Settings(BaseSettings):
    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "adaptive-nutrition-copilot"

    backend_host: str = "0.0.0.0"
    backend_port: Port = 8000
    frontend_port: Port = 5173

    postgres_host: str = "127.0.0.1"
    postgres_port: Port = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    database_url: SecretStr | None = None

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if self.database_url is None:
            user = quote(self.postgres_user, safe="")
            password = quote(self.postgres_password.get_secret_value(), safe="")
            database = quote(self.postgres_db, safe="")
            self.database_url = SecretStr(
                f"postgresql://{user}:{password}@"
                f"{self.postgres_host}:{self.postgres_port}/{database}"
            )

        return self

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    env_file = PROJECT_ROOT / ".env" if app_env == "local" else None
    return Settings(_env_file=env_file, _env_file_encoding="utf-8")