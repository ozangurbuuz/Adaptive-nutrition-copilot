import subprocess
import sys

from sqlalchemy import CheckConstraint, DateTime, Enum, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID


def test_clinical_record_table_names_columns_and_mixins() -> None:
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    expected_columns = {
        ClientAllergy: {
            "id",
            "client_profile_id",
            "allergen_name",
            "severity",
            "notes",
            "created_at",
            "updated_at",
        },
        ClientMedicalCondition: {
            "id",
            "client_profile_id",
            "condition_name",
            "status",
            "notes",
            "created_at",
            "updated_at",
        },
        ClientMedication: {
            "id",
            "client_profile_id",
            "medication_name",
            "status",
            "notes",
            "created_at",
            "updated_at",
        },
    }
    assert ClientAllergy.__tablename__ == "client_allergies"
    assert ClientMedicalCondition.__tablename__ == "client_medical_conditions"
    assert ClientMedication.__tablename__ == "client_medications"

    for model, columns in expected_columns.items():
        assert issubclass(model, UUIDPrimaryKeyMixin)
        assert issubclass(model, TimestampMixin)
        assert set(model.__table__.columns.keys()) == columns
        assert isinstance(model.__table__.c.id.type, UUID)
        assert isinstance(model.__table__.c.created_at.type, DateTime)
        assert isinstance(model.__table__.c.updated_at.type, DateTime)


def test_clinical_record_foreign_keys_are_required_and_cascading() -> None:
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )

    expected_fk_names = {
        ClientAllergy: "fk_client_allergies_client_profile_id_client_profiles",
        ClientMedicalCondition: (
            "fk_client_medical_conditions_client_profile_id_client_profiles"
        ),
        ClientMedication: (
            "fk_client_medications_client_profile_id_client_profiles"
        ),
    }

    for model, foreign_key_name in expected_fk_names.items():
        client_profile_id = model.__table__.c.client_profile_id
        foreign_keys = list(client_profile_id.foreign_keys)

        assert isinstance(client_profile_id.type, UUID)
        assert client_profile_id.nullable is False
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == "client_profiles.id"
        assert foreign_keys[0].ondelete == "CASCADE"
        assert foreign_keys[0].constraint.name == foreign_key_name


def test_client_profile_relationships_are_bidirectional_one_to_many() -> None:
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )
    from app.models.profiles import ClientProfile

    for client_attribute, record_model in (
        ("allergies", ClientAllergy),
        ("medical_conditions", ClientMedicalCondition),
        ("medications", ClientMedication),
    ):
        client_relationship = ClientProfile.__mapper__.relationships[client_attribute]
        record_relationship = record_model.__mapper__.relationships["client_profile"]

        assert client_relationship.mapper.class_ is record_model
        assert client_relationship.uselist is True
        assert client_relationship.back_populates == "client_profile"
        assert "delete-orphan" in client_relationship.cascade
        assert client_relationship.passive_deletes is True
        assert record_relationship.mapper.class_ is ClientProfile
        assert record_relationship.back_populates == client_attribute
        assert record_relationship.uselist is False


def test_clinical_record_enums_are_shared_required_and_constrained() -> None:
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )
    from app.models.enums import (
        AllergySeverity,
        MedicalConditionStatus,
        MedicationStatus,
    )

    for column, enum_class, values, constraint_name in (
        (
            ClientAllergy.__table__.c.severity,
            AllergySeverity,
            ["MILD", "MODERATE", "SEVERE"],
            "allergy_severity",
        ),
        (
            ClientMedicalCondition.__table__.c.status,
            MedicalConditionStatus,
            ["ACTIVE", "RESOLVED", "UNKNOWN"],
            "medical_condition_status",
        ),
        (
            ClientMedication.__table__.c.status,
            MedicationStatus,
            ["ACTIVE", "INACTIVE"],
            "medication_status",
        ),
    ):
        assert isinstance(column.type, Enum)
        assert column.type.enum_class is enum_class
        assert column.type.enums == values
        assert column.type.native_enum is False
        assert column.type.create_constraint is True
        assert column.nullable is False
        assert any(
            isinstance(constraint, CheckConstraint)
            and constraint.name == constraint_name
            for constraint in column.table.constraints
        )


def test_record_names_and_notes_have_explicit_schema() -> None:
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )

    for name_column in (
        ClientAllergy.__table__.c.allergen_name,
        ClientMedicalCondition.__table__.c.condition_name,
        ClientMedication.__table__.c.medication_name,
    ):
        assert isinstance(name_column.type, String)
        assert name_column.type.length == 255
        assert name_column.nullable is False

    for model in (ClientAllergy, ClientMedicalCondition, ClientMedication):
        assert isinstance(model.__table__.c.notes.type, String)
        assert model.__table__.c.notes.type.length == 1000
        assert model.__table__.c.notes.nullable is True


def test_allergen_normalization_and_duplicate_constraint() -> None:
    from app.models.clinical_records import ClientAllergy
    from app.models.enums import AllergySeverity

    allergy = ClientAllergy(
        allergen_name="  Tree Nuts  ",
        severity=AllergySeverity.SEVERE,
    )
    assert allergy.allergen_name == "tree nuts"

    unique_constraints = [
        constraint
        for constraint in ClientAllergy.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == (
        "uq_client_allergies_client_profile_id_allergen_name"
    )
    assert [column.name for column in unique_constraints[0].columns] == [
        "client_profile_id",
        "allergen_name",
    ]
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_client_allergies_allergen_name_normalized"
        for constraint in ClientAllergy.__table__.constraints
    )


def test_clinical_records_use_no_json_and_do_not_expand_health_profile() -> None:
    from app.models.client_details import ClientHealthProfile
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )

    for model in (ClientAllergy, ClientMedicalCondition, ClientMedication):
        assert not any(
            isinstance(column.type, JSON)
            for column in model.__table__.columns
        )

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


def test_clinical_record_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Clinical record import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
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
