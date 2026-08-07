import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_CONFTEST = PROJECT_ROOT / "tests" / "integration" / "conftest.py"


def _load_integration_conftest():
    spec = importlib.util.spec_from_file_location(
        "integration_database_safety",
        INTEGRATION_CONFTEST,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_database_url_requires_postgresql_and_explicit_test_name() -> None:
    module = _load_integration_conftest()

    url = module._psycopg_url(
        "postgresql://integration_user:secret@localhost/nutrition_test"
    )

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "nutrition_test"
    with pytest.raises(pytest.UsageError):
        module._psycopg_url("postgresql://user:secret@localhost/production")
    with pytest.raises(pytest.UsageError):
        module._psycopg_url("sqlite:///nutrition_test.db")


def test_test_database_url_rejects_application_database_name(
    monkeypatch,
) -> None:
    module = _load_integration_conftest()
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql://test_user:secret@test-host/nutrition_test",
    )
    monkeypatch.setattr(
        module,
        "_application_database_url",
        lambda: make_url(
            "postgresql://app_user:secret@application-host/nutrition_test"
        ),
    )

    with pytest.raises(pytest.UsageError):
        module._validated_test_database_url()


def test_unknown_database_objects_block_cleanup(monkeypatch) -> None:
    module = _load_integration_conftest()

    class Inspector:
        def get_table_names(self):
            return ["unexpected_business_table"]

        def get_view_names(self):
            return []

    monkeypatch.setattr(module.sa, "inspect", lambda engine: Inspector())

    with pytest.raises(pytest.UsageError):
        module._assert_only_managed_objects(object())
