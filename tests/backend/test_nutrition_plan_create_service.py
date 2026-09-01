import importlib
import uuid
from datetime import date

import pytest

from app.core.exceptions import ResourceNotFoundException
from app.models.enums import NutritionPlanStatus
from app.models.nutrition_plan import NutritionPlan


# Sabit kimlikler, service'e giren request ile çıkan response'u kolayca karşılaştırmayı sağlar.
PLAN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
DIETITIAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


# Service testlerini gerçek schema implementasyonu tamamlanmadan çalıştıran request dublörüdür.
class _PlanCreateStub:
    client_profile_id = CLIENT_ID
    dietitian_profile_id = DIETITIAN_ID
    title = "September Plan"
    starts_on = date(2026, 9, 1)
    ends_on = date(2026, 9, 7)
    notes = "Initial draft"


# Commit ve rollback çağrılarını olay sırasıyla birlikte kaydeden session dublörüdür.
class _SessionSpy:
    # Ortak olay listesini ve opsiyonel commit hatasını test için hazırlar.
    def __init__(self, events: list[str], commit_exception=None) -> None:
        self.events = events
        self.commit_exception = commit_exception
        self.commit_calls = 0
        self.rollback_calls = 0

    # Başarılı commit'i kaydeder; istenirse gerçek session gibi aynı noktada hata üretir.
    def commit(self) -> None:
        self.events.append("commit")
        self.commit_calls += 1
        if self.commit_exception is not None:
            raise self.commit_exception

    # Service'in hata sonrası transaction'ı temizlediğini gözlemlemek için rollback'i kaydeder.
    def rollback(self) -> None:
        self.events.append("rollback")
        self.rollback_calls += 1


# Gerekli service/repository/schema sembollerini bulur ve eksikleri anlaşılır RED yapar.
def _service_contract():
    service_module = importlib.import_module("app.services.nutrition_plan")
    repository_module = importlib.import_module("app.repositories.nutrition_plan")
    schema_module = importlib.import_module("app.schemas.nutrition_plan")
    service = getattr(service_module, "create_nutrition_plan", None)
    dto_type = getattr(schema_module, "NutritionPlanRead", None)
    assert callable(service), "create_nutrition_plan service function is missing"
    assert dto_type is not None, "NutritionPlanRead response DTO is missing"
    return service_module, repository_module, service, dto_type


# Repository fonksiyonunu hem modül importunda hem açık alias kullanımında monkeypatch eder.
def _patch_repository_function(
    monkeypatch,
    service_module,
    repository_module,
    function_name: str,
    replacement,
) -> None:
    original = getattr(repository_module, function_name, None)
    assert callable(original), f"{function_name} repository function is missing"
    bound_aliases = [
        name
        for name, value in vars(service_module).items()
        if value is original
    ]
    monkeypatch.setattr(repository_module, function_name, replacement)
    for alias in bound_aliases:
        monkeypatch.setattr(service_module, alias, replacement)


# Üç repository bağımlılığını tek noktadan değiştirerek her testin akışa odaklanmasını sağlar.
def _patch_repository_contract(
    monkeypatch,
    service_module,
    repository_module,
    *,
    get_client,
    get_dietitian,
    create,
) -> None:
    _patch_repository_function(
        monkeypatch,
        service_module,
        repository_module,
        "get_client_profile_by_id",
        get_client,
    )
    _patch_repository_function(
        monkeypatch,
        service_module,
        repository_module,
        "get_dietitian_profile_by_id",
        get_dietitian,
    )
    _patch_repository_function(
        monkeypatch,
        service_module,
        repository_module,
        "create_nutrition_plan",
        create,
    )


# Repository flush'ından dönmesi beklenen, DRAFT durumundaki boş plan entity'sini hazırlar.
def _persisted_plan() -> NutritionPlan:
    plan = NutritionPlan(
        id=PLAN_ID,
        client_profile_id=CLIENT_ID,
        dietitian_profile_id=DIETITIAN_ID,
        title="September Plan",
        status=NutritionPlanStatus.DRAFT,
        starts_on=date(2026, 9, 1),
        ends_on=date(2026, 9, 7),
        notes="Initial draft",
    )
    plan.plan_days = []
    return plan


# Mutlu yolda profil sırasını, create delegasyonunu, commit'i ve explicit DTO'yu doğrular.
def test_create_service_validates_profiles_creates_commits_and_maps_dto(
    monkeypatch,
) -> None:
    service_module, repository_module, service, dto_type = _service_contract()
    events: list[str] = []
    session = _SessionSpy(events)
    plan_create = _PlanCreateStub()
    plan = _persisted_plan()

    # İlk adımda client profilinin doğru session ve UUID ile arandığını kaydeder.
    def get_client(received_session, profile_id):
        events.append("client")
        assert (received_session, profile_id) == (session, CLIENT_ID)
        return object()

    # Client bulunduğunda ikinci adım olarak dietitian kontrolünü kaydeder.
    def get_dietitian(received_session, profile_id):
        events.append("dietitian")
        assert (received_session, profile_id) == (session, DIETITIAN_ID)
        return object()

    # İki profil de mevcutsa request DTO'nun repository create'e aynen geçtiğini doğrular.
    def create(received_session, received_create):
        events.append("create")
        assert (received_session, received_create) == (session, plan_create)
        return plan

    _patch_repository_contract(
        monkeypatch,
        service_module,
        repository_module,
        get_client=get_client,
        get_dietitian=get_dietitian,
        create=create,
    )

    result = service(session, plan_create)

    # Olay listesi, transaction commit'inin persistence tamamlandıktan sonra geldiğini kanıtlar.
    assert isinstance(result, dto_type)
    assert events == ["client", "dietitian", "create", "commit"]
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert result.model_dump(mode="json") == {
        "id": str(PLAN_ID),
        "client_profile_id": str(CLIENT_ID),
        "dietitian_profile_id": str(DIETITIAN_ID),
        "title": "September Plan",
        "status": "DRAFT",
        "starts_on": "2026-09-01",
        "ends_on": "2026-09-07",
        "notes": "Initial draft",
        "days": [],
    }


# Client bulunamazsa akışın dietitian sorgusuna veya persistence'a ilerlemesini engeller.
def test_create_service_stops_when_client_profile_is_missing(monkeypatch) -> None:
    service_module, repository_module, service, _ = _service_contract()
    events: list[str] = []
    session = _SessionSpy(events)

    # İlk lookup eksik client senaryosunu üretir.
    def get_client(received_session, profile_id):
        events.append("client")
        return None

    # Çağrılması yasak olan sonraki adımları tek bir fail-fast dublörüyle korur.
    def unexpected(*args, **kwargs):
        pytest.fail("service must stop after the missing client profile")

    _patch_repository_contract(
        monkeypatch,
        service_module,
        repository_module,
        get_client=get_client,
        get_dietitian=unexpected,
        create=unexpected,
    )

    with pytest.raises(ResourceNotFoundException):
        service(session, _PlanCreateStub())

    assert events == ["client"]
    assert session.commit_calls == 0


# Client mevcutken dietitian bulunamazsa create ve commit yapılmamasını doğrular.
def test_create_service_stops_when_dietitian_profile_is_missing(monkeypatch) -> None:
    service_module, repository_module, service, _ = _service_contract()
    events: list[str] = []
    session = _SessionSpy(events)

    # Akışın dietitian kontrolüne ulaşabilmesi için client lookup başarılıdır.
    def get_client(received_session, profile_id):
        events.append("client")
        return object()

    # İkinci lookup eksik dietitian senaryosunu üretir.
    def get_dietitian(received_session, profile_id):
        events.append("dietitian")
        return None

    # Eksik profile rağmen create çağrılırsa testi doğrudan anlaşılır mesajla durdurur.
    def unexpected(*args, **kwargs):
        pytest.fail("service must not create when the dietitian is missing")

    _patch_repository_contract(
        monkeypatch,
        service_module,
        repository_module,
        get_client=get_client,
        get_dietitian=get_dietitian,
        create=unexpected,
    )

    with pytest.raises(ResourceNotFoundException):
        service(session, _PlanCreateStub())

    assert events == ["client", "dietitian"]
    assert session.commit_calls == 0


# Repository create sırasında oluşan hatanın rollback sonrası değişmeden yükselmesini bekler.
def test_create_service_rolls_back_and_reraises_repository_failure(
    monkeypatch,
) -> None:
    service_module, repository_module, service, _ = _service_contract()
    events: list[str] = []
    session = _SessionSpy(events)
    persistence_error = RuntimeError("persistence failed")

    # Hata noktasına ulaşmak için iki profil lookup'ı da başarılı sonuç döndürür.
    def get_client(received_session, profile_id):
        events.append("client")
        return object()

    # Client'tan sonra dietitian kontrolünün de başarılı olmasını sağlar.
    def get_dietitian(received_session, profile_id):
        events.append("dietitian")
        return object()

    # Persistence katmanındaki özgün exception nesnesini üretir.
    def create(received_session, received_create):
        events.append("create")
        raise persistence_error

    _patch_repository_contract(
        monkeypatch,
        service_module,
        repository_module,
        get_client=get_client,
        get_dietitian=get_dietitian,
        create=create,
    )

    with pytest.raises(RuntimeError) as exc_info:
        service(session, _PlanCreateStub())

    assert exc_info.value is persistence_error
    assert events == ["client", "dietitian", "create", "rollback"]
    assert session.commit_calls == 0
    assert session.rollback_calls == 1


# Commit başarısız olduğunda da rollback yapılıp aynı exception'ın korunmasını doğrular.
def test_create_service_rolls_back_and_reraises_commit_failure(
    monkeypatch,
) -> None:
    service_module, repository_module, service, _ = _service_contract()
    events: list[str] = []
    commit_error = RuntimeError("commit failed")
    session = _SessionSpy(events, commit_exception=commit_error)

    # Commit aşamasına kadar ilerlemek için lookup ve create adımları başarılıdır.
    def get_client(received_session, profile_id):
        events.append("client")
        return object()

    # Commit hatasına ulaşabilmek için dietitian lookup'ını başarılı sonuçlandırır.
    def get_dietitian(received_session, profile_id):
        events.append("dietitian")
        return object()

    # Commit öncesindeki persistence adımını başarılı bir planla tamamlar.
    def create(received_session, received_create):
        events.append("create")
        return _persisted_plan()

    _patch_repository_contract(
        monkeypatch,
        service_module,
        repository_module,
        get_client=get_client,
        get_dietitian=get_dietitian,
        create=create,
    )

    with pytest.raises(RuntimeError) as exc_info:
        service(session, _PlanCreateStub())

    assert exc_info.value is commit_error
    assert events == ["client", "dietitian", "create", "commit", "rollback"]
    assert session.commit_calls == 1
    assert session.rollback_calls == 1
