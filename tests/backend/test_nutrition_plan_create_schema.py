import importlib
import uuid
from datetime import date

import pytest
from pydantic import ValidationError


# Testlerde aynı kimliklerin kullanılması, DTO dönüşümlerini öngörülebilir kılar.
CLIENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
DIETITIAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


# Production DTO henüz yoksa collection'ı bozmadan anlaşılır bir RED hatası üretir.
def _schema_type():
    module = importlib.import_module("app.schemas.nutrition_plan")
    schema_type = getattr(module, "NutritionPlanCreate", None)
    assert schema_type is not None, "NutritionPlanCreate request DTO is missing"
    return schema_type


# Her senaryonun üzerine yalnızca değiştirdiği alanları eklediği temel isteği hazırlar.
def _minimum_payload() -> dict[str, object]:
    return {
        "client_profile_id": CLIENT_ID,
        "dietitian_profile_id": DIETITIAN_ID,
        "title": "September Plan",
    }


# Zorunlu alanların yeterli, opsiyonel alanların varsayılan olarak None olduğunu sınar.
def test_create_schema_accepts_minimum_payload_and_defaults_optionals() -> None:
    schema_type = _schema_type()

    result = schema_type.model_validate(_minimum_payload())

    assert result.client_profile_id == CLIENT_ID
    assert result.dietitian_profile_id == DIETITIAN_ID
    assert result.title == "September Plan"
    assert result.starts_on is None
    assert result.ends_on is None
    assert result.notes is None


# İzin verilen bütün request alanlarının doğru Python tiplerine çevrildiğini doğrular.
def test_create_schema_accepts_all_request_fields() -> None:
    schema_type = _schema_type()
    payload = {
        **_minimum_payload(),
        "starts_on": "2026-09-01",
        "ends_on": "2026-09-07",
        "notes": "Initial draft",
    }

    result = schema_type.model_validate(payload)

    assert result.model_dump() == {
        "client_profile_id": CLIENT_ID,
        "dietitian_profile_id": DIETITIAN_ID,
        "title": "September Plan",
        "starts_on": date(2026, 9, 1),
        "ends_on": date(2026, 9, 7),
        "notes": "Initial draft",
    }


# Bir günlük planlarda başlangıç ve bitiş tarihinin aynı olmasına izin verir.
def test_create_schema_accepts_equal_start_and_end_dates() -> None:
    schema_type = _schema_type()
    payload = {
        **_minimum_payload(),
        "starts_on": "2026-09-01",
        "ends_on": "2026-09-01",
    }

    result = schema_type.model_validate(payload)

    assert result.starts_on == result.ends_on == date(2026, 9, 1)


# Nullable tarihlerin birbirinden bağımsız gönderilebildiğini iki yönde kontrol eder.
@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("starts_on", "2026-09-01"),
        ("ends_on", "2026-09-07"),
    ],
)
def test_create_schema_accepts_only_one_date(
    field_name: str,
    field_value: str,
) -> None:
    schema_type = _schema_type()
    payload = {**_minimum_payload(), field_name: field_value}

    result = schema_type.model_validate(payload)

    assert getattr(result, field_name) == date.fromisoformat(field_value)


# Bitiş tarihi başlangıçtan önceyse schema seviyesinde validation bekler.
def test_create_schema_rejects_reversed_date_range() -> None:
    schema_type = _schema_type()
    payload = {
        **_minimum_payload(),
        "starts_on": "2026-09-07",
        "ends_on": "2026-09-01",
    }

    with pytest.raises(ValidationError):
        schema_type.model_validate(payload)


# Veritabanı sınırlarıyla uyumlu olarak boş ve 255 karakteri aşan başlıkları reddeder.
@pytest.mark.parametrize("title", ["", "x" * 256])
def test_create_schema_rejects_invalid_title_length(title: str) -> None:
    schema_type = _schema_type()

    with pytest.raises(ValidationError):
        schema_type.model_validate({**_minimum_payload(), "title": title})


# Notes alanının VARCHAR(1000) sınırını API girişinde korur.
def test_create_schema_rejects_notes_longer_than_1000_characters() -> None:
    schema_type = _schema_type()

    with pytest.raises(ValidationError):
        schema_type.model_validate({**_minimum_payload(), "notes": "x" * 1001})


# Sunucunun ürettiği veya sonraki dilimlere ait alanların request'e sızmasını engeller.
@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("id", "10000000-0000-0000-0000-000000000001"),
        ("status", "ACTIVE"),
        ("days", []),
        ("created_at", "2026-09-01T00:00:00Z"),
        ("updated_at", "2026-09-01T00:00:00Z"),
    ],
)
def test_create_schema_forbids_non_request_fields(
    field_name: str,
    field_value: object,
) -> None:
    schema_type = _schema_type()

    with pytest.raises(ValidationError) as exc_info:
        schema_type.model_validate(
            {**_minimum_payload(), field_name: field_value}
        )

    # Hatanın genel validation değil, özellikle yasaklanan ekstra alan olduğunu kanıtlar.
    assert any(
        error["type"] == "extra_forbidden"
        and error["loc"] == (field_name,)
        for error in exc_info.value.errors()
    )
