from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.core import config, database
from app.core.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_KEYS = (
    "APP_ENV",
    "BACKEND_HOST",
    "BACKEND_PORT",
    "FRONTEND_PORT",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
)


def build_settings(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: str,
) -> Settings:
    values = {
        "APP_ENV": "test",
        "BACKEND_HOST": "127.0.0.1",
        "BACKEND_PORT": "8100",
        "FRONTEND_PORT": "4173",
        "POSTGRES_HOST": "db.internal",
        "POSTGRES_PORT": "5544",
        "POSTGRES_DB": "nutrition_test",
        "POSTGRES_USER": "nutrition_user",
        "POSTGRES_PASSWORD": "test-password",
    }
    values.update(overrides)

    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    return Settings(_env_file=None)


def test_settings_parse_valid_environment_and_integer_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings(monkeypatch)

    assert settings.app_env == "test"
    assert settings.backend_host == "127.0.0.1"
    assert settings.backend_port == 8100
    assert isinstance(settings.backend_port, int)
    assert settings.frontend_port == 4173
    assert isinstance(settings.frontend_port, int)
    assert settings.postgres_host == "db.internal"
    assert settings.postgres_port == 5544
    assert isinstance(settings.postgres_port, int)
    assert settings.postgres_db == "nutrition_test"
    assert settings.postgres_user == "nutrition_user"


def test_postgres_password_is_secret_and_hidden_from_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings(monkeypatch)

    assert isinstance(settings.postgres_password, SecretStr)
    assert settings.postgres_password.get_secret_value() == "test-password"
    assert "test-password" not in repr(settings)


def test_explicit_database_url_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explicit_url = "postgresql://explicit_user:DB_URL_SENTINEL_91@explicit-host:6432/explicit_db"
    settings = build_settings(monkeypatch, DATABASE_URL=explicit_url)

    assert isinstance(settings.database_url, SecretStr)
    assert settings.database_url.get_secret_value() == explicit_url
    assert "DB_URL_SENTINEL_91" not in repr(settings)


def test_database_url_is_built_from_postgres_fields_when_not_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings(
        monkeypatch,
        POSTGRES_USER="user+name",
        POSTGRES_PASSWORD="TOKEN@:/#",
        POSTGRES_DB="nutrition test",
    )

    assert isinstance(settings.database_url, SecretStr)
    assert settings.database_url.get_secret_value() == (
        "postgresql://user%2Bname:TOKEN%40%3A%2F%23@"
        "db.internal:5544/nutrition%20test"
    )
    assert "TOKEN@:/#" not in repr(settings)


@pytest.mark.parametrize(
    ("port_name", "invalid_value"),
    [
        ("BACKEND_PORT", "0"),
        ("FRONTEND_PORT", "65536"),
        ("POSTGRES_PORT", "not-a-port"),
    ],
)
def test_invalid_port_produces_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    port_name: str,
    invalid_value: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_settings(monkeypatch, **{port_name: invalid_value})

    error_message = str(exc_info.value)
    assert port_name.lower() in error_message.lower()
    assert "test-password" not in error_message


def test_non_local_settings_do_not_read_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "POSTGRES_DB=from_env_file\n"
        "POSTGRES_USER=from_env_file\n"
        "POSTGRES_PASSWORD=from_env_file\n",
        encoding="utf-8",
    )
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    config.get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError) as exc_info:
            config.get_settings()
    finally:
        config.get_settings.cache_clear()

    assert "postgres_db" in str(exc_info.value).lower()


def test_database_connection_uses_resolved_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explicit_url = "postgresql://db_user:DB_CONNECT_SENTINEL_42@db-host:5432/db_name"
    settings = build_settings(monkeypatch, DATABASE_URL=explicit_url)
    captured: dict[str, object] = {}
    connection_sentinel = object()

    def fake_connect(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return connection_sentinel

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database.psycopg, "connect", fake_connect)

    result = database.create_database_connection()

    assert result is connection_sentinel
    assert captured["args"] == (explicit_url,)
    assert captured["kwargs"] == {"connect_timeout": 5}


def test_invalid_app_environment_produces_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_settings(monkeypatch, APP_ENV="unknown-environment")

    error_message = str(exc_info.value)
    assert "app_env" in error_message.lower()
    assert "test-password" not in error_message


def test_missing_critical_setting_produces_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("POSTGRES_USER", "nutrition_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-value")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "postgres_db" in str(exc_info.value).lower()


def test_isolated_settings_instance_ignores_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_url_sentinel = "FILE_URL_SENTINEL_18"
    (tmp_path / ".env").write_text(
        f"DATABASE_URL=postgresql://file_user:{file_url_sentinel}@file-host/file_db\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = build_settings(monkeypatch)

    assert file_url_sentinel not in settings.database_url.get_secret_value()
    assert settings.postgres_host == "db.internal"


def test_local_settings_read_project_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "APP_ENV=local\n"
        "BACKEND_HOST=127.0.0.1\n"
        "BACKEND_PORT=8001\n"
        "FRONTEND_PORT=5174\n"
        "POSTGRES_HOST=local-db\n"
        "POSTGRES_PORT=5433\n"
        "POSTGRES_DB=local_nutrition\n"
        "POSTGRES_USER=local_user\n"
        "POSTGRES_PASSWORD=LOCAL_ENV_SENTINEL_77\n",
        encoding="utf-8",
    )
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    config.get_settings.cache_clear()

    try:
        settings = config.get_settings()
    finally:
        config.get_settings.cache_clear()

    assert settings.app_env == "local"
    assert settings.postgres_db == "local_nutrition"
    assert settings.frontend_port == 5174
    assert "LOCAL_ENV_SENTINEL_77" not in repr(settings)


def test_env_example_contains_no_active_secret_values() -> None:
    content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    active_values = {}

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        active_values[key] = value

    assert active_values["POSTGRES_PASSWORD"].startswith("<")
    assert "DATABASE_URL" in content
    assert "DATABASE_URL" not in active_values
