import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_ROOT = PROJECT_ROOT / "backend" / "alembic"
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"
MIGRATION_PATH = ALEMBIC_ROOT / "versions" / "0012_create_food_nutrient_values.py"


def _migration():
    assert MIGRATION_PATH.is_file(), "0012 nutrient value migration is missing"
    spec = importlib.util.spec_from_file_location(
        "stage5a2_food_nutrient_values",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_upgrade(monkeypatch):
    module = _migration()
    metadata = sa.MetaData()
    sa.Table(
        "food_source_records",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    created_tables = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    module.upgrade()
    return module, created_tables


def test_nutrient_value_migration_revision_and_length() -> None:
    module = _migration()
    assert module.revision == "0012_food_nutrient_values"
    assert len(module.revision) <= 32
    assert module.down_revision == "0011_food_dataset_provenance"
    assert module.branch_labels is None
    assert module.depends_on is None


def test_nutrient_value_revision_remains_below_food_portion_head() -> None:
    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0013_food_portions"]
    revision = script.get_revision("0012_food_nutrient_values")
    assert revision is not None
    assert revision.down_revision == "0011_food_dataset_provenance"


def test_migration_creates_only_two_tables_in_dependency_order(monkeypatch) -> None:
    _, created_tables = _capture_upgrade(monkeypatch)
    assert [table.name for table in created_tables] == [
        "nutrient_definitions",
        "food_nutrient_values",
    ]


def test_migration_columns_match_contract(monkeypatch) -> None:
    _, created_tables = _capture_upgrade(monkeypatch)
    tables = {table.name: table for table in created_tables}
    definition = tables["nutrient_definitions"]
    value = tables["food_nutrient_values"]

    assert set(definition.columns.keys()) == {
        "id",
        "code",
        "name_en",
        "unit",
        "created_at",
        "updated_at",
    }
    assert isinstance(definition.c.id.type, postgresql.UUID)
    assert definition.c.code.type.length == 50
    assert definition.c.name_en.type.length == 100
    assert definition.c.unit.nullable is False
    assert definition.c.created_at.type.timezone is True
    assert definition.c.updated_at.type.timezone is True

    assert set(value.columns.keys()) == {
        "id",
        "food_source_record_id",
        "nutrient_definition_id",
        "amount_per_100g",
        "created_at",
        "updated_at",
    }
    amount = value.c.amount_per_100g
    assert isinstance(amount.type, sa.Numeric)
    assert amount.type.precision == 14
    assert amount.type.scale == 6
    assert amount.nullable is True


def test_migration_constraints_and_foreign_keys_match_contract(monkeypatch) -> None:
    _, created_tables = _capture_upgrade(monkeypatch)
    tables = {table.name: table for table in created_tables}
    names = {
        constraint.name
        for table in created_tables
        for constraint in table.constraints
    }
    assert {
        "pk_nutrient_definitions",
        "uq_nutrient_definitions_code",
        "ck_nutrient_definitions_code_nonblank",
        "ck_nutrient_definitions_code_canonical",
        "ck_nutrient_definitions_name_en_nonblank",
        "pk_food_nutrient_values",
        "uq_food_nutrient_values_source_record_nutrient",
        "ck_food_nutrient_values_amount_non_negative",
    }.issubset(names)

    foreign_keys = {
        tuple(constraint.column_keys): constraint
        for constraint in tables["food_nutrient_values"].foreign_key_constraints
    }
    assert foreign_keys[("food_source_record_id",)].ondelete == "CASCADE"
    assert foreign_keys[("nutrient_definition_id",)].ondelete == "RESTRICT"


def test_migration_uses_non_native_nutrient_unit_enum(monkeypatch) -> None:
    _, created_tables = _capture_upgrade(monkeypatch)
    definition = {table.name: table for table in created_tables}[
        "nutrient_definitions"
    ]
    unit_type = definition.c.unit.type
    assert isinstance(unit_type, sa.Enum)
    assert unit_type.native_enum is False
    assert unit_type.create_constraint is True
    assert unit_type.enums == ["KCAL", "GRAM", "MILLIGRAM", "MICROGRAM"]


def test_migration_does_not_mutate_or_seed_existing_tables(monkeypatch) -> None:
    module = _migration()

    def fail_existing_mutation(*args, **kwargs):
        raise AssertionError("0012 must only create nutrient tables")

    monkeypatch.setattr(module.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    for operation_name in (
        "add_column",
        "alter_column",
        "drop_column",
        "create_foreign_key",
        "drop_constraint",
        "bulk_insert",
        "execute",
    ):
        monkeypatch.setattr(module.op, operation_name, fail_existing_mutation)

    module.upgrade()


def test_migration_downgrade_uses_reverse_dependency_order(monkeypatch) -> None:
    module = _migration()
    dropped_tables = []
    monkeypatch.setattr(module.op, "drop_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()
    assert dropped_tables == ["food_nutrient_values", "nutrient_definitions"]
