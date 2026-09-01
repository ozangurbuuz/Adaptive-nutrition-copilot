import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from app.ingestion.schemas import (
    CanonicalFoodRecordDTO,
    DatasetManifestDTO,
    validate_pilot_food_record,
)


def _validation_locations(error: ValidationError) -> str:
    locations = []
    for item in error.errors(include_input=False, include_context=False):
        location = ".".join(str(part) for part in item["loc"])
        locations.append(location or "root")
    return ", ".join(locations)


def load_manifest(path: Path) -> DatasetManifestDTO:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Manifest must be valid UTF-8") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Manifest contains invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Manifest root must be an object")

    try:
        return DatasetManifestDTO.model_validate(payload)
    except ValidationError as exc:
        locations = _validation_locations(exc)
        raise ValueError(f"Manifest validation failed at: {locations}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_checksum(path: Path, manifest: DatasetManifestDTO) -> None:
    if _sha256(path) != manifest.canonical_sha256:
        raise ValueError("Canonical checksum mismatch")


def iter_canonical_food_records(
    jsonl_path: Path,
    manifest: DatasetManifestDTO,
) -> Iterator[CanonicalFoodRecordDTO]:
    _verify_checksum(jsonl_path, manifest)
    source_food_ids: set[str] = set()
    record_count = 0

    try:
        with jsonl_path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise ValueError(f"JSONL line {line_number} is blank")

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON object at JSONL line {line_number}"
                    ) from exc

                if not isinstance(payload, dict):
                    raise ValueError(
                        f"JSONL line {line_number} root must be an object"
                    )

                try:
                    record = CanonicalFoodRecordDTO.model_validate(payload)
                except ValidationError as exc:
                    locations = _validation_locations(exc)
                    raise ValueError(
                        f"Record validation failed at JSONL line {line_number}: "
                        f"{locations}"
                    ) from exc

                if record.source != manifest.source:
                    raise ValueError(
                        f"source mismatch at JSONL line {line_number}"
                    )
                if record.release_version != manifest.release_version:
                    raise ValueError(
                        f"release_version mismatch at JSONL line {line_number}"
                    )
                if record.source_food_id in source_food_ids:
                    raise ValueError(
                        f"duplicate source_food_id at JSONL line {line_number}"
                    )
                source_food_ids.add(record.source_food_id)
                record_count += 1
                yield record
    except UnicodeDecodeError as exc:
        raise ValueError("JSONL must be valid UTF-8") from exc

    if record_count != manifest.record_count:
        raise ValueError(
            "JSONL record_count does not match manifest.record_count"
        )


def validate_canonical_dataset(
    jsonl_path: Path,
    manifest: DatasetManifestDTO,
    require_pilot_nutrients: bool = False,
) -> list[CanonicalFoodRecordDTO]:
    records = list(iter_canonical_food_records(jsonl_path, manifest))
    if require_pilot_nutrients:
        for record in records:
            validate_pilot_food_record(record)
    return records
