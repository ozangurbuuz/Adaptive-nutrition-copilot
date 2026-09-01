import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_ROOT = PROJECT_ROOT / "backend" / "alembic"
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"
MIGRATION_PATH = ALEMBIC_ROOT / "versions" / "0013_create_food_portions.py"


def _migration():
    assert MIGRATION_PATH.is_file(), "0013 food portion migration is missing"
    spec = importlib.util.spec_from_file_location(
        "stage5a3_food_portions",
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
    indexes = []

    def capture_create_table(name, *elements, **kwargs):
        table = sa.Table(name, metadata, *elements, **kwargs)
        created_tables.append(table)
        return table

    monkeypatch.setattr(module.op, "create_table", capture_create_table)
    monkeypatch.setattr(
        module.op,
        "create_index",
        lambda *args, **kwargs: indexes.append((args, kwargs)),
    )
    module.upgrade()
    return module, created_tables, indexes


def test_food_portion_migration_revision_and_length() -> None:
    module = _migration()
    assert module.revision == "0013_food_portions"
    assert len(module.revision) <= 32
    assert module.down_revision == "0012_food_nutrient_values"
    assert module.branch_labels is None
    assert module.depends_on is None


def test_alembic_head_is_food_portion_revision() -> None:
    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0013_food_portions"]


def test_migration_creates_only_food_portions_table(monkeypatch) -> None:
    _, created_tables, indexes = _capture_upgrade(monkeypatch)
    assert [table.name for table in created_tables] == ["food_portions"]
    assert indexes == [
        (
            (
                "ix_food_portions_food_source_record_id",
                "food_portions",
                ["food_source_record_id"],
            ),
            {"unique": False},
        )
    ]


def test_migration_columns_match_food_portion_contract(monkeypatch) -> None:
    _, created_tables, _ = _capture_upgrade(monkeypatch)
    table = created_tables[0]
    assert set(table.columns.keys()) == {
        "id",
        "food_source_record_id",
        "source_portion_id",
        "amount",
        "measure_code",
        "measure_name",
        "modifier",
        "portion_description",
        "gram_weight",
        "sequence_number",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, postgresql.UUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.id.primary_key is True
    assert table.c.id.server_default is None
    assert isinstance(table.c.food_source_record_id.type, postgresql.UUID)
    assert table.c.food_source_record_id.nullable is False

    for name, length, nullable in (
        ("source_portion_id", 100, True),
        ("measure_code", 50, True),
        ("measure_name", 100, True),
        ("modifier", 100, True),
        ("portion_description", 255, False),
    ):
        assert isinstance(table.c[name].type, sa.String)
        assert not isinstance(table.c[name].type, sa.Enum)
        assert table.c[name].type.length == length
        assert table.c[name].nullable is nullable
        assert table.c[name].server_default is None

    for name, nullable in (("amount", False), ("gram_weight", True)):
        column = table.c[name]
        assert isinstance(column.type, sa.Numeric)
        assert (column.type.precision, column.type.scale) == (14, 6)
        assert column.nullable is nullable
        assert column.server_default is None

    assert isinstance(table.c.sequence_number.type, sa.Integer)
    assert table.c.sequence_number.nullable is True
    for name in ("created_at", "updated_at"):
        assert isinstance(table.c[name].type, sa.DateTime)
        assert table.c[name].type.timezone is True
        assert table.c[name].nullable is False
        assert table.c[name].server_default is None


def test_migration_constraints_and_foreign_key_match_contract(monkeypatch) -> None:
    _, created_tables, _ = _capture_upgrade(monkeypatch)
    table = created_tables[0]
    constraints = {constraint.name: constraint for constraint in table.constraints}
    assert {
        "pk_food_portions",
        "uq_food_portions_source_record_source_portion_id",
        "uq_food_portions_source_record_sequence_number",
        "ck_food_portions_source_portion_id_nonblank",
        "ck_food_portions_amount_positive",
        "ck_food_portions_measure_code_canonical",
        "ck_food_portions_measure_name_nonblank",
        "ck_food_portions_modifier_nonblank",
        "ck_food_portions_description_nonblank",
        "ck_food_portions_gram_weight_positive",
        "ck_food_portions_sequence_number_positive",
        "fk_food_portions_food_source_record_id_food_source_records",
    }.issubset(constraints)

    source_id_unique = constraints[
        "uq_food_portions_source_record_source_portion_id"
    ]
    assert [column.name for column in source_id_unique.columns] == [
        "food_source_record_id",
        "source_portion_id",
    ]
    sequence_unique = constraints[
        "uq_food_portions_source_record_sequence_number"
    ]
    assert [column.name for column in sequence_unique.columns] == [
        "food_source_record_id",
        "sequence_number",
    ]
    assert not any(
        isinstance(constraint, sa.UniqueConstraint)
        and [column.name for column in constraint.columns]
        == ["food_source_record_id", "amount", "measure_code", "modifier"]
        for constraint in table.constraints
    )

    foreign_keys = list(table.foreign_key_constraints)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].name == (
        "fk_food_portions_food_source_record_id_food_source_records"
    )
    assert foreign_keys[0].ondelete == "CASCADE"
    assert [element.target_fullname for element in foreign_keys[0].elements] == [
        "food_source_records.id"
    ]


def test_migration_uses_no_measure_enum(monkeypatch) -> None:
    _, created_tables, _ = _capture_upgrade(monkeypatch)
    assert not any(
        isinstance(column.type, sa.Enum)
        for column in created_tables[0].columns
    )


def test_migration_does_not_mutate_seed_or_backfill(monkeypatch) -> None:
    module = _migration()

    def fail_forbidden_operation(*args, **kwargs):
        raise AssertionError("0013 must only create the food_portions table")

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
        monkeypatch.setattr(
            module.op,
            operation_name,
            fail_forbidden_operation,
        )
    module.upgrade()


def test_migration_downgrade_removes_index_then_table(monkeypatch) -> None:
    module = _migration()
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
        (
            "drop_index",
            ("ix_food_portions_food_source_record_id",),
            {"table_name": "food_portions"},
        ),
        ("drop_table", ("food_portions",), {}),
    ]
