import importlib.util
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql


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
    assert set(module.target_metadata.tables) == {
        "users",
        "dietitian_profiles",
        "client_profiles",
        "client_health_profiles",
        "client_preferences",
        "client_allergies",
        "client_medical_conditions",
        "client_medications",
        "nutrition_plans",
        "plan_days",
        "meals",
        "meal_items",
        "foods",
        "food_nutrients",
    }


def test_alembic_revision_graph_loads_without_database_connection() -> None:
    assert ALEMBIC_INI.is_file()

    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())

    assert script.get_heads() == ["0010_add_meal_item_sort_order"]
    assert len(revisions) == 10
    assert revisions[0].revision == "0010_add_meal_item_sort_order"
    assert revisions[0].down_revision == "0009_link_meal_items_to_foods"
    assert revisions[1].revision == "0009_link_meal_items_to_foods"
    assert revisions[1].down_revision == "0008_create_food_catalog"
    assert revisions[2].revision == "0008_create_food_catalog"
    assert revisions[2].down_revision == "0007_create_plan_structure"
    assert revisions[3].revision == "0007_create_plan_structure"
    assert revisions[3].down_revision == "0006_create_nutrition_plans"
    assert revisions[4].revision == "0006_create_nutrition_plans"
    assert revisions[4].down_revision == "0005_create_clinical_records"
    assert revisions[5].revision == "0005_create_clinical_records"
    assert revisions[5].down_revision == "0004_create_client_details"
    assert revisions[6].revision == "0004_create_client_details"
    assert revisions[6].down_revision == "0003_create_profiles"
    assert revisions[7].revision == "0003_create_profiles"
    assert revisions[7].down_revision == "0002_create_users"
    assert revisions[8].revision == "0002_create_users"
    assert revisions[8].down_revision == "0001_orm_baseline"
    assert revisions[9].revision == "0001_orm_baseline"
    assert revisions[9].down_revision is None


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


def test_alembic_online_migration_uses_injected_connection(monkeypatch) -> None:
    env_path = ALEMBIC_ROOT / "env.py"
    spec = importlib.util.spec_from_file_location("injected_alembic_env", env_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    connection = object()
    events = []

    class TransactionContext:
        def __enter__(self):
            events.append("transaction_started")

        def __exit__(self, exc_type, exc_value, traceback):
            events.append("transaction_finished")

    fake_context = SimpleNamespace(
        config=SimpleNamespace(attributes={"connection": connection}),
        configure=lambda **kwargs: events.append(("configure", kwargs)),
        begin_transaction=lambda: TransactionContext(),
        run_migrations=lambda: events.append("migrations_run"),
    )
    monkeypatch.setattr(module, "context", fake_context)
    monkeypatch.setattr(
        module,
        "engine_from_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Injected connection must avoid engine creation")
        ),
    )
    monkeypatch.setattr(
        module,
        "get_database_url",
        lambda: (_ for _ in ()).throw(
            AssertionError("Injected connection must avoid application settings")
        ),
    )

    module.run_migrations_online()

    assert events == [
        (
            "configure",
            {
                "connection": connection,
                "target_metadata": module.target_metadata,
                "compare_type": True,
            },
        ),
        "transaction_started",
        "migrations_run",
        "transaction_finished",
    ]


def test_alembic_files_contain_no_hardcoded_credentials() -> None:
    migration_files = [
        ALEMBIC_INI,
        ALEMBIC_ROOT / "env.py",
        ALEMBIC_ROOT / "script.py.mako",
        ALEMBIC_ROOT / "versions" / "0001_orm_baseline.py",
        ALEMBIC_ROOT / "versions" / "0002_create_users.py",
        ALEMBIC_ROOT / "versions" / "0003_create_profiles.py",
        ALEMBIC_ROOT / "versions" / "0004_create_client_details.py",
        ALEMBIC_ROOT / "versions" / "0005_create_clinical_records.py",
        ALEMBIC_ROOT / "versions" / "0006_create_nutrition_plans.py",
        ALEMBIC_ROOT / "versions" / "0007_create_plan_structure.py",
        ALEMBIC_ROOT / "versions" / "0008_create_food_catalog.py",
        ALEMBIC_ROOT / "versions" / "0009_link_meal_items_to_foods.py",
    ]

    for path in migration_files:
        assert path.is_file()
        content = path.read_text(encoding="utf-8").lower()
        assert "postgresql://" not in content
        assert "postgres_password" not in content

    baseline = (ALEMBIC_ROOT / "versions" / "0001_orm_baseline.py").read_text(
        encoding="utf-8",
    ).lower()
    assert "create_table" not in baseline
    assert "drop_table" not in baseline

    user_migration = (
        ALEMBIC_ROOT / "versions" / "0002_create_users.py"
    ).read_text(encoding="utf-8").lower()
    assert "password_hash" not in user_migration


def test_user_migration_creates_only_expected_table_and_index(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0002_create_users.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_user_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    created_tables = []
    create_index_calls = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, sa.MetaData(), *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(
        module.op,
        "create_table",
        capture_create_table,
    )
    monkeypatch.setattr(
        module.op,
        "create_index",
        lambda *args, **kwargs: create_index_calls.append((args, kwargs)),
    )

    module.upgrade()

    assert len(created_tables) == 1
    table = created_tables[0]
    assert table.name == "users"

    columns = dict(table.columns)
    assert set(columns) == {
        "id",
        "email",
        "role",
        "is_active",
        "is_verified",
        "created_at",
        "updated_at",
    }
    assert isinstance(columns["id"].type, postgresql.UUID)
    assert columns["id"].type.as_uuid is True
    assert isinstance(columns["email"].type, sa.String)
    assert columns["email"].type.length == 320
    assert columns["email"].nullable is False
    assert isinstance(columns["role"].type, sa.Enum)
    assert columns["role"].type.enums == ["DIETITIAN", "CLIENT", "ADMIN"]
    assert columns["role"].nullable is False
    assert isinstance(columns["is_active"].type, sa.Boolean)
    assert str(columns["is_active"].server_default.arg).lower() == "true"
    assert isinstance(columns["is_verified"].type, sa.Boolean)
    assert str(columns["is_verified"].server_default.arg).lower() == "false"
    assert isinstance(columns["created_at"].type, sa.DateTime)
    assert columns["created_at"].type.timezone is True
    assert isinstance(columns["updated_at"].type, sa.DateTime)
    assert columns["updated_at"].type.timezone is True

    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    ]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uq_users_email"
    assert [column.name for column in unique_constraints[0].columns] == ["email"]
    assert create_index_calls == [
        (("ix_users_email", "users", ["email"]), {"unique": False}),
    ]


def test_user_migration_downgrade_removes_only_users_table(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0002_create_users.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_user_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    operations = []
    monkeypatch.setattr(
        module.op,
        "drop_index",
        lambda *args, **kwargs: operations.append(("drop_index", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda *args, **kwargs: operations.append(("drop_table", args, kwargs)),
    )

    module.downgrade()

    assert operations == [
        ("drop_index", ("ix_users_email",), {"table_name": "users"}),
        ("drop_table", ("users",), {}),
    ]


def test_profile_migration_creates_only_profile_tables(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0003_create_profiles.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_profile_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = sa.MetaData()
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)

    module.upgrade()

    assert [table.name for table in created_tables] == [
        "dietitian_profiles",
        "client_profiles",
    ]

    expected_columns = {
        "dietitian_profiles": {
            "id",
            "user_id",
            "display_name",
            "professional_title",
            "license_number",
            "created_at",
            "updated_at",
        },
        "client_profiles": {
            "id",
            "user_id",
            "display_name",
            "created_at",
            "updated_at",
        },
    }

    for table in created_tables:
        assert set(table.columns.keys()) == expected_columns[table.name]
        assert isinstance(table.c.id.type, postgresql.UUID)
        assert isinstance(table.c.user_id.type, postgresql.UUID)
        assert table.c.user_id.nullable is False

        foreign_keys = list(table.foreign_key_constraints)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].ondelete == "CASCADE"
        assert [element.target_fullname for element in foreign_keys[0].elements] == [
            "users.id",
        ]

        unique_constraints = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        ]
        assert len(unique_constraints) == 1
        assert [column.name for column in unique_constraints[0].columns] == [
            "user_id",
        ]


def test_profile_migration_downgrade_removes_only_profile_tables(
    monkeypatch,
) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0003_create_profiles.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_profile_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert dropped_tables == ["client_profiles", "dietitian_profiles"]


def test_client_detail_migration_creates_only_expected_tables(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0004_create_client_details.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_client_detail_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = sa.MetaData()
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)

    module.upgrade()

    assert [table.name for table in created_tables] == [
        "client_health_profiles",
        "client_preferences",
    ]
    expected_columns = {
        "client_health_profiles": {
            "id",
            "client_profile_id",
            "date_of_birth",
            "biological_sex",
            "height_cm",
            "weight_kg",
            "created_at",
            "updated_at",
        },
        "client_preferences": {
            "id",
            "client_profile_id",
            "dietary_pattern",
            "created_at",
            "updated_at",
        },
    }

    for table in created_tables:
        assert set(table.columns.keys()) == expected_columns[table.name]
        assert isinstance(table.c.id.type, postgresql.UUID)
        assert isinstance(table.c.client_profile_id.type, postgresql.UUID)
        assert table.c.client_profile_id.nullable is False

        foreign_keys = list(table.foreign_key_constraints)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].ondelete == "CASCADE"
        assert [element.target_fullname for element in foreign_keys[0].elements] == [
            "client_profiles.id",
        ]

        unique_constraints = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        ]
        assert len(unique_constraints) == 1
        assert [column.name for column in unique_constraints[0].columns] == [
            "client_profile_id",
        ]

    health_table = metadata.tables["client_health_profiles"]
    assert isinstance(health_table.c.height_cm.type, sa.Numeric)
    assert (health_table.c.height_cm.type.precision, health_table.c.height_cm.type.scale) == (
        5,
        2,
    )
    assert isinstance(health_table.c.weight_kg.type, sa.Numeric)
    assert (health_table.c.weight_kg.type.precision, health_table.c.weight_kg.type.scale) == (
        6,
        2,
    )


def test_client_detail_migration_downgrade_removes_only_new_tables(
    monkeypatch,
) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0004_create_client_details.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_client_detail_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert dropped_tables == ["client_preferences", "client_health_profiles"]


def test_clinical_record_migration_creates_only_expected_tables(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0005_create_clinical_records.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_clinical_record_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = sa.MetaData()
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)

    module.upgrade()

    assert [table.name for table in created_tables] == [
        "client_allergies",
        "client_medical_conditions",
        "client_medications",
    ]
    expected_columns = {
        "client_allergies": {
            "id",
            "client_profile_id",
            "allergen_name",
            "severity",
            "notes",
            "created_at",
            "updated_at",
        },
        "client_medical_conditions": {
            "id",
            "client_profile_id",
            "condition_name",
            "status",
            "notes",
            "created_at",
            "updated_at",
        },
        "client_medications": {
            "id",
            "client_profile_id",
            "medication_name",
            "status",
            "notes",
            "created_at",
            "updated_at",
        },
    }

    for table in created_tables:
        assert set(table.columns.keys()) == expected_columns[table.name]
        assert isinstance(table.c.id.type, postgresql.UUID)
        assert isinstance(table.c.client_profile_id.type, postgresql.UUID)
        assert table.c.client_profile_id.nullable is False
        assert not any(isinstance(column.type, sa.JSON) for column in table.columns)

        foreign_keys = list(table.foreign_key_constraints)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].ondelete == "CASCADE"
        assert [element.target_fullname for element in foreign_keys[0].elements] == [
            "client_profiles.id",
        ]

    allergy_table = metadata.tables["client_allergies"]
    unique_constraints = [
        constraint
        for constraint in allergy_table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    ]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == (
        "uq_client_allergies_client_profile_id_allergen_name"
    )
    assert [column.name for column in unique_constraints[0].columns] == [
        "client_profile_id",
        "allergen_name",
    ]
    assert allergy_table.c.severity.nullable is False


def test_clinical_record_migration_downgrade_removes_only_new_tables(
    monkeypatch,
) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0005_create_clinical_records.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_clinical_record_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert dropped_tables == [
        "client_medications",
        "client_medical_conditions",
        "client_allergies",
    ]


def test_nutrition_plan_migration_creates_only_expected_table(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0006_create_nutrition_plans.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_nutrition_plan_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = sa.MetaData()
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)

    module.upgrade()

    assert [table.name for table in created_tables] == ["nutrition_plans"]
    table = created_tables[0]
    assert set(table.columns.keys()) == {
        "id",
        "client_profile_id",
        "dietitian_profile_id",
        "title",
        "status",
        "starts_on",
        "ends_on",
        "notes",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, postgresql.UUID)
    assert table.c.client_profile_id.nullable is False
    assert table.c.dietitian_profile_id.nullable is False
    assert table.c.title.nullable is False
    assert table.c.status.nullable is False
    assert str(table.c.status.server_default.arg) == "'DRAFT'"

    foreign_keys = {
        tuple(element.target_fullname for element in constraint.elements): constraint
        for constraint in table.foreign_key_constraints
    }
    assert set(foreign_keys) == {
        ("client_profiles.id",),
        ("dietitian_profiles.id",),
    }
    assert all(constraint.ondelete == "RESTRICT" for constraint in foreign_keys.values())

    date_checks = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
        and constraint.name == "ck_nutrition_plans_date_range"
    ]
    assert len(date_checks) == 1


def test_nutrition_plan_migration_downgrade_removes_only_plan_table(
    monkeypatch,
) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0006_create_nutrition_plans.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_nutrition_plan_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert dropped_tables == ["nutrition_plans"]


def test_plan_structure_migration_creates_only_expected_tables(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0007_create_plan_structure.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_plan_structure_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = sa.MetaData()
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)

    module.upgrade()

    assert [table.name for table in created_tables] == [
        "plan_days",
        "meals",
        "meal_items",
    ]
    expected_columns = {
        "plan_days": {
            "id",
            "nutrition_plan_id",
            "day_number",
            "label",
            "created_at",
            "updated_at",
        },
        "meals": {
            "id",
            "plan_day_id",
            "meal_type",
            "name",
            "sort_order",
            "created_at",
            "updated_at",
        },
        "meal_items": {
            "id",
            "meal_id",
            "item_name",
            "quantity",
            "unit",
            "created_at",
            "updated_at",
        },
    }
    expected_foreign_keys = {
        "plan_days": "nutrition_plans.id",
        "meals": "plan_days.id",
        "meal_items": "meals.id",
    }

    for table in created_tables:
        assert set(table.columns.keys()) == expected_columns[table.name]
        assert isinstance(table.c.id.type, postgresql.UUID)
        foreign_keys = list(table.foreign_key_constraints)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].ondelete == "CASCADE"
        assert [element.target_fullname for element in foreign_keys[0].elements] == [
            expected_foreign_keys[table.name],
        ]

    assert isinstance(metadata.tables["meal_items"].c.quantity.type, sa.Numeric)
    assert (
        metadata.tables["meal_items"].c.quantity.type.precision,
        metadata.tables["meal_items"].c.quantity.type.scale,
    ) == (10, 3)

    constraint_names = {
        constraint.name
        for table in created_tables
        for constraint in table.constraints
    }
    assert {
        "uq_plan_days_nutrition_plan_id_day_number",
        "ck_plan_days_day_number_positive",
        "uq_meals_plan_day_id_sort_order",
        "ck_meals_sort_order_non_negative",
        "ck_meal_items_quantity_positive",
        "meal_type",
        "meal_item_unit",
    }.issubset(constraint_names)


def test_plan_structure_migration_downgrade_uses_dependency_order(
    monkeypatch,
) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0007_create_plan_structure.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_plan_structure_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert dropped_tables == ["meal_items", "meals", "plan_days"]


def test_food_catalog_migration_creates_only_expected_tables(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0008_create_food_catalog.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_food_catalog_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = sa.MetaData()
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)

    module.upgrade()

    assert [table.name for table in created_tables] == ["foods", "food_nutrients"]
    assert set(metadata.tables["foods"].columns.keys()) == {
        "id",
        "name",
        "category",
        "default_serving_quantity",
        "default_serving_unit",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert set(metadata.tables["food_nutrients"].columns.keys()) == {
        "id",
        "food_id",
        "reference_quantity",
        "reference_unit",
        "calories_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "fiber_g",
        "created_at",
        "updated_at",
    }

    food_nutrients = metadata.tables["food_nutrients"]
    foreign_keys = list(food_nutrients.foreign_key_constraints)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].ondelete == "CASCADE"
    assert [element.target_fullname for element in foreign_keys[0].elements] == [
        "foods.id",
    ]
    assert any(
        isinstance(constraint, sa.UniqueConstraint)
        and constraint.name == "uq_food_nutrients_food_id"
        for constraint in food_nutrients.constraints
    )

    for column_name in (
        "reference_quantity",
        "calories_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "fiber_g",
    ):
        column = food_nutrients.c[column_name]
        assert isinstance(column.type, sa.Numeric)
        assert (column.type.precision, column.type.scale) == (10, 3)

    constraint_names = {
        constraint.name
        for table in created_tables
        for constraint in table.constraints
    }
    assert {
        "ck_foods_default_serving_quantity_positive",
        "food_category",
        "food_default_serving_unit",
        "uq_food_nutrients_food_id",
        "nutrient_reference_unit",
        "ck_food_nutrients_reference_quantity_positive",
        "ck_food_nutrients_calories_kcal_non_negative",
        "ck_food_nutrients_protein_g_non_negative",
        "ck_food_nutrients_carbohydrate_g_non_negative",
        "ck_food_nutrients_fat_g_non_negative",
        "ck_food_nutrients_fiber_g_non_negative",
    }.issubset(constraint_names)


def test_food_catalog_migration_downgrade_uses_dependency_order(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0008_create_food_catalog.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_food_catalog_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert dropped_tables == ["food_nutrients", "foods"]


def test_meal_item_food_migration_only_alters_meal_items(monkeypatch) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0009_link_meal_items_to_foods.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_meal_item_food_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    operations = []
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda *args, **kwargs: operations.append(("add_column", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "create_foreign_key",
        lambda *args, **kwargs: operations.append(
            ("create_foreign_key", args, kwargs)
        ),
    )

    module.upgrade()

    assert len(operations) == 2
    operation, args, kwargs = operations[0]
    assert operation == "add_column"
    assert args[0] == "meal_items"
    column = args[1]
    assert column.name == "food_id"
    assert isinstance(column.type, postgresql.UUID)
    assert column.type.as_uuid is True
    assert column.nullable is True
    assert kwargs == {}

    assert operations[1] == (
        "create_foreign_key",
        (
            "fk_meal_items_food_id_foods",
            "meal_items",
            "foods",
            ["food_id"],
            ["id"],
        ),
        {"ondelete": "RESTRICT"},
    )


def test_meal_item_food_migration_downgrade_removes_fk_then_column(
    monkeypatch,
) -> None:
    migration_path = ALEMBIC_ROOT / "versions" / "0009_link_meal_items_to_foods.py"
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage3_meal_item_food_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    operations = []
    monkeypatch.setattr(
        module.op,
        "drop_constraint",
        lambda *args, **kwargs: operations.append(
            ("drop_constraint", args, kwargs)
        ),
    )
    monkeypatch.setattr(
        module.op,
        "drop_column",
        lambda *args, **kwargs: operations.append(("drop_column", args, kwargs)),
    )

    module.downgrade()

    assert operations == [
        (
            "drop_constraint",
            ("fk_meal_items_food_id_foods", "meal_items"),
            {"type_": "foreignkey"},
        ),
        ("drop_column", ("meal_items", "food_id"), {}),
    ]


def test_meal_item_sort_order_migration_is_next_0010_revision() -> None:
    migration_path = (
        ALEMBIC_ROOT / "versions" / "0010_add_meal_item_sort_order.py"
    )
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage4_meal_item_sort_order_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "0010_add_meal_item_sort_order"
    assert module.down_revision == "0009_link_meal_items_to_foods"
    assert module.branch_labels is None
    assert module.depends_on is None


def test_meal_item_sort_order_migration_adds_only_column_and_check(
    monkeypatch,
) -> None:
    migration_path = (
        ALEMBIC_ROOT / "versions" / "0010_add_meal_item_sort_order.py"
    )
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage4_meal_item_sort_order_migration_upgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    operations = []
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda *args, **kwargs: operations.append(("add_column", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "create_check_constraint",
        lambda *args, **kwargs: operations.append(
            ("create_check_constraint", args, kwargs)
        ),
    )
    monkeypatch.setattr(
        module.op,
        "create_unique_constraint",
        lambda *args, **kwargs: operations.append(
            ("create_unique_constraint", args, kwargs)
        ),
    )

    module.upgrade()

    assert len(operations) == 2
    operation, args, kwargs = operations[0]
    assert operation == "add_column"
    assert args[0] == "meal_items"
    column = args[1]
    assert column.name == "sort_order"
    assert isinstance(column.type, sa.Integer)
    assert column.nullable is False
    assert column.server_default is not None
    assert str(column.server_default.arg) == "0"
    assert kwargs == {}
    assert operations[1] == (
        "create_check_constraint",
        (
            "ck_meal_items_sort_order_non_negative",
            "meal_items",
            "sort_order >= 0",
        ),
        {},
    )


def test_meal_item_sort_order_migration_downgrade_removes_check_then_column(
    monkeypatch,
) -> None:
    migration_path = (
        ALEMBIC_ROOT / "versions" / "0010_add_meal_item_sort_order.py"
    )
    assert migration_path.is_file()

    spec = importlib.util.spec_from_file_location(
        "stage4_meal_item_sort_order_migration_downgrade",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    operations = []
    monkeypatch.setattr(
        module.op,
        "drop_constraint",
        lambda *args, **kwargs: operations.append(
            ("drop_constraint", args, kwargs)
        ),
    )
    monkeypatch.setattr(
        module.op,
        "drop_column",
        lambda *args, **kwargs: operations.append(("drop_column", args, kwargs)),
    )

    module.downgrade()

    assert operations == [
        (
            "drop_constraint",
            ("ck_meal_items_sort_order_non_negative", "meal_items"),
            {"type_": "check"},
        ),
        ("drop_column", ("meal_items", "sort_order"), {}),
    ]
