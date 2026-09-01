import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import FoodCategory, MealItemUnit, NutrientUnit


CanonicalNutrientCode = Literal[
    "ENERGY_KCAL",
    "PROTEIN",
    "TOTAL_FAT",
    "CARBOHYDRATE",
    "FIBER",
    "TOTAL_SUGARS",
    "SATURATED_FAT",
    "SODIUM",
]

CANONICAL_NUTRIENT_DEFINITIONS = (
    ("ENERGY_KCAL", "Energy", NutrientUnit.KCAL, (2048, 2047, 1008)),
    ("PROTEIN", "Protein", NutrientUnit.GRAM, (1003,)),
    ("TOTAL_FAT", "Total fat", NutrientUnit.GRAM, (1004,)),
    ("CARBOHYDRATE", "Carbohydrate", NutrientUnit.GRAM, (1005,)),
    ("FIBER", "Dietary fiber", NutrientUnit.GRAM, (1079,)),
    ("TOTAL_SUGARS", "Total sugars", NutrientUnit.GRAM, (2000,)),
    ("SATURATED_FAT", "Saturated fat", NutrientUnit.GRAM, (1258,)),
    ("SODIUM", "Sodium", NutrientUnit.MILLIGRAM, (1093,)),
)

_NUTRIENT_CONTRACT = {
    code: {
        "name_en": name_en,
        "unit": unit,
        "usda_nutrient_ids": nutrient_ids,
    }
    for code, name_en, unit, nutrient_ids in CANONICAL_NUTRIENT_DEFINITIONS
}
_PILOT_REQUIRED_NUTRIENTS = {
    "ENERGY_KCAL",
    "PROTEIN",
    "TOTAL_FAT",
    "CARBOHYDRATE",
}
_DECIMAL6_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,7})\.[0-9]{6}\Z")


def _parse_decimal6(value: object) -> Decimal:
    if not isinstance(value, str) or _DECIMAL6_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a canonical Decimal6 string")
    return Decimal(value)


def _validate_trimmed_nonblank(value: str) -> str:
    if not value or value != value.strip():
        raise ValueError("value must be nonblank and trimmed")
    return value


Decimal6 = Annotated[Decimal, BeforeValidator(_parse_decimal6)]
PositiveDecimal6 = Annotated[Decimal6, Field(gt=Decimal("0"))]
StrictPositiveInt = Annotated[int, Field(strict=True, gt=0)]
StrictNonnegativeInt = Annotated[int, Field(strict=True, ge=0)]

TrimmedText50 = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=50),
    AfterValidator(_validate_trimmed_nonblank),
]
TrimmedText100 = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=100),
    AfterValidator(_validate_trimmed_nonblank),
]
TrimmedText255 = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=255),
    AfterValidator(_validate_trimmed_nonblank),
]
TrimmedText500 = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=500),
    AfterValidator(_validate_trimmed_nonblank),
]
UnboundedTrimmedText = Annotated[
    str,
    Field(strict=True, min_length=1),
    AfterValidator(_validate_trimmed_nonblank),
]


class _StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetManifestDTO(_StrictDTO):
    source: TrimmedText50
    release_version: TrimmedText100
    downloaded_at: datetime
    license_reference: TrimmedText500
    raw_filename: Annotated[str, Field(strict=True, min_length=1, max_length=255)]
    canonical_filename: Annotated[
        str,
        Field(strict=True, min_length=1, max_length=255),
    ]
    raw_size_bytes: StrictPositiveInt
    raw_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
    canonical_sha256: Annotated[
        str,
        Field(strict=True, pattern=r"^[0-9a-f]{64}$"),
    ]
    record_count: StrictNonnegativeInt
    canonical_schema_version: UnboundedTrimmedText
    mapping_version: UnboundedTrimmedText
    generator_version: UnboundedTrimmedText

    @field_validator("downloaded_at")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("downloaded_at must be timezone-aware")
        return value

    @field_validator("raw_filename", "canonical_filename")
    @classmethod
    def validate_safe_basename(cls, value: str) -> str:
        if (
            value != value.strip()
            or not value
            or "/" in value
            or "\\" in value
            or ".." in value
        ):
            raise ValueError("filename must be a safe basename")
        return value


class CanonicalFoodDTO(_StrictDTO):
    name: TrimmedText255
    category: FoodCategory
    default_serving_quantity: PositiveDecimal6 | None = None
    default_serving_unit: MealItemUnit | None = None

    @field_validator("name")
    @classmethod
    def validate_canonical_name(cls, value: str) -> str:
        if value != value.casefold():
            raise ValueError("name must be canonical casefolded text")
        return value


class CanonicalNutrientDTO(_StrictDTO):
    source_nutrient_id: StrictPositiveInt
    canonical_code: CanonicalNutrientCode
    amount_per_100g: Decimal6 | None
    unit: NutrientUnit


class CanonicalPortionDTO(_StrictDTO):
    source_portion_id: TrimmedText100 | None = None
    amount: PositiveDecimal6
    measure_code: Annotated[
        str,
        Field(strict=True, max_length=50, pattern=r"^[A-Z][A-Z0-9_]*$"),
    ] | None = None
    measure_name: TrimmedText100 | None = None
    modifier: TrimmedText100 | None = None
    portion_description: TrimmedText255
    gram_weight: PositiveDecimal6 | None = None
    sequence_number: StrictPositiveInt | None = None

    @model_validator(mode="after")
    def validate_source_identity(self) -> "CanonicalPortionDTO":
        if self.source_portion_id is None and self.sequence_number is None:
            raise ValueError(
                "source_portion_id or sequence_number must be provided"
            )
        return self


class CanonicalFoodRecordDTO(_StrictDTO):
    source: TrimmedText50
    release_version: TrimmedText100
    source_food_id: TrimmedText100
    food: CanonicalFoodDTO
    source_description: TrimmedText255
    preparation_state: TrimmedText100 | None = None
    nutrients: list[CanonicalNutrientDTO]
    portions: list[CanonicalPortionDTO]

    @model_validator(mode="after")
    def validate_record_identities_and_mapping(self) -> "CanonicalFoodRecordDTO":
        codes: set[str] = set()
        source_nutrient_ids: set[int] = set()
        for nutrient in self.nutrients:
            if nutrient.canonical_code in codes:
                raise ValueError(
                    f"duplicate canonical_code: {nutrient.canonical_code}"
                )
            codes.add(nutrient.canonical_code)

            if nutrient.source_nutrient_id in source_nutrient_ids:
                raise ValueError(
                    f"duplicate source_nutrient_id: {nutrient.source_nutrient_id}"
                )
            source_nutrient_ids.add(nutrient.source_nutrient_id)

            contract = _NUTRIENT_CONTRACT[nutrient.canonical_code]
            if nutrient.unit is not contract["unit"]:
                raise ValueError(
                    f"unit does not match {nutrient.canonical_code}"
                )
            if nutrient.source_nutrient_id not in contract["usda_nutrient_ids"]:
                raise ValueError(
                    "source_nutrient_id does not match "
                    f"{nutrient.canonical_code}"
                )

        source_portion_ids: set[str] = set()
        sequence_numbers: set[int] = set()
        for portion in self.portions:
            if portion.source_portion_id is not None:
                if portion.source_portion_id in source_portion_ids:
                    raise ValueError(
                        f"duplicate source_portion_id: {portion.source_portion_id}"
                    )
                source_portion_ids.add(portion.source_portion_id)
            if portion.sequence_number is not None:
                if portion.sequence_number in sequence_numbers:
                    raise ValueError(
                        f"duplicate sequence_number: {portion.sequence_number}"
                    )
                sequence_numbers.add(portion.sequence_number)

        return self


class CanonicalNutrientDefinitionDTO(_StrictDTO):
    code: TrimmedText50
    name_en: TrimmedText100
    unit: NutrientUnit
    usda_nutrient_ids: Annotated[list[StrictPositiveInt], Field(min_length=1)]

    @field_validator("code")
    @classmethod
    def validate_canonical_code(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError("code must be uppercase canonical text")
        return value

    @field_validator("usda_nutrient_ids")
    @classmethod
    def validate_unique_source_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("usda_nutrient_ids must not contain duplicates")
        return value


class CanonicalNutrientCatalogDTO(_StrictDTO):
    catalog_version: Annotated[int, Field(strict=True)]
    definitions: list[CanonicalNutrientDefinitionDTO]

    @model_validator(mode="after")
    def validate_v1_catalog(self) -> "CanonicalNutrientCatalogDTO":
        if self.catalog_version != 1:
            raise ValueError("catalog_version must be 1")

        codes = [definition.code for definition in self.definitions]
        if len(codes) != len(set(codes)):
            raise ValueError("catalog definitions must not contain duplicate codes")

        expected_codes = [item[0] for item in CANONICAL_NUTRIENT_DEFINITIONS]
        if codes != expected_codes:
            raise ValueError(
                "catalog definitions must contain the exact v1 codes in order"
            )

        for definition, expected in zip(
            self.definitions,
            CANONICAL_NUTRIENT_DEFINITIONS,
            strict=True,
        ):
            code, name_en, unit, nutrient_ids = expected
            if (
                definition.code != code
                or definition.name_en != name_en
                or definition.unit is not unit
                or definition.usda_nutrient_ids != list(nutrient_ids)
            ):
                raise ValueError(f"catalog definition does not match v1: {code}")

        return self


def validate_pilot_food_record(
    record: CanonicalFoodRecordDTO,
) -> CanonicalFoodRecordDTO:
    amounts = {
        nutrient.canonical_code: nutrient.amount_per_100g
        for nutrient in record.nutrients
    }
    for code in sorted(_PILOT_REQUIRED_NUTRIENTS):
        if code not in amounts:
            raise ValueError(f"missing required pilot nutrient: {code}")
        if amounts[code] is None:
            raise ValueError(f"required pilot nutrient is null: {code}")
    return record
