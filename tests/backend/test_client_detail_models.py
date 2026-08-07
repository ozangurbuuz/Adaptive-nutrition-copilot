import subprocess
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID


def _unique_client_profile_constraint(model):
    constraints = [
        constraint
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["client_profile_id"]
    ]
    assert len(constraints) == 1
    return constraints[0]


def test_client_detail_table_names_columns_and_mixins() -> None:
    from app.models.client_details import ClientHealthProfile, ClientPreferences
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    assert ClientHealthProfile.__tablename__ == "client_health_profiles"
    assert ClientPreferences.__tablename__ == "client_preferences"

    for model in (ClientHealthProfile, ClientPreferences):
        assert issubclass(model, UUIDPrimaryKeyMixin)
        assert issubclass(model, TimestampMixin)
        assert isinstance(model.__table__.c.id.type, UUID)
        assert isinstance(model.__table__.c.created_at.type, DateTime)
        assert isinstance(model.__table__.c.updated_at.type, DateTime)


def test_client_profile_foreign_keys_are_required_unique_and_cascading() -> None:
    from app.models.client_details import ClientHealthProfile, ClientPreferences

    for model, unique_name, foreign_key_name in (
        (
            ClientHealthProfile,
            "uq_client_health_profiles_client_profile_id",
            "fk_client_health_profiles_client_profile_id_client_profiles",
        ),
        (
            ClientPreferences,
            "uq_client_preferences_client_profile_id",
            "fk_client_preferences_client_profile_id_client_profiles",
        ),
    ):
        client_profile_id = model.__table__.c.client_profile_id
        foreign_keys = list(client_profile_id.foreign_keys)

        assert isinstance(client_profile_id.type, UUID)
        assert client_profile_id.nullable is False
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == "client_profiles.id"
        assert foreign_keys[0].ondelete == "CASCADE"
        assert foreign_keys[0].constraint.name == foreign_key_name
        assert _unique_client_profile_constraint(model).name == unique_name


def test_client_profile_detail_relationships_are_bidirectional_one_to_one() -> None:
    from app.models.client_details import ClientHealthProfile, ClientPreferences
    from app.models.profiles import ClientProfile

    for client_attribute, detail_model in (
        ("health_profile", ClientHealthProfile),
        ("preferences", ClientPreferences),
    ):
        client_relationship = ClientProfile.__mapper__.relationships[client_attribute]
        detail_relationship = detail_model.__mapper__.relationships["client_profile"]

        assert client_relationship.mapper.class_ is detail_model
        assert client_relationship.uselist is False
        assert client_relationship.back_populates == "client_profile"
        assert "delete-orphan" in client_relationship.cascade
        assert client_relationship.passive_deletes is True
        assert detail_relationship.mapper.class_ is ClientProfile
        assert detail_relationship.back_populates == client_attribute
        assert detail_relationship.uselist is False


def test_health_fields_use_date_decimal_numeric_and_positive_constraints() -> None:
    from app.models.client_details import ClientHealthProfile

    table = ClientHealthProfile.__table__
    assert isinstance(table.c.date_of_birth.type, Date)
    assert table.c.date_of_birth.nullable is True
    assert isinstance(table.c.height_cm.type, Numeric)
    assert (table.c.height_cm.type.precision, table.c.height_cm.type.scale) == (5, 2)
    assert table.c.height_cm.nullable is True
    assert isinstance(table.c.weight_kg.type, Numeric)
    assert (table.c.weight_kg.type.precision, table.c.weight_kg.type.scale) == (6, 2)
    assert table.c.weight_kg.nullable is True

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_names == {
        "ck_client_health_profiles_height_cm_positive",
        "ck_client_health_profiles_weight_kg_positive",
        "client_biological_sex",
    }

    health_profile = ClientHealthProfile(
        date_of_birth=date(1990, 1, 1),
        height_cm=Decimal("172.50"),
        weight_kg=Decimal("68.25"),
    )
    assert health_profile.height_cm == Decimal("172.50")
    assert health_profile.weight_kg == Decimal("68.25")
    assert "172.50" not in repr(health_profile)
    assert "68.25" not in repr(health_profile)


def test_optional_enums_use_shared_domain_definitions() -> None:
    from app.models.client_details import ClientHealthProfile, ClientPreferences
    from app.models.enums import BiologicalSex, DietaryPattern

    biological_sex = ClientHealthProfile.__table__.c.biological_sex
    dietary_pattern = ClientPreferences.__table__.c.dietary_pattern

    assert isinstance(biological_sex.type, Enum)
    assert biological_sex.type.enum_class is BiologicalSex
    assert biological_sex.type.enums == ["FEMALE", "MALE", "INTERSEX"]
    assert biological_sex.type.native_enum is False
    assert biological_sex.type.create_constraint is True
    assert biological_sex.nullable is True

    assert isinstance(dietary_pattern.type, Enum)
    assert dietary_pattern.type.enum_class is DietaryPattern
    assert dietary_pattern.type.enums == ["OMNIVORE", "VEGETARIAN", "VEGAN"]
    assert dietary_pattern.type.native_enum is False
    assert dietary_pattern.type.create_constraint is True
    assert dietary_pattern.nullable is True


def test_client_models_contain_no_forbidden_or_denormalized_fields() -> None:
    from app.models.client_details import ClientHealthProfile, ClientPreferences
    from app.models.profiles import ClientProfile

    assert set(ClientProfile.__table__.columns.keys()) == {
        "id",
        "user_id",
        "display_name",
        "created_at",
        "updated_at",
    }
    assert set(ClientHealthProfile.__table__.columns.keys()) == {
        "id",
        "client_profile_id",
        "date_of_birth",
        "biological_sex",
        "height_cm",
        "weight_kg",
        "created_at",
        "updated_at",
    }
    assert set(ClientPreferences.__table__.columns.keys()) == {
        "id",
        "client_profile_id",
        "dietary_pattern",
        "created_at",
        "updated_at",
    }


def test_client_detail_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Client detail model import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
from app.models.client_details import ClientHealthProfile, ClientPreferences
from app.models.clinical_records import (
    ClientAllergy,
    ClientMedicalCondition,
    ClientMedication,
)

assert set(Base.metadata.tables) == {
    "users",
    "dietitian_profiles",
    "client_profiles",
    "client_health_profiles",
    "client_preferences",
    "client_allergies",
    "client_medical_conditions",
    "client_medications",
}
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
