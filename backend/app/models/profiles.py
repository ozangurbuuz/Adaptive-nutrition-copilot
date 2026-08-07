import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User

if TYPE_CHECKING:
    from app.models.client_details import ClientHealthProfile, ClientPreferences
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )
    from app.models.nutrition_plan import NutritionPlan


class DietitianProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dietitian_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_dietitian_profiles_user_id",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_dietitian_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    professional_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    license_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    user: Mapped[User] = relationship(back_populates="dietitian_profile")
    # Plans are retained unless their RESTRICT foreign key is deliberately resolved.
    nutrition_plans: Mapped[list["NutritionPlan"]] = relationship(
        back_populates="dietitian_profile",
        passive_deletes="all",
    )


class ClientProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_client_profiles_user_id",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_client_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user: Mapped[User] = relationship(back_populates="client_profile")
    # ORM orphan cleanup complements the database-level ON DELETE CASCADE.
    health_profile: Mapped["ClientHealthProfile | None"] = relationship(
        back_populates="client_profile",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    preferences: Mapped["ClientPreferences | None"] = relationship(
        back_populates="client_profile",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    allergies: Mapped[list["ClientAllergy"]] = relationship(
        back_populates="client_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    medical_conditions: Mapped[list["ClientMedicalCondition"]] = relationship(
        back_populates="client_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    medications: Mapped[list["ClientMedication"]] = relationship(
        back_populates="client_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    # Plans are retained unless their RESTRICT foreign key is deliberately resolved.
    nutrition_plans: Mapped[list["NutritionPlan"]] = relationship(
        back_populates="client_profile",
        passive_deletes="all",
    )
