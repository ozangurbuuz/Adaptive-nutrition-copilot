import hashlib
import importlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "ingestion"
JSONL_PATH = FIXTURE_ROOT / "canonical_3_foods.jsonl"
MANIFEST_PATH = FIXTURE_ROOT / "canonical_3_foods.manifest.json"


def _jsonl_contract():
    try:
        module = importlib.import_module("app.ingestion.jsonl")
    except ModuleNotFoundError:
        pytest.fail(
            "app.ingestion.jsonl is missing; implement the Stage 5A4.1 "
            "manifest and canonical JSONL parser",
            pytrace=False,
        )

    expected = (
        "load_manifest",
        "iter_canonical_food_records",
        "validate_canonical_dataset",
    )
    missing = [name for name in expected if not hasattr(module, name)]
    assert not missing, f"Canonical JSONL parser API is missing: {missing}"
    return module


def _fixture_manifest_document():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fixture_records():
    return [
        json.loads(line)
        for line in JSONL_PATH.read_text(encoding="utf-8").splitlines()
    ]


def _write_dataset(tmp_path: Path, records_or_lines, **manifest_overrides):
    lines = [
        item if isinstance(item, str) else json.dumps(item, separators=(",", ":"))
        for item in records_or_lines
    ]
    content = ("\n".join(lines) + "\n").encode("utf-8")
    jsonl_path = tmp_path / "canonical.jsonl"
    jsonl_path.write_bytes(content)

    manifest = _fixture_manifest_document()
    manifest.update(
        canonical_filename=jsonl_path.name,
        canonical_sha256=hashlib.sha256(content).hexdigest(),
        record_count=len(lines),
    )
    manifest.update(manifest_overrides)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, separators=(",", ":")),
        encoding="utf-8",
    )
    return jsonl_path, manifest_path


def test_synthetic_fixture_metadata_and_checksum_are_self_consistent() -> None:
    assert JSONL_PATH.is_file(), "Synthetic canonical JSONL fixture is missing"
    assert MANIFEST_PATH.is_file(), "Synthetic canonical manifest fixture is missing"

    manifest = _fixture_manifest_document()
    content = JSONL_PATH.read_bytes()
    records = _fixture_records()

    assert manifest["source"] == "USDA_FDC_FOUNDATION_TEST_FIXTURE"
    assert manifest["release_version"] == "test-fixture-v1"
    assert manifest["license_reference"] == "TEST_ONLY_SYNTHETIC_DATA"
    assert manifest["raw_filename"] == "synthetic_usda_foundation_source.json"
    assert manifest["canonical_filename"] == "canonical_3_foods.jsonl"
    assert manifest["canonical_sha256"] == hashlib.sha256(content).hexdigest()
    assert manifest["record_count"] == len(records) == 3
    assert [record["source_food_id"] for record in records] == [
        "test-olive-oil",
        "test-whole-milk",
        "test-banana",
    ]
    assert all(
        record["source"] == "USDA_FDC_FOUNDATION_TEST_FIXTURE"
        for record in records
    )


def test_fixture_covers_required_synthetic_contract_cases() -> None:
    records = _fixture_records()
    required = {"ENERGY_KCAL", "PROTEIN", "TOTAL_FAT", "CARBOHYDRATE"}
    assert all(
        required.issubset(
            {nutrient["canonical_code"] for nutrient in record["nutrients"]}
        )
        for record in records
    )

    optional_codes = {
        "FIBER",
        "TOTAL_SUGARS",
        "SATURATED_FAT",
        "SODIUM",
    }
    assert any(
        optional_codes
        - {nutrient["canonical_code"] for nutrient in record["nutrients"]}
        for record in records
    )
    assert any(
        nutrient["amount_per_100g"] is None
        for record in records
        for nutrient in record["nutrients"]
        if nutrient["canonical_code"] in optional_codes
    )
    assert any(
        nutrient["amount_per_100g"] == "0.000000"
        for record in records
        for nutrient in record["nutrients"]
        if nutrient["canonical_code"] in optional_codes
    )
    portions = [portion for record in records for portion in record["portions"]]
    assert any(portion["source_portion_id"] is not None for portion in portions)
    assert any(
        portion["source_portion_id"] is None
        and portion["sequence_number"] is not None
        for portion in portions
    )
    assert any(portion["gram_weight"] is None for portion in portions)
    assert len({portion["measure_code"] for portion in portions}) >= 3


def test_manifest_and_three_synthetic_foods_parse_successfully() -> None:
    api = _jsonl_contract()
    manifest = api.load_manifest(MANIFEST_PATH)
    records = api.validate_canonical_dataset(
        JSONL_PATH,
        manifest,
        require_pilot_nutrients=True,
    )

    assert len(records) == 3
    assert [record.source_food_id for record in records] == [
        "test-olive-oil",
        "test-whole-milk",
        "test-banana",
    ]
    assert records[0].food.name == "olive oil"
    assert records[0].source_description == "Synthetic olive oil test record"


def test_record_iterator_is_lazy_and_does_not_load_jsonl_as_one_json_document(
    monkeypatch,
) -> None:
    api = _jsonl_contract()
    manifest = api.load_manifest(MANIFEST_PATH)

    def forbidden_whole_document_read(*args, **kwargs):
        raise AssertionError("JSONL records must be processed line by line")

    monkeypatch.setattr(Path, "read_text", forbidden_whole_document_read)
    monkeypatch.setattr(json, "load", forbidden_whole_document_read)
    iterator = api.iter_canonical_food_records(JSONL_PATH, manifest)

    assert iter(iterator) is iterator
    assert len(list(iterator)) == 3


def test_checksum_is_verified_before_invalid_json_is_parsed(tmp_path: Path) -> None:
    api = _jsonl_contract()
    jsonl_path, manifest_path = _write_dataset(tmp_path, ["{invalid-json"])
    manifest_document = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_document["canonical_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest_document), encoding="utf-8")
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError) as error:
        api.validate_canonical_dataset(jsonl_path, manifest)

    assert "checksum" in str(error.value).casefold()
    assert "line" not in str(error.value).casefold()


def test_record_count_must_match_manifest(tmp_path: Path) -> None:
    api = _jsonl_contract()
    jsonl_path, manifest_path = _write_dataset(
        tmp_path,
        _fixture_records(),
        record_count=4,
    )
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError, match="record_count"):
        api.validate_canonical_dataset(jsonl_path, manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", "A_DIFFERENT_SOURCE"),
        ("release_version", "another-release"),
    ],
)
def test_record_source_and_release_must_match_manifest(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    api = _jsonl_contract()
    records = _fixture_records()
    records[1][field] = value
    jsonl_path, manifest_path = _write_dataset(tmp_path, records)
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError, match=field):
        api.validate_canonical_dataset(jsonl_path, manifest)


def test_duplicate_source_food_id_is_rejected(tmp_path: Path) -> None:
    api = _jsonl_contract()
    records = _fixture_records()
    records[1]["source_food_id"] = records[0]["source_food_id"]
    jsonl_path, manifest_path = _write_dataset(tmp_path, records)
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError, match="source_food_id"):
        api.validate_canonical_dataset(jsonl_path, manifest)


def test_blank_jsonl_line_is_rejected_with_one_based_line_number(
    tmp_path: Path,
) -> None:
    api = _jsonl_contract()
    records = _fixture_records()
    jsonl_path, manifest_path = _write_dataset(
        tmp_path,
        [json.dumps(records[0], separators=(",", ":")), "", json.dumps(records[1])],
    )
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError) as error:
        api.validate_canonical_dataset(jsonl_path, manifest)
    message = str(error.value).casefold()
    assert "line 2" in message
    assert "blank" in message or "empty" in message


def test_invalid_json_error_is_line_numbered_and_does_not_echo_raw_record(
    tmp_path: Path,
) -> None:
    api = _jsonl_contract()
    secret_marker = "DO_NOT_ECHO_THIS_RAW_RECORD"
    records = _fixture_records()
    invalid_line = "{\"secret\":\"" + secret_marker + "\""
    jsonl_path, manifest_path = _write_dataset(
        tmp_path,
        [json.dumps(records[0]), invalid_line],
    )
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError) as error:
        api.validate_canonical_dataset(jsonl_path, manifest)
    message = str(error.value)
    assert "line 2" in message.casefold()
    assert secret_marker not in message


def test_jsonl_must_be_valid_utf8(tmp_path: Path) -> None:
    api = _jsonl_contract()
    content = b"{\"source\":\"fixture\",\"invalid\":\"\xff\"}\n"
    jsonl_path = tmp_path / "canonical.jsonl"
    jsonl_path.write_bytes(content)
    manifest = _fixture_manifest_document()
    manifest.update(
        canonical_filename=jsonl_path.name,
        canonical_sha256=hashlib.sha256(content).hexdigest(),
        record_count=1,
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    validated_manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError, match="UTF-8"):
        api.validate_canonical_dataset(jsonl_path, validated_manifest)


@pytest.mark.parametrize("root", [[], "record", 13, None])
def test_each_jsonl_line_must_have_an_object_root(tmp_path: Path, root) -> None:
    api = _jsonl_contract()
    jsonl_path, manifest_path = _write_dataset(tmp_path, [root])
    manifest = api.load_manifest(manifest_path)

    with pytest.raises(ValueError) as error:
        api.validate_canonical_dataset(jsonl_path, manifest)
    assert "line 1" in str(error.value).casefold()
    assert "object" in str(error.value).casefold()


def test_unknown_record_fields_are_rejected_without_echoing_values(
    tmp_path: Path,
) -> None:
    api = _jsonl_contract()
    secret_marker = "DO_NOT_ECHO_UNKNOWN_FIELD_VALUE"
    records = _fixture_records()
    records[0]["unexpected"] = secret_marker
    jsonl_path, manifest_path = _write_dataset(tmp_path, records)
    manifest = api.load_manifest(manifest_path)

    with pytest.raises((ValidationError, ValueError)) as error:
        api.validate_canonical_dataset(jsonl_path, manifest)
    message = str(error.value)
    assert "line 1" in message.casefold()
    assert secret_marker not in message


@pytest.mark.parametrize("manifest_root", [[], "manifest", 13, None])
def test_manifest_root_must_be_a_json_object(
    tmp_path: Path,
    manifest_root,
) -> None:
    api = _jsonl_contract()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_root), encoding="utf-8")

    with pytest.raises(ValueError, match="object"):
        api.load_manifest(manifest_path)


def test_invalid_manifest_json_is_reported_without_echoing_raw_content(
    tmp_path: Path,
) -> None:
    api = _jsonl_contract()
    secret_marker = "DO_NOT_ECHO_MANIFEST_CONTENT"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        "{\"secret\":\"" + secret_marker + "\"",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as error:
        api.load_manifest(manifest_path)
    assert secret_marker not in str(error.value)


def test_manifest_must_be_valid_utf8(tmp_path: Path) -> None:
    api = _jsonl_contract()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(b"{\"invalid\":\"\xff\"}")

    with pytest.raises(ValueError, match="UTF-8"):
        api.load_manifest(manifest_path)


def test_unknown_manifest_field_is_rejected_without_echoing_value(
    tmp_path: Path,
) -> None:
    api = _jsonl_contract()
    secret_marker = "DO_NOT_ECHO_MANIFEST_EXTRA"
    document = _fixture_manifest_document()
    document["unexpected"] = secret_marker
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises((ValidationError, ValueError)) as error:
        api.load_manifest(manifest_path)
    assert secret_marker not in str(error.value)


def test_parser_does_not_access_database_or_network(monkeypatch) -> None:
    def forbidden_external_access(*args, **kwargs):
        raise AssertionError("Canonical parser must not access database or network")

    import psycopg
    import socket
    import sqlalchemy

    monkeypatch.setattr(psycopg, "connect", forbidden_external_access)
    monkeypatch.setattr(sqlalchemy, "create_engine", forbidden_external_access)
    monkeypatch.setattr(socket, "create_connection", forbidden_external_access)

    api = _jsonl_contract()
    manifest = api.load_manifest(MANIFEST_PATH)
    records = api.validate_canonical_dataset(JSONL_PATH, manifest)
    assert len(records) == 3


def test_pilot_validation_is_optional_and_applied_to_every_record(
    tmp_path: Path,
) -> None:
    api = _jsonl_contract()
    records = _fixture_records()
    records[1]["nutrients"] = [
        nutrient
        for nutrient in records[1]["nutrients"]
        if nutrient["canonical_code"] != "ENERGY_KCAL"
    ]
    jsonl_path, manifest_path = _write_dataset(tmp_path, records)
    manifest = api.load_manifest(manifest_path)

    assert len(api.validate_canonical_dataset(jsonl_path, manifest)) == 3
    with pytest.raises((ValidationError, ValueError)) as error:
        api.validate_canonical_dataset(
            jsonl_path,
            manifest,
            require_pilot_nutrients=True,
        )
    assert "ENERGY_KCAL" in str(error.value)
