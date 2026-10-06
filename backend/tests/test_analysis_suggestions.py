import os

os.environ["ENV"] = "dev"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-characters"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import analyses as analyses_api
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.dataset import Dataset
from app.models.user import User
from app.services import suggestion_service

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
client = TestClient(app)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def setup_function():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    suggestion_service.clear_suggestion_cache()
    app.dependency_overrides[get_db] = override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def _create_user_and_dataset(dataset_owner_id: int | None = None) -> tuple[int, int]:
    with TestSession() as db:
        user = User(name="Test", email="suggestions@example.com", password_hash="unused", is_verified=True)
        db.add(user)
        db.flush()
        owner_id = dataset_owner_id or user.id
        dataset = Dataset(
            user_id=owner_id,
            filename="sales.csv",
            file_path="not-loaded.csv",
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.commit()
        db.refresh(user)
        db.refresh(dataset)
        return user.id, dataset.id


def test_suggestions_endpoint_requires_owned_dataset_and_returns_questions(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    user_id, dataset_id = _create_user_and_dataset()
    monkeypatch.setattr(
        analyses_api,
        "_load_dataframe",
        lambda _: pd.DataFrame({"Date": ["2025-01-01", "2025-01-02"], "Ventes": [10, 20]}),
    )
    token = create_access_token(str(user_id))

    response = client.get(
        f"/analysis/suggestions?dataset_ids={dataset_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert 3 <= len(response.json()["suggestions"]) <= 6
    assert response.json()["source"] == "rules"
    assert any("Ventes" in question["question"] for question in response.json()["suggestions"])


def test_suggestions_endpoint_rejects_dataset_owned_by_another_user(monkeypatch):
    user_id, _ = _create_user_and_dataset()
    with TestSession() as db:
        other_user = User(name="Other", email="other@example.com", password_hash="unused", is_verified=True)
        db.add(other_user)
        db.flush()
        dataset = Dataset(
            user_id=other_user.id,
            filename="private.csv",
            file_path="not-loaded.csv",
            file_type="csv",
            row_count=1,
            column_count=1,
        )
        db.add(dataset)
        db.commit()
        dataset_id = dataset.id
    monkeypatch.setattr(analyses_api, "_load_dataframe", lambda _: pd.DataFrame({"value": [1]}))
    token = create_access_token(str(user_id))

    response = client.get(
        f"/analysis/suggestions?dataset_ids={dataset_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_refresh_limit_returns_retry_after_header(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    user_id, dataset_id = _create_user_and_dataset()
    monkeypatch.setattr(
        analyses_api,
        "_load_dataframe",
        lambda _: pd.DataFrame({"region": ["Nord", "Sud"], "sales": [2, 5]}),
    )
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    first = client.get(
        f"/analysis/suggestions?dataset_ids={dataset_id}&refresh=true",
        headers=headers,
    )
    second = client.get(
        f"/analysis/suggestions?dataset_ids={dataset_id}&refresh=true",
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "10"
