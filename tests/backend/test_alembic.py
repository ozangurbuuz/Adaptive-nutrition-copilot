import importlib.util
from pathlib import Path
from types import SimpleNamespace

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_ROOT = PROJECT_ROOT / "backend" / "alembic"
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"


def test_alembic_target_metadata_uses_central_base_without_database_connection(
    monkeypatch,
) -> None:
    import psycopg
    import sqlalchemy

    from app.models.base import Base

    def fail_if_database_is_used(*args, **kwargs):
        raise AssertionError("Alembic env import must not open a database connection")

    monkeypatch.setattr(sqlalchemy, "create_engine", fail_if_database_is_used)
    monkeypatch.setattr(psycopg, "connect", fail_if_database_is_used)

    env_path = ALEMBIC_ROOT / "env.py"
    assert env_path.is_file()

    spec = importlib.util.spec_from_file_location("stage3_alembic_env", env_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.target_metadata is Base.metadata


def test_alembic_revision_graph_loads_without_database_connection() -> None:
    assert ALEMBIC_INI.is_file()

    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())

    assert script.get_heads() == ["0001_orm_baseline"]
    assert len(revisions) == 1
    assert revisions[0].revision == "0001_orm_baseline"
    assert revisions[0].down_revision is None


def test_alembic_database_url_is_resolved_from_settings(monkeypatch) -> None:
    env_path = ALEMBIC_ROOT / "env.py"
    spec = importlib.util.spec_from_file_location("settings_alembic_env", env_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    database_url = "postgresql://migration_user:***@migration-host/migration_db"
    settings = SimpleNamespace(database_url=SecretStr(database_url))
    monkeypatch.setattr(module, "get_settings", lambda: settings)

    assert module.get_database_url() == database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


def test_alembic_files_contain_no_hardcoded_credentials_or_domain_tables() -> None:
    migration_files = [
        ALEMBIC_INI,
        ALEMBIC_ROOT / "env.py",
        ALEMBIC_ROOT / "script.py.mako",
        ALEMBIC_ROOT / "versions" / "0001_orm_baseline.py",
    ]

    for path in migration_files:
        assert path.is_file()
        content = path.read_text(encoding="utf-8").lower()
        assert "postgresql://" not in content
        assert "postgres_password" not in content

    baseline = migration_files[-1].read_text(encoding="utf-8").lower()
    assert "create_table" not in baseline
    assert "drop_table" not in baseline
