import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_ROOT = PROJECT_ROOT / "backend" / "alembic"
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"
MIGRATION_PATH = (
    ALEMBIC_ROOT / "versions" / "0011_create_food_dataset_provenance.py"
)


# Eksik migration dosyasını import/collection error yerine açık RED failure olarak gösterir.
def _migration():
    assert MIGRATION_PATH.is_file(), "0011 provenance migration is missing"
    spec = importlib.util.spec_from_file_location(
        "stage5a1_food_dataset_provenance",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Migration upgrade'ını gerçek DB olmadan SQLAlchemy metadata üzerinde yakalar.
def _capture_upgrade(monkeypatch):
    module = _migration()
    metadata = sa.MetaData()
    sa.Table(
        "foods",
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


# Yeni migration'ın mevcut 0010 head'inin doğrudan devamı olmasını zorunlu kılar.
def test_provenance_migration_is_revision_0011() -> None:
    module = _migration()
    assert module.revision == "0011_food_dataset_provenance"
    assert module.down_revision == "0010_add_meal_item_sort_order"
    assert module.branch_labels is None
    assert module.depends_on is None


# Alembic graph head'inin yeni revision'a taşındığını doğrular.
def test_alembic_head_is_provenance_revision() -> None:
    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0011_food_dataset_provenance"]


# Upgrade'ın yalnız iki yeni tabloyu doğru bağımlılık sırasıyla oluşturmasını sınar.
def test_migration_creates_only_provenance_tables_in_dependency_order(
    monkeypatch,
) -> None:
    _, created_tables, indexes = _capture_upgrade(monkeypatch)
    assert [table.name for table in created_tables] == [
        "dataset_releases",
        "food_source_records",
    ]
    assert {
        args[0]
        for args, kwargs in indexes
    } == {
        "ix_food_source_records_food_id",
        "ix_food_source_records_source_food_id",
    }


# Bu dilimde upgrade'in var olan tablolari alter etmesine izin verilmedigini dogrular.
def test_migration_does_not_mutate_existing_tables(monkeypatch) -> None:
    module = _migration()

    def fail_existing_table_mutation(*args, **kwargs):
        raise AssertionError("Migration must only create provenance tables")

    monkeypatch.setattr(module.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    for operation_name in (
        "add_column",
        "alter_column",
        "drop_column",
        "create_foreign_key",
        "drop_constraint",
        "execute",
    ):
        monkeypatch.setattr(
            module.op,
            operation_name,
            fail_existing_table_mutation,
        )

    module.upgrade()


# Migration kolonlarının model kontratındaki tip, uzunluk ve nullability ile eşleşmesini sınar.
def test_migration_columns_match_provenance_contract(monkeypatch) -> None:
    _, created_tables, _ = _capture_upgrade(monkeypatch)
    tables = {table.name: table for table in created_tables}
    release = tables["dataset_releases"]
    source_record = tables["food_source_records"]

    assert set(release.columns.keys()) == {
        "id",
        "source",
        "release_version",
        "downloaded_at",
        "imported_at",
        "checksum_sha256",
        "license_reference",
        "created_at",
        "updated_at",
    }
    assert isinstance(release.c.id.type, postgresql.UUID)
    assert release.c.id.type.as_uuid is True
    assert release.c.id.primary_key is True
    assert release.c.id.server_default is None
    for name, length, nullable in (
        ("source", 50, False),
        ("release_version", 100, False),
        ("checksum_sha256", 64, False),
        ("license_reference", 500, False),
    ):
        assert release.c[name].type.length == length
        assert release.c[name].nullable is nullable
        assert release.c[name].server_default is None
    assert release.c.downloaded_at.type.timezone is True
    assert release.c.downloaded_at.nullable is False
    assert release.c.imported_at.type.timezone is True
    assert release.c.imported_at.nullable is True
    assert release.c.created_at.type.timezone is True
    assert release.c.created_at.nullable is False
    assert release.c.updated_at.type.timezone is True
    assert release.c.updated_at.nullable is False

    assert set(source_record.columns.keys()) == {
        "id",
        "food_id",
        "dataset_release_id",
        "source_food_id",
        "canonical_name",
        "preparation_state",
        "created_at",
        "updated_at",
    }
    assert source_record.c.id.primary_key is True
    assert source_record.c.id.server_default is None
    assert source_record.c.food_id.nullable is False
    assert source_record.c.dataset_release_id.nullable is False
    for name, length, nullable in (
        ("source_food_id", 100, False),
        ("canonical_name", 255, False),
        ("preparation_state", 100, True),
    ):
        assert source_record.c[name].type.length == length
        assert source_record.c[name].nullable is nullable
        assert source_record.c[name].server_default is None
    assert source_record.c.created_at.type.timezone is True
    assert source_record.c.created_at.nullable is False
    assert source_record.c.updated_at.type.timezone is True
    assert source_record.c.updated_at.nullable is False


# Unique, check ve foreign key isimlerinin migration metadata'sında eksiksiz olmasını bekler.
def test_migration_constraints_match_model_contract(monkeypatch) -> None:
    _, created_tables, _ = _capture_upgrade(monkeypatch)
    tables = {table.name: table for table in created_tables}
    constraint_names = {
        constraint.name
        for table in created_tables
        for constraint in table.constraints
    }
    assert {
        "pk_dataset_releases",
        "uq_dataset_releases_source_release_version",
        "uq_dataset_releases_source_checksum_sha256",
        "ck_dataset_releases_source_nonblank",
        "ck_dataset_releases_release_version_nonblank",
        "ck_dataset_releases_checksum_sha256_length",
        "ck_dataset_releases_license_reference_nonblank",
        "pk_food_source_records",
        "uq_food_source_records_dataset_release_id_source_food_id",
        "ck_food_source_records_source_food_id_nonblank",
        "ck_food_source_records_canonical_name_nonblank",
        "ck_food_source_records_preparation_state_nonblank",
        "fk_food_source_records_food_id_foods",
        "fk_food_source_records_dataset_release_id_dataset_releases",
    }.issubset(constraint_names)

    foreign_keys = {
        constraint.name: constraint
        for constraint in tables["food_source_records"].foreign_key_constraints
    }
    assert foreign_keys["fk_food_source_records_food_id_foods"].ondelete == "CASCADE"
    assert (
        foreign_keys[
            "fk_food_source_records_dataset_release_id_dataset_releases"
        ].ondelete
        == "RESTRICT"
    )


# Downgrade'ın child tabloyu parent tablodan önce kaldırmasını doğrular.
def test_migration_downgrade_uses_reverse_dependency_order(monkeypatch) -> None:
    module = _migration()
    dropped_indexes = []
    dropped_tables = []
    monkeypatch.setattr(
        module.op,
        "drop_index",
        lambda *args, **kwargs: dropped_indexes.append((args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "drop_table",
        lambda table_name: dropped_tables.append(table_name),
    )

    module.downgrade()

    assert {args[0] for args, kwargs in dropped_indexes} == {
        "ix_food_source_records_food_id",
        "ix_food_source_records_source_food_id",
    }
    assert dropped_tables == ["food_source_records", "dataset_releases"]
