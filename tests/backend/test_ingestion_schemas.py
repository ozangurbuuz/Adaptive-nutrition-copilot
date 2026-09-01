import importlib
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

EXPECTED_SCHEMA_NAMES = (
    "DatasetManifestDTO",
    "CanonicalFoodDTO",
    "CanonicalNutrientDTO",
    "CanonicalPortionDTO",
    "CanonicalFoodRecordDTO",
    "CanonicalNutrientCatalogDTO",
    "CanonicalNutrientDefinitionDTO",
)


def _schemas():
    try:
        module = importlib.import_module("app.ingestion.schemas")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "app.ingestion.schemas is missing; implement the Stage 5A4.1 "
            "canonical DTO contract",
            pytrace=False,
        )

    missing = [name for name in EXPECTED_SCHEMA_NAMES if not hasattr(module, name)]
    assert not missing, f"Canonical ingestion DTOs are missing: {missing}"
    assert hasattr(module, "validate_pilot_food_record"), (
        "validate_pilot_food_record is missing"
    )
    return module


def _manifest_payload(**overrides):
    payload = {
        "source": "USDA_FDC_FOUNDATION_TEST_FIXTURE",
        "release_version": "test-fixture-v1",
        "downloaded_at": "2026-09-01T00:00:00Z",
        "license_reference": "TEST_ONLY_SYNTHETIC_DATA",
        "raw_filename": "synthetic_usda_foundation_source.json",
        "canonical_filename": "canonical_3_foods.jsonl",
        "raw_size_bytes": 1,
        "raw_sha256": "a" * 64,
        "canonical_sha256": "b" * 64,
        "record_count": 3,
        "canonical_schema_version": "1",
        "mapping_version": "canonical-nutrients-v1",
        "generator_version": "test-fixture-v1",
    }
    payload.update(overrides)
    return payload


def _food_payload(**overrides):
    payload = {
        "name": "banana",
        "category": "FRUIT",
        "default_serving_quantity": "1.000000",
        "default_serving_unit": "PIECE",
    }
    payload.update(overrides)
    return payload


def _nutrient_payload(code="PROTEIN", source_id=1003, amount="1.000000", **overrides):
    units = {
        "ENERGY_KCAL": "KCAL",
        "PROTEIN": "GRAM",
        "TOTAL_FAT": "GRAM",
        "CARBOHYDRATE": "GRAM",
        "FIBER": "GRAM",
        "TOTAL_SUGARS": "GRAM",
        "SATURATED_FAT": "GRAM",
        "SODIUM": "MILLIGRAM",
    }
    payload = {
        "source_nutrient_id": source_id,
        "canonical_code": code,
        "amount_per_100g": amount,
        "unit": units[code],
    }
    payload.update(overrides)
    return payload


def _portion_payload(**overrides):
    payload = {
        "source_portion_id": "test-portion-banana-medium",
        "amount": "1.000000",
        "measure_code": "PIECE",
        "measure_name": "piece",
        "modifier": "medium",
        "portion_description": "1 medium synthetic banana",
        "gram_weight": "118.000000",
        "sequence_number": 1,
    }
    payload.update(overrides)
    return payload


def _required_nutrients():
    return [
        _nutrient_payload("ENERGY_KCAL", 2048, "100.000000"),
        _nutrient_payload("PROTEIN", 1003, "1.000000"),
        _nutrient_payload("TOTAL_FAT", 1004, "2.000000"),
        _nutrient_payload("CARBOHYDRATE", 1005, "3.000000"),
    ]


def _record_payload(**overrides):
    payload = {
        "source": "USDA_FDC_FOUNDATION_TEST_FIXTURE",
        "release_version": "test-fixture-v1",
        "source_food_id": "test-banana",
        "food": _food_payload(),
        "source_description": "Synthetic banana test record",
        "preparation_state": "raw",
        "nutrients": _required_nutrients(),
        "portions": [_portion_payload()],
    }
    payload.update(overrides)
    return payload


def test_expected_schema_api_is_available() -> None:
    _schemas()


def test_all_dtos_forbid_unknown_fields() -> None:
    schemas = _schemas()
    payloads = {
        "DatasetManifestDTO": _manifest_payload(),
        "CanonicalFoodDTO": _food_payload(),
        "CanonicalNutrientDTO": _nutrient_payload(),
        "CanonicalPortionDTO": _portion_payload(),
        "CanonicalFoodRecordDTO": _record_payload(),
        "CanonicalNutrientDefinitionDTO": {
            "code": "PROTEIN",
            "name_en": "Protein",
            "unit": "GRAM",
            "usda_nutrient_ids": [1003],
        },
        "CanonicalNutrientCatalogDTO": {
            "catalog_version": 1,
            "definitions": [
                {
                    "code": "PROTEIN",
                    "name_en": "Protein",
                    "unit": "GRAM",
                    "usda_nutrient_ids": [1003],
                }
            ],
        },
    }

    for name, payload in payloads.items():
        model = getattr(schemas, name)
        invalid = {**payload, "unexpected": "must be forbidden"}
        with pytest.raises(ValidationError):
            model.model_validate(invalid)


@pytest.mark.parametrize(
    "value",
    [
        "0.000000",
        "1.000000",
        "13.500000",
        "99999999.999999",
    ],
)
def test_decimal6_accepts_only_canonical_strings(value: str) -> None:
    schemas = _schemas()
    nutrient = schemas.CanonicalNutrientDTO.model_validate(
        _nutrient_payload(amount=value)
    )
    assert nutrient.amount_per_100g == Decimal(value)
    assert isinstance(nutrient.amount_per_100g, Decimal)


@pytest.mark.parametrize(
    "value",
    [
        13.5,
        "13.5",
        "13.5000000",
        "013.500000",
        "1e2",
        "NaN",
        "Infinity",
        "-1.000000",
        " 13.500000",
        "100000000.000000",
        "1,000000",
        "+1.000000",
    ],
)
def test_decimal6_rejects_noncanonical_values(value) -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalNutrientDTO.model_validate(
            _nutrient_payload(amount=value)
        )


def test_decimal6_preserves_null_and_real_zero_as_distinct_values() -> None:
    schemas = _schemas()
    null_value = schemas.CanonicalNutrientDTO.model_validate(
        _nutrient_payload(amount=None)
    )
    zero_value = schemas.CanonicalNutrientDTO.model_validate(
        _nutrient_payload(amount="0.000000")
    )

    assert null_value.amount_per_100g is None
    assert zero_value.amount_per_100g == Decimal("0.000000")
    assert zero_value.amount_per_100g is not None


@pytest.mark.parametrize("value", ["0.000000", None])
def test_portion_amount_is_required_and_positive(value) -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalPortionDTO.model_validate(_portion_payload(amount=value))


def test_non_null_gram_weight_must_be_positive_but_null_is_valid() -> None:
    schemas = _schemas()
    nullable = schemas.CanonicalPortionDTO.model_validate(
        _portion_payload(gram_weight=None)
    )
    assert nullable.gram_weight is None

    with pytest.raises(ValidationError):
        schemas.CanonicalPortionDTO.model_validate(
            _portion_payload(gram_weight="0.000000")
        )


def test_non_null_default_serving_quantity_must_be_positive() -> None:
    schemas = _schemas()
    nullable = schemas.CanonicalFoodDTO.model_validate(
        _food_payload(
            default_serving_quantity=None,
            default_serving_unit=None,
        )
    )
    assert nullable.default_serving_quantity is None

    with pytest.raises(ValidationError):
        schemas.CanonicalFoodDTO.model_validate(
            _food_payload(default_serving_quantity="0.000000")
        )


@pytest.mark.parametrize("name", [" Banana", "banana ", "Banana", "BANANA", ""])
def test_food_name_must_be_nonblank_trimmed_and_casefolded(name: str) -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalFoodDTO.model_validate(_food_payload(name=name))


def test_text_fields_enforce_trim_nonblank_and_max_lengths() -> None:
    schemas = _schemas()
    invalid_payloads = [
        _record_payload(source=" source"),
        _record_payload(release_version="version "),
        _record_payload(source_food_id=""),
        _record_payload(source_description=" " * 2),
        _record_payload(preparation_state=" raw"),
        _record_payload(source="s" * 51),
        _record_payload(release_version="v" * 101),
        _record_payload(source_food_id="i" * 101),
        _record_payload(source_description="d" * 256),
        _record_payload(preparation_state="p" * 101),
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            schemas.CanonicalFoodRecordDTO.model_validate(payload)


def test_dtos_return_existing_domain_enums() -> None:
    from app.models.enums import FoodCategory, MealItemUnit, NutrientUnit

    schemas = _schemas()
    food = schemas.CanonicalFoodDTO.model_validate(_food_payload())
    nutrient = schemas.CanonicalNutrientDTO.model_validate(_nutrient_payload())

    assert food.category is FoodCategory.FRUIT
    assert food.default_serving_unit is MealItemUnit.PIECE
    assert nutrient.unit is NutrientUnit.GRAM

    with pytest.raises(ValidationError):
        schemas.CanonicalFoodDTO.model_validate(_food_payload(category="UNKNOWN"))
    with pytest.raises(ValidationError):
        schemas.CanonicalNutrientDTO.model_validate(
            _nutrient_payload(unit="OUNCE")
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_portion_id": None, "sequence_number": None},
        {"source_portion_id": "", "sequence_number": 1},
        {"source_portion_id": " portion", "sequence_number": 1},
        {"source_portion_id": None, "sequence_number": 0},
        {"measure_code": "table-spoon"},
        {"measure_name": " cup"},
        {"modifier": " "},
        {"portion_description": "description "},
    ],
)
def test_portion_identity_and_text_contract(overrides) -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalPortionDTO.model_validate(_portion_payload(**overrides))


def test_portion_allows_either_source_id_or_sequence_fallback() -> None:
    schemas = _schemas()
    source_identity = schemas.CanonicalPortionDTO.model_validate(
        _portion_payload(sequence_number=None)
    )
    sequence_identity = schemas.CanonicalPortionDTO.model_validate(
        _portion_payload(source_portion_id=None, sequence_number=2)
    )

    assert source_identity.source_portion_id == "test-portion-banana-medium"
    assert source_identity.sequence_number is None
    assert sequence_identity.source_portion_id is None
    assert sequence_identity.sequence_number == 2


def test_record_rejects_duplicate_nutrient_codes_and_source_ids() -> None:
    schemas = _schemas()
    duplicate_code = _required_nutrients() + [
        _nutrient_payload("PROTEIN", 9999, "2.000000")
    ]
    duplicate_source_id = _required_nutrients() + [
        _nutrient_payload("FIBER", 1003, "2.000000")
    ]

    for nutrients in (duplicate_code, duplicate_source_id):
        with pytest.raises(ValidationError):
            schemas.CanonicalFoodRecordDTO.model_validate(
                _record_payload(nutrients=nutrients)
            )


def test_record_rejects_duplicate_non_null_portion_identities() -> None:
    schemas = _schemas()
    duplicate_source_id = [
        _portion_payload(sequence_number=1),
        _portion_payload(sequence_number=2),
    ]
    duplicate_sequence = [
        _portion_payload(source_portion_id="portion-a", sequence_number=1),
        _portion_payload(source_portion_id="portion-b", sequence_number=1),
    ]

    for portions in (duplicate_source_id, duplicate_sequence):
        with pytest.raises(ValidationError):
            schemas.CanonicalFoodRecordDTO.model_validate(
                _record_payload(portions=portions)
            )


def test_record_rejects_nutrient_code_unit_mismatch() -> None:
    schemas = _schemas()
    mismatched = [_nutrient_payload("PROTEIN", 1003, unit="MILLIGRAM")]
    with pytest.raises(ValidationError):
        schemas.CanonicalFoodRecordDTO.model_validate(
            _record_payload(nutrients=mismatched)
        )


def test_base_schema_allows_empty_nutrients_and_portions() -> None:
    schemas = _schemas()
    record = schemas.CanonicalFoodRecordDTO.model_validate(
        _record_payload(nutrients=[], portions=[])
    )
    assert record.nutrients == []
    assert record.portions == []


def test_pilot_policy_requires_four_present_non_null_nutrients() -> None:
    schemas = _schemas()
    valid = schemas.CanonicalFoodRecordDTO.model_validate(_record_payload())
    assert schemas.validate_pilot_food_record(valid) is valid

    missing = schemas.CanonicalFoodRecordDTO.model_validate(
        _record_payload(nutrients=_required_nutrients()[:-1])
    )
    null_energy = schemas.CanonicalFoodRecordDTO.model_validate(
        _record_payload(
            nutrients=[
                _nutrient_payload("ENERGY_KCAL", 2048, None),
                *_required_nutrients()[1:],
            ]
        )
    )
    for record in (missing, null_energy):
        with pytest.raises((ValidationError, ValueError)):
            schemas.validate_pilot_food_record(record)


@pytest.mark.parametrize(
    "filename",
    [
        "/tmp/canonical.jsonl",
        "C:\\temp\\canonical.jsonl",
        "../canonical.jsonl",
        "folder/canonical.jsonl",
        "folder\\canonical.jsonl",
    ],
)
def test_manifest_rejects_non_basename_filenames(filename: str) -> None:
    schemas = _schemas()
    for field in ("raw_filename", "canonical_filename"):
        with pytest.raises(ValidationError):
            schemas.DatasetManifestDTO.model_validate(
                _manifest_payload(**{field: filename})
            )


def test_manifest_text_fields_are_nonblank_trimmed_and_bounded() -> None:
    schemas = _schemas()
    invalid_payloads = [
        _manifest_payload(source=" source"),
        _manifest_payload(source="s" * 51),
        _manifest_payload(release_version="version "),
        _manifest_payload(release_version="v" * 101),
        _manifest_payload(license_reference=""),
        _manifest_payload(license_reference="l" * 501),
        _manifest_payload(canonical_schema_version=" 1"),
        _manifest_payload(mapping_version=""),
        _manifest_payload(generator_version="v1 "),
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            schemas.DatasetManifestDTO.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw_size_bytes", 1.0),
        ("raw_size_bytes", "1"),
        ("raw_size_bytes", True),
        ("record_count", 1.0),
        ("record_count", "1"),
        ("record_count", True),
    ],
)
def test_manifest_count_fields_require_strict_integers(field: str, value) -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.DatasetManifestDTO.model_validate(
            _manifest_payload(**{field: value})
        )


def test_manifest_requires_timezone_aware_datetime_and_strict_hashes() -> None:
    schemas = _schemas()
    valid = schemas.DatasetManifestDTO.model_validate(_manifest_payload())
    assert isinstance(valid.downloaded_at, datetime)
    assert valid.downloaded_at.utcoffset() is not None

    invalid_payloads = [
        _manifest_payload(downloaded_at="2026-09-01T00:00:00"),
        _manifest_payload(raw_sha256="A" * 64),
        _manifest_payload(canonical_sha256="a" * 63),
        _manifest_payload(raw_size_bytes=0),
        _manifest_payload(record_count=-1),
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            schemas.DatasetManifestDTO.model_validate(payload)


@pytest.mark.parametrize("source_nutrient_id", [0, -1, 1003.0, "1003", True])
def test_nutrient_source_id_is_a_strict_positive_integer(source_nutrient_id) -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalNutrientDTO.model_validate(
            _nutrient_payload(source_nutrient_id=source_nutrient_id)
        )


def test_nutrient_code_is_limited_to_the_eight_canonical_codes() -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalNutrientDTO.model_validate(
            _nutrient_payload(canonical_code="UNKNOWN_NUTRIENT")
        )


def test_food_and_portion_string_max_lengths_are_enforced() -> None:
    schemas = _schemas()
    with pytest.raises(ValidationError):
        schemas.CanonicalFoodDTO.model_validate(_food_payload(name="n" * 256))

    invalid_portions = [
        _portion_payload(source_portion_id="i" * 101),
        _portion_payload(measure_code="M" * 51),
        _portion_payload(measure_name="m" * 101),
        _portion_payload(modifier="m" * 101),
        _portion_payload(portion_description="d" * 256),
    ]
    for payload in invalid_portions:
        with pytest.raises(ValidationError):
            schemas.CanonicalPortionDTO.model_validate(payload)
