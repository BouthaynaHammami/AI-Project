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
    app.dependency_overrides[get_db] = override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def test_analysis_code_and_explanation_are_exposed_and_restored_from_history(monkeypatch):
    with TestSession() as db:
        user = User(
            name="Test",
            email="code-history@example.com",
            password_hash="unused",
            is_verified=True,
        )
        db.add(user)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            filename="sales.csv",
            file_path="unused.csv",
            file_type="csv",
            row_count=1,
            column_count=1,
        )
        db.add(dataset)
        db.commit()
        user_id = user.id
        dataset_id = dataset.id

    executed_code = "result = df['amount'].sum()\nprint(result)"
    monkeypatch.setattr(analyses_api, "_load_dataframe", lambda _: pd.DataFrame({"amount": [42]}))
    monkeypatch.setattr(
        analyses_api,
        "analyze_dataset",
        lambda *_args, **_kwargs: {
            "answer": "Le total est 42.",
            "chart_config": None,
            "code": executed_code,
            "retried": True,
            "code_explanation": "Le code additionne les montants et affiche le total.",
        },
    )
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/analysis/ask",
        json={"dataset_ids": [dataset_id], "question": "Quel est le total ?"},
        headers=headers,
    )
    history = client.get("/analysis/history", headers=headers)

    assert response.status_code == 200
    assert response.json()["generated_code"] == executed_code
    assert response.json()["code_retried"] is True
    assert response.json()["code_explanation"] == "Le code additionne les montants et affiche le total."
    assert history.status_code == 200
    assert history.json()["items"][0]["generated_code"] == executed_code
    assert history.json()["items"][0]["code_retried"] is True
    assert history.json()["items"][0]["code_explanation"] == "Le code additionne les montants et affiche le total."
