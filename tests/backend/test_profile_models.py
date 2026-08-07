import subprocess
import sys

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID


def _unique_user_constraint(model):
    constraints = [
        constraint
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["user_id"]
    ]
    assert len(constraints) == 1
    return constraints[0]


def test_profile_table_names_columns_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
    from app.models.profiles import ClientProfile, DietitianProfile

    assert DietitianProfile.__tablename__ == "dietitian_profiles"
    assert ClientProfile.__tablename__ == "client_profiles"
    assert issubclass(DietitianProfile, UUIDPrimaryKeyMixin)
    assert issubclass(DietitianProfile, TimestampMixin)
    assert issubclass(ClientProfile, UUIDPrimaryKeyMixin)
    assert issubclass(ClientProfile, TimestampMixin)

    for model in (DietitianProfile, ClientProfile):
        assert isinstance(model.__table__.c.id.type, UUID)
        assert isinstance(model.__table__.c.created_at.type, DateTime)
        assert isinstance(model.__table__.c.updated_at.type, DateTime)


def test_profile_user_foreign_keys_are_required_unique_and_cascading() -> None:
    from app.models.profiles import ClientProfile, DietitianProfile

    for model, constraint_name, foreign_key_name in (
        (
            DietitianProfile,
            "uq_dietitian_profiles_user_id",
            "fk_dietitian_profiles_user_id_users",
        ),
        (
            ClientProfile,
            "uq_client_profiles_user_id",
            "fk_client_profiles_user_id_users",
        ),
    ):
        user_id = model.__table__.c.user_id
        foreign_keys = list(user_id.foreign_keys)

        assert isinstance(user_id.type, UUID)
        assert user_id.nullable is False
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == "users.id"
        assert foreign_keys[0].ondelete == "CASCADE"
        assert foreign_keys[0].constraint.name == foreign_key_name
        assert _unique_user_constraint(model).name == constraint_name


def test_user_and_profile_relationships_are_bidirectional_one_to_one() -> None:
    from app.models.profiles import ClientProfile, DietitianProfile
    from app.models.user import User

    for user_attribute, profile_model in (
        ("dietitian_profile", DietitianProfile),
        ("client_profile", ClientProfile),
    ):
        user_relationship = User.__mapper__.relationships[user_attribute]
        profile_relationship = profile_model.__mapper__.relationships["user"]

        assert user_relationship.mapper.class_ is profile_model
        assert user_relationship.uselist is False
        assert user_relationship.back_populates == "user"
        assert "delete-orphan" in user_relationship.cascade
        assert user_relationship.passive_deletes is True
        assert profile_relationship.mapper.class_ is User
        assert profile_relationship.back_populates == user_attribute
        assert profile_relationship.uselist is False


def test_profile_display_fields_have_explicit_lengths_and_nullability() -> None:
    from app.models.profiles import ClientProfile, DietitianProfile

    assert isinstance(DietitianProfile.__table__.c.display_name.type, String)
    assert DietitianProfile.__table__.c.display_name.type.length == 255
    assert DietitianProfile.__table__.c.display_name.nullable is False
    assert DietitianProfile.__table__.c.professional_title.type.length == 255
    assert DietitianProfile.__table__.c.professional_title.nullable is True
    assert DietitianProfile.__table__.c.license_number.type.length == 100
    assert DietitianProfile.__table__.c.license_number.nullable is True

    assert isinstance(ClientProfile.__table__.c.display_name.type, String)
    assert ClientProfile.__table__.c.display_name.type.length == 255
    assert ClientProfile.__table__.c.display_name.nullable is False


def test_client_profile_contains_no_health_or_preference_fields() -> None:
    from app.models.profiles import ClientProfile

    assert set(ClientProfile.__table__.columns.keys()) == {
        "id",
        "user_id",
        "display_name",
        "created_at",
        "updated_at",
    }


def test_profile_model_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Profile model import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
from app.models.client_details import ClientHealthProfile, ClientPreferences
from app.models.clinical_records import (
    ClientAllergy,
    ClientMedicalCondition,
    ClientMedication,
)
from app.models.profiles import ClientProfile, DietitianProfile
from app.models.user import User

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
