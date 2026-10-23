from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.main import app
from app.models.analysis import Analysis
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.services.usage_service import month_start_utc, next_month_start_utc

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
client = TestClient(app)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def setup_function():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    limiter.reset()
    app.dependency_overrides[get_db] = _override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def _create_user(role: str = "user", quota: int = 50):
    with TestSession() as db:
        user = User(
            name="Usage tester",
            email=f"usage-{uuid4()}@example.test",
            password_hash="unused",
            is_verified=True,
            role=role,
            monthly_quota=quota,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(str(user.id), user.token_version)
        return user.id, {"Authorization": f"Bearer {token}"}


def test_monthly_quota_blocks_analysis_and_reports_reset_date():
    user_id, headers = _create_user(quota=1)
    with TestSession() as db:
        db.add(Analysis(
            user_id=user_id,
            dataset_id=None,
            question="Existing",
            answer="Already consumed",
            result_type="text",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()

    usage = client.get("/usage/me", headers=headers)
    blocked = client.post(
        "/analysis/ask",
        json={"dataset_ids": [999], "question": "Analyse"},
        headers=headers,
    )

    assert usage.status_code == 200
    assert usage.json()["used"] == 1
    assert usage.json()["quota"] == 1
    assert usage.json()["unit"] == "analyses"
    assert datetime.fromisoformat(usage.json()["reset_at"]).day == 1
    assert blocked.status_code == 429
    assert "quota mensuel" in blocked.json()["detail"]
    assert int(blocked.headers["retry-after"]) > 0


def test_month_boundaries_reset_including_december_rollover():
    december = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
    assert month_start_utc(december) == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert next_month_start_utc(december) == datetime(2027, 1, 1, tzinfo=timezone.utc)


def test_failed_server_side_usage_does_not_consume_monthly_quota():
    user_id, headers = _create_user(quota=1)
    with TestSession() as db:
        db.add(UsageEvent(
            user_id=user_id,
            type="analysis",
            tokens_in=0,
            tokens_out=0,
            model=None,
            status="error",
        ))
        db.commit()

    rejected_dataset = client.post(
        "/analysis/ask",
        json={"dataset_ids": [999], "question": "Analyse"},
        headers=headers,
    )
    usage = client.get("/usage/me", headers=headers)

    assert rejected_dataset.status_code == 404
    assert usage.json()["used"] == 0


def test_analysis_route_applies_per_user_requests_per_minute_limit():
    _, headers = _create_user()
    responses = [
        client.post(
            "/analysis/ask",
            json={"dataset_ids": [999], "question": f"Question {index}"},
            headers=headers,
        )
        for index in range(6)
    ]

    assert all(response.status_code == 404 for response in responses[:5])
    assert responses[5].status_code == 429
    assert int(responses[5].headers["retry-after"]) > 0


def test_non_admin_cannot_access_admin_routes_and_admin_can_manage_quota():
    user_id, user_headers = _create_user()
    denied_users = client.get("/admin/users", headers=user_headers)
    denied_stats = client.get("/admin/stats", headers=user_headers)
    admin_id, admin_headers = _create_user(role="admin")

    assert denied_users.status_code == 403
    assert denied_stats.status_code == 403
    updated = client.patch(f"/admin/users/{user_id}", json={"monthly_quota": 75}, headers=admin_headers)
    users = client.get("/admin/users", headers=admin_headers)
    stats = client.get("/admin/stats", headers=admin_headers)

    assert updated.status_code == 200
    assert updated.json()["monthly_quota"] == 75
    assert users.status_code == 200
    assert any(user["id"] == admin_id for user in users.json())
    assert stats.status_code == 200
    assert {"analyses_today", "error_rate", "like_rate", "tokens_in", "tokens_out", "daily"} <= stats.json().keys()


def test_usage_event_token_totals_count_only_successful_usage():
    user_id, headers = _create_user()
    with TestSession() as db:
        db.add_all([
            UsageEvent(
                user_id=user_id,
                type="analysis",
                tokens_in=120,
                tokens_out=80,
                model="example-model",
                status="success",
            ),
            UsageEvent(
                user_id=user_id,
                type="analysis",
                tokens_in=999,
                tokens_out=999,
                model="example-model",
                status="error",
            ),
        ])
        db.commit()
    usage = client.get("/usage/me", headers=headers)
    assert usage.status_code == 200
    assert usage.json()["used"] == 1
    assert usage.json()["tokens_in"] == 120
    assert usage.json()["tokens_out"] == 80
