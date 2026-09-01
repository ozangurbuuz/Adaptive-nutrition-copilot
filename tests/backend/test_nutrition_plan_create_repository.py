import importlib
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.sql import Select

from app.models.nutrition_plan import NutritionPlan
from app.models.profiles import ClientProfile, DietitianProfile


# Sabit UUID'ler sorgu parametrelerini ve oluşturulan entity alanlarını netleştirir.
CLIENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
DIETITIAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


# Repository testini henüz RED olan gerçek schema sınıfından bağımsız tutan request dublörüdür.
@dataclass(frozen=True)
class _PlanCreateStub:
    client_profile_id: uuid.UUID = CLIENT_ID
    dietitian_profile_id: uuid.UUID = DIETITIAN_ID
    title: str = "September Plan"
    starts_on: date | None = date(2026, 9, 1)
    ends_on: date | None = date(2026, 9, 7)
    notes: str | None = "Initial draft"


# Session üzerindeki okuma, yazma ve transaction çağrılarını ayrı ayrı kaydeder.
class _SessionSpy:
    # Lookup dönüşünü ve izlenecek bütün çağrı sayaçlarını başlangıç durumuna getirir.
    def __init__(self, lookup_value=None) -> None:
        self.lookup_value = lookup_value
        self.get_calls = []
        self.statements = []
        self.add_calls = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.refresh_calls = 0

    # session.get kullanan lookup implementasyonlarının model ve UUID çağrısını yakalar.
    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return self.lookup_value

    # select + scalar kullanan alternatif repository stilini de gözlemler.
    def scalar(self, statement):
        self.statements.append(statement)
        return self.lookup_value

    # select + execute kullanan implementasyonun statement'ını ve dönüşünü taklit eder.
    def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult(self.lookup_value)

    # Oluşturulan ORM entity'sinin session'a kaç kez eklendiğini kaydeder.
    def add(self, entity) -> None:
        self.add_calls.append(entity)

    # ORM default'larını üretmek için beklenen flush çağrısını sayar.
    def flush(self) -> None:
        self.flush_calls += 1

    # Repository'nin transaction sahibi olmadığını kanıtlamak için commit'i izler.
    def commit(self) -> None:
        self.commit_calls += 1

    # Hata yönetiminin service'te kalması gerektiği için rollback'i izler.
    def rollback(self) -> None:
        self.rollback_calls += 1

    # Gereksiz refresh çağrısı yapılmadığını doğrulamak için kullanılır.
    def refresh(self, *args, **kwargs) -> None:
        self.refresh_calls += 1


# execute sonucundan tek bir entity veya None döndüren küçük SQLAlchemy sonuç dublörüdür.
class _ScalarResult:
    # Repository'ye geri verilecek entity veya None değerini saklar.
    def __init__(self, value) -> None:
        self.value = value

    # Farklı repository okuma stillerinin aynı sentinel değeri almasını sağlar.
    def scalar_one_or_none(self):
        return self.value

    # one_or_none kullanan repository implementasyonuna aynı sonucu verir.
    def one_or_none(self):
        return self.value

    # first kullanan repository implementasyonuna aynı sonucu verir.
    def first(self):
        return self.value


# Eksik repository fonksiyonlarını collection error yerine açıklayıcı RED failure yapar.
def _repository_function(name: str):
    module = importlib.import_module("app.repositories.nutrition_plan")
    function = getattr(module, name, None)
    assert callable(function), f"{name} repository function is missing"
    return function


# Lookup'ın hem session.get hem select tabanlı geçerli implementasyonlarını doğrular.
def _assert_lookup_contract(
    function_name: str,
    model,
    record_id: uuid.UUID,
    expected_value,
) -> None:
    function = _repository_function(function_name)
    session = _SessionSpy(expected_value)

    result = function(session, record_id)

    assert result is expected_value
    # Kullanılan sorgu stiline göre doğru ORM modeli ile UUID'nin taşındığını kontrol eder.
    if session.get_calls:
        assert session.get_calls == [((model, record_id), {})]
        assert session.statements == []
    else:
        assert len(session.statements) == 1
        statement = session.statements[0]
        assert isinstance(statement, Select)
        assert statement.column_descriptions[0]["entity"] is model
        assert record_id in statement.compile().params.values()
    # Salt-okunur lookup fonksiyonlarının hiçbir yazma veya transaction yan etkisi olmamalıdır.
    assert session.add_calls == []
    assert session.flush_calls == 0
    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert session.refresh_calls == 0


# Client lookup'ının doğru modeli sorgulayıp bulunan entity'yi aynen döndürmesini bekler.
def test_get_client_profile_by_id_queries_client_profile_and_returns_entity() -> None:
    profile = object()
    _assert_lookup_contract(
        "get_client_profile_by_id",
        ClientProfile,
        CLIENT_ID,
        profile,
    )


# Olmayan client profilinin exception yerine None olarak repository'den dönmesini bekler.
def test_get_client_profile_by_id_returns_none() -> None:
    _assert_lookup_contract(
        "get_client_profile_by_id",
        ClientProfile,
        CLIENT_ID,
        None,
    )


# Dietitian lookup'ının doğru modeli ve istenen UUID'yi kullanmasını doğrular.
def test_get_dietitian_profile_by_id_queries_dietitian_and_returns_entity() -> None:
    profile = object()
    _assert_lookup_contract(
        "get_dietitian_profile_by_id",
        DietitianProfile,
        DIETITIAN_ID,
        profile,
    )


# Olmayan dietitian profilinin service tarafından yorumlanmak üzere None dönmesini bekler.
def test_get_dietitian_profile_by_id_returns_none() -> None:
    _assert_lookup_contract(
        "get_dietitian_profile_by_id",
        DietitianProfile,
        DIETITIAN_ID,
        None,
    )


# Request alanlarından boş bir NutritionPlan kurup tek add ve tek flush yapılmasını sınar.
def test_create_repository_builds_empty_plan_adds_and_flushes_once() -> None:
    create = _repository_function("create_nutrition_plan")
    session = _SessionSpy()
    plan_create = _PlanCreateStub()

    result = create(session, plan_create)

    assert isinstance(result, NutritionPlan)
    assert session.add_calls == [result]
    assert session.flush_calls == 1
    assert result.client_profile_id == CLIENT_ID
    assert result.dietitian_profile_id == DIETITIAN_ID
    assert result.title == "September Plan"
    assert result.starts_on == date(2026, 9, 1)
    assert result.ends_on == date(2026, 9, 7)
    assert result.notes == "Initial draft"
    assert list(result.plan_days) == []


# Commit, rollback ve refresh sorumluluklarının repository'ye taşınmasını engeller.
def test_create_repository_does_not_own_transaction_or_refresh() -> None:
    create = _repository_function("create_nutrition_plan")
    session = _SessionSpy()

    create(session, _PlanCreateStub())

    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert session.refresh_calls == 0
