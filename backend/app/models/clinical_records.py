import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

# Register related one-to-one mappers before clinical relationships configure.
from app.models import client_details as _client_details
from app.models.base import Base
from app.models.enums import (
    AllergySeverity,
    MedicalConditionStatus,
    MedicationStatus,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.profiles import ClientProfile


def _normalize_record_name(value: str) -> str:
    return value.strip().lower()


# Default object repr intentionally avoids exposing clinical record contents.
class ClientAllergy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_allergies"
    __table_args__ = (
        UniqueConstraint(
            "client_profile_id",
            "allergen_name",
            name="uq_client_allergies_client_profile_id_allergen_name",
        ),
        CheckConstraint(
            "allergen_name = lower(btrim(allergen_name))",
            name="ck_client_allergies_allergen_name_normalized",
        ),
    )

    client_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "client_profiles.id",
            name="fk_client_allergies_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    allergen_name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[AllergySeverity] = mapped_column(
        Enum(
            AllergySeverity,
            name="allergy_severity",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    client_profile: Mapped[ClientProfile] = relationship(
        back_populates="allergies",
    )

    @validates("allergen_name")
    def normalize_allergen_name(self, key: str, value: str) -> str:
        return _normalize_record_name(value)


class ClientMedicalCondition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_medical_conditions"

    client_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "client_profiles.id",
            name="fk_client_medical_conditions_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MedicalConditionStatus] = mapped_column(
        Enum(
            MedicalConditionStatus,
            name="medical_condition_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    client_profile: Mapped[ClientProfile] = relationship(
        back_populates="medical_conditions",
    )

    @validates("condition_name")
    def normalize_condition_name(self, key: str, value: str) -> str:
        return _normalize_record_name(value)


class ClientMedication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_medications"

    client_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "client_profiles.id",
            name="fk_client_medications_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MedicationStatus] = mapped_column(
        Enum(
            MedicationStatus,
            name="medication_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    client_profile: Mapped[ClientProfile] = relationship(
        back_populates="medications",
    )

    @validates("medication_name")
    def normalize_medication_name(self, key: str, value: str) -> str:
        return _normalize_record_name(value)
