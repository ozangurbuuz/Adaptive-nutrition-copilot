import importlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = (
    PROJECT_ROOT
    / "backend"
    / "app"
    / "ingestion"
    / "catalogs"
    / "canonical_nutrients.v1.json"
)

EXPECTED_DEFINITIONS = [
    {
        "code": "ENERGY_KCAL",
        "name_en": "Energy",
        "unit": "KCAL",
        "usda_nutrient_ids": [2048, 2047, 1008],
    },
    {
        "code": "PROTEIN",
        "name_en": "Protein",
        "unit": "GRAM",
        "usda_nutrient_ids": [1003],
    },
    {
        "code": "TOTAL_FAT",
        "name_en": "Total fat",
        "unit": "GRAM",
        "usda_nutrient_ids": [1004],
    },
    {
        "code": "CARBOHYDRATE",
        "name_en": "Carbohydrate",
        "unit": "GRAM",
        "usda_nutrient_ids": [1005],
    },
    {
        "code": "FIBER",
        "name_en": "Dietary fiber",
        "unit": "GRAM",
        "usda_nutrient_ids": [1079],
    },
    {
        "code": "TOTAL_SUGARS",
        "name_en": "Total sugars",
        "unit": "GRAM",
        "usda_nutrient_ids": [2000],
    },
    {
        "code": "SATURATED_FAT",
        "name_en": "Saturated fat",
        "unit": "GRAM",
        "usda_nutrient_ids": [1258],
    },
    {
        "code": "SODIUM",
        "name_en": "Sodium",
        "unit": "MILLIGRAM",
        "usda_nutrient_ids": [1093],
    },
]


def _catalog_schema():
    try:
        module = importlib.import_module("app.ingestion.schemas")
    except ModuleNotFoundError:
        pytest.fail(
            "app.ingestion.schemas is missing; implement "
            "CanonicalNutrientCatalogDTO",
            pytrace=False,
        )
    model = getattr(module, "CanonicalNutrientCatalogDTO", None)
    assert model is not None, "CanonicalNutrientCatalogDTO is missing"
    return model


def _load_catalog_document():
    assert CATALOG_PATH.is_file(), (
        "backend/app/ingestion/catalogs/canonical_nutrients.v1.json is missing"
    )
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"Canonical nutrient catalog is not valid UTF-8 JSON: {exc}")


def _valid_catalog_payload():
    return {
        "catalog_version": 1,
        "definitions": [dict(definition) for definition in EXPECTED_DEFINITIONS],
    }


def test_versioned_catalog_file_exists_and_is_valid_utf8_json() -> None:
    document = _load_catalog_document()
    assert isinstance(document, dict), "Canonical nutrient catalog root must be an object"


def test_catalog_root_and_exact_eight_definitions_are_locked() -> None:
    document = _load_catalog_document()
    assert set(document) == {"catalog_version", "definitions"}
    assert document["catalog_version"] == 1
    assert document["definitions"] == EXPECTED_DEFINITIONS


def test_catalog_document_validates_with_the_canonical_schema() -> None:
    model = _catalog_schema()
    validated = model.model_validate(_load_catalog_document())
    assert validated.catalog_version == 1
    assert len(validated.definitions) == 8


def test_catalog_units_are_existing_nutrient_unit_values() -> None:
    from app.models.enums import NutrientUnit

    known_units = {unit.value for unit in NutrientUnit}
    assert {item["unit"] for item in EXPECTED_DEFINITIONS}.issubset(known_units)


def test_energy_priority_order_is_specific_general_then_legacy() -> None:
    energy = next(
        definition
        for definition in EXPECTED_DEFINITIONS
        if definition["code"] == "ENERGY_KCAL"
    )
    assert energy["usda_nutrient_ids"] == [2048, 2047, 1008]


def test_catalog_schema_rejects_duplicate_codes() -> None:
    model = _catalog_schema()
    payload = _valid_catalog_payload()
    payload["definitions"].append(dict(payload["definitions"][0]))
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_catalog_schema_rejects_duplicate_usda_ids_within_definition() -> None:
    model = _catalog_schema()
    payload = _valid_catalog_payload()
    payload["definitions"][0]["usda_nutrient_ids"] = [2048, 2048]
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("invalid_id", [0, -1, 1003.0, "1003", True])
def test_catalog_schema_requires_positive_integer_usda_ids(invalid_id) -> None:
    model = _catalog_schema()
    payload = _valid_catalog_payload()
    payload["definitions"][1]["usda_nutrient_ids"] = [invalid_id]
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code", "protein"),
        ("code", " PROTEIN"),
        ("code", "PROTEIN "),
        ("name_en", ""),
        ("name_en", " Protein"),
        ("name_en", "Protein "),
        ("unit", "OUNCE"),
    ],
)
def test_catalog_definition_requires_canonical_text_and_known_unit(
    field: str,
    value,
) -> None:
    model = _catalog_schema()
    payload = _valid_catalog_payload()
    payload["definitions"][1][field] = value
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_catalog_schema_rejects_unknown_root_and_definition_fields() -> None:
    model = _catalog_schema()

    root_extra = _valid_catalog_payload()
    root_extra["unexpected"] = True
    with pytest.raises(ValidationError):
        model.model_validate(root_extra)

    definition_extra = _valid_catalog_payload()
    definition_extra["definitions"][0]["unexpected"] = True
    with pytest.raises(ValidationError):
        model.model_validate(definition_extra)
