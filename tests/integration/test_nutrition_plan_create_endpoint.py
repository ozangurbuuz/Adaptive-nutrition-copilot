import asyncio
import uuid

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.orm import get_database_session
from app.core.security import UserRole
from app.main import app
from app.models.enums import NutritionPlanStatus
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay
from app.models.profiles import ClientProfile, DietitianProfile
from app.models.user import User


# Bu dosyadaki testlerin güvenli PostgreSQL fixture'larıyla çalışması gerektiğini işaretler.
pytestmark = pytest.mark.integration


# Her test için birbirine bağlı gerçek bir client ve dietitian profili oluşturur.
def _profiles(session: Session) -> tuple[ClientProfile, DietitianProfile]:
    client = ClientProfile(
        user=User(
            email=f"create-client-{uuid.uuid4()}@example.test",
            role=UserRole.CLIENT,
        ),
        display_name="Create Client",
    )
    dietitian = DietitianProfile(
        user=User(
            email=f"create-dietitian-{uuid.uuid4()}@example.test",
            role=UserRole.DIETITIAN,
        ),
        display_name="Create Dietitian",
    )
    session.add_all([client, dietitian])
    session.flush()
    return client, dietitian


# Endpoint'in kabul ettiği tam ve geçerli create body’sini verilen profil UUID'leriyle kurar.
def _payload(
    client_id: uuid.UUID,
    dietitian_id: uuid.UUID,
) -> dict[str, object]:
    return {
        "client_profile_id": str(client_id),
        "dietitian_profile_id": str(dietitian_id),
        "title": "September Plan",
        "starts_on": "2026-09-01",
        "ends_on": "2026-09-07",
        "notes": "Initial draft",
    }


# Aynı transactional session'ı FastAPI dependency override üzerinden endpoint'e verir.
async def _request(
    method: str,
    path: str,
    session: Session,
    **kwargs,
) -> httpx.Response:
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_database_session] = lambda: session
    try:
        # Uygulama exception'larının merkezi handler'lar üzerinden HTTP cevabına dönüşmesini sağlar.
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


# Başarısız create denemelerinin yeni satır bırakmadığını karşılaştırmak için planları sayar.
def _plan_count(session: Session) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(NutritionPlan)) or 0


# POST ile boş DRAFT planı persist eder ve mevcut GET endpoint'iyle aynı sözleşmeyi geri okur.
def test_create_endpoint_persists_empty_draft_and_detail_get_reads_it(
    db_session: Session,
) -> None:
    client, dietitian = _profiles(db_session)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/nutrition-plans",
            db_session,
            json=_payload(client.id, dietitian.id),
        )
    )

    # HTTP response yalnız mevcut NutritionPlanRead alanlarını ve boş days listesini içermelidir.
    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "client_profile_id": str(client.id),
        "dietitian_profile_id": str(dietitian.id),
        "title": "September Plan",
        "status": "DRAFT",
        "starts_on": "2026-09-01",
        "ends_on": "2026-09-07",
        "notes": "Initial draft",
        "days": [],
    }
    plan_id = uuid.UUID(body["id"])
    plan = db_session.get(NutritionPlan, plan_id)
    assert plan is not None
    assert plan.status is NutritionPlanStatus.DRAFT

    # İlk create diliminin hiçbir PlanDay, Meal veya MealItem üretmediğini DB seviyesinde kanıtlar.
    day_count = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(PlanDay)
        .where(PlanDay.nutrition_plan_id == plan_id)
    )
    meal_count = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Meal)
        .join(PlanDay)
        .where(PlanDay.nutrition_plan_id == plan_id)
    )
    item_count = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(MealItem)
        .join(Meal)
        .join(PlanDay)
        .where(PlanDay.nutrition_plan_id == plan_id)
    )
    assert (day_count, meal_count, item_count) == (0, 0, 0)

    # Yeni ID'nin mevcut detail endpoint'i tarafından aynı response sözleşmesiyle okunmasını sınar.
    detail_response = asyncio.run(
        _request(
            "GET",
            f"/api/v1/nutrition-plans/{plan_id}",
            db_session,
        )
    )

    assert detail_response.status_code == 200
    assert detail_response.json() == body


# Client ve dietitian eksikliği için aynı 404/no-insert davranışını ayrı ayrı doğrular.
@pytest.mark.parametrize("missing_profile", ["client", "dietitian"])
def test_create_endpoint_returns_404_without_inserting_for_unknown_profile(
    db_session: Session,
    missing_profile: str,
) -> None:
    client, dietitian = _profiles(db_session)
    # Parametreye göre yalnızca bir FK'yi bilinmeyen UUID ile değiştirir.
    client_id = uuid.uuid4() if missing_profile == "client" else client.id
    dietitian_id = (
        uuid.uuid4() if missing_profile == "dietitian" else dietitian.id
    )
    before_count = _plan_count(db_session)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/nutrition-plans",
            db_session,
            json=_payload(client_id, dietitian_id),
        )
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "Requested resource was not found",
            "details": None,
        }
    }
    # Domain 404 cevabı üretildikten sonra nutrition_plans tablosu değişmemelidir.
    assert _plan_count(db_session) == before_count


# Ters tarih aralığının repository'ye ulaşmadan 422 üretmesini ve DB'yi değiştirmemesini sınar.
def test_create_endpoint_rejects_reversed_dates_without_inserting(
    db_session: Session,
) -> None:
    client, dietitian = _profiles(db_session)
    payload = {
        **_payload(client.id, dietitian.id),
        "starts_on": "2026-09-07",
        "ends_on": "2026-09-01",
    }
    before_count = _plan_count(db_session)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/nutrition-plans",
            db_session,
            json=payload,
        )
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # Schema validation başarısız olduğunda hiçbir plan satırı eklenmediğini doğrular.
    assert _plan_count(db_session) == before_count
