import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import BiologicalSex, DietaryPattern
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.profiles import ClientProfile


# Keep sensitive measurements out of an application-specific repr/log format.
class ClientHealthProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_health_profiles"
    __table_args__ = (
        UniqueConstraint(
            "client_profile_id",
            name="uq_client_health_profiles_client_profile_id",
        ),
        # Basic positivity belongs in the schema; plausible ranges need domain context.
        CheckConstraint(
            "height_cm IS NULL OR height_cm > 0",
            name="ck_client_health_profiles_height_cm_positive",
        ),
        CheckConstraint(
            "weight_kg IS NULL OR weight_kg > 0",
            name="ck_client_health_profiles_weight_kg_positive",
        ),
    )

    client_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "client_profiles.id",
            name="fk_client_health_profiles_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    biological_sex: Mapped[BiologicalSex | None] = mapped_column(
        Enum(
            BiologicalSex,
            name="client_biological_sex",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    height_cm: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    client_profile: Mapped[ClientProfile] = relationship(
        back_populates="health_profile",
    )


class ClientPreferences(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_preferences"
    __table_args__ = (
        UniqueConstraint(
            "client_profile_id",
            name="uq_client_preferences_client_profile_id",
        ),
    )

    client_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "client_profiles.id",
            name="fk_client_preferences_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    dietary_pattern: Mapped[DietaryPattern | None] = mapped_column(
        Enum(
            DietaryPattern,
            name="client_dietary_pattern",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    client_profile: Mapped[ClientProfile] = relationship(
        back_populates="preferences",
    )
