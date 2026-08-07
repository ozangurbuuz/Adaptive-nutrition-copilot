import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import clinical_records as _clinical_records  # noqa: F401
from app.models.base import Base
from app.models.enums import NutritionPlanStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.profiles import ClientProfile, DietitianProfile


class NutritionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "nutrition_plans"
    __table_args__ = (
        CheckConstraint(
            "starts_on IS NULL OR ends_on IS NULL OR ends_on >= starts_on",
            name="ck_nutrition_plans_date_range",
        ),
    )

    client_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "client_profiles.id",
            name="fk_nutrition_plans_client_profile_id_client_profiles",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    dietitian_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "dietitian_profiles.id",
            name="fk_nutrition_plans_dietitian_profile_id_dietitian_profiles",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[NutritionPlanStatus] = mapped_column(
        Enum(
            NutritionPlanStatus,
            name="nutrition_plan_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=NutritionPlanStatus.DRAFT,
        server_default=text("'DRAFT'"),
        nullable=False,
    )
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    client_profile: Mapped[ClientProfile] = relationship(
        back_populates="nutrition_plans"
    )
    dietitian_profile: Mapped[DietitianProfile] = relationship(
        back_populates="nutrition_plans"
    )
    # Plan günleri plan bütününün bağımsız yaşam döngüsü olmayan parçalarıdır.
    plan_days: Mapped[list["PlanDay"]] = relationship(
        back_populates="nutrition_plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )

    # Gelecekte kısmi benzersiz PostgreSQL indeksi danışan başına tek ACTIVE planı koruyabilir.


from app.models import plan_structure as _plan_structure  # noqa: E402, F401
