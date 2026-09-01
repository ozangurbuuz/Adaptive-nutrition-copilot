from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import MealItemUnit, MealType, NutritionPlanStatus


class NutritionPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_profile_id: UUID
    dietitian_profile_id: UUID
    title: Annotated[str, Field(min_length=1, max_length=255)]
    starts_on: date | None = None
    ends_on: date | None = None
    notes: Annotated[str | None, Field(max_length=1000)] = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "NutritionPlanCreate":
        if (
            self.starts_on is not None
            and self.ends_on is not None
            and self.ends_on < self.starts_on
        ):
            raise ValueError("ends_on must be on or after starts_on")
        return self


class MealItemRead(BaseModel):
    id: UUID
    food_id: UUID | None
    item_name: str
    quantity: Decimal
    unit: MealItemUnit
    sort_order: int


class MealRead(BaseModel):
    id: UUID
    meal_type: MealType
    name: str | None
    sort_order: int
    items: list[MealItemRead]


class PlanDayRead(BaseModel):
    id: UUID
    day_number: int
    label: str | None
    meals: list[MealRead]


class NutritionPlanRead(BaseModel):
    id: UUID
    client_profile_id: UUID
    dietitian_profile_id: UUID
    title: str
    status: NutritionPlanStatus
    starts_on: date | None
    ends_on: date | None
    notes: str | None
    days: list[PlanDayRead]
