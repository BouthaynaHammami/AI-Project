import os

os.environ["ENV"] = "dev"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-characters"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.feedback import Feedback
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


def _create_user_and_analysis() -> tuple[int, int]:
    with TestSession() as db:
        user = User(
            name="Test",
            email="feedback@example.com",
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
        db.flush()
        conversation = Conversation(
            user_id=user.id,
            title="Analyse des ventes",
            dataset_ids=f"[{dataset.id}]",
        )
        db.add(conversation)
        db.flush()
        analysis = Analysis(
            user_id=user.id,
            conversation_id=conversation.id,
            dataset_id=dataset.id,
            question="Quel est le total des ventes ?",
            answer="Le total est 42.",
            result_type="text",
        )
        db.add(analysis)
        db.commit()
        return user.id, analysis.id


def _headers(user_id: int) -> dict[str, str]:
    token = create_access_token(str(user_id))
    return {"Authorization": f"Bearer {token}"}


def test_database_enforces_one_feedback_per_analysis_and_user():
    user_id, analysis_id = _create_user_and_analysis()
    with TestSession() as db:
        db.add(Feedback(analysis_id=analysis_id, user_id=user_id, rating=1))
        db.commit()
        db.add(Feedback(analysis_id=analysis_id, user_id=user_id, rating=-1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(Feedback).filter_by(analysis_id=analysis_id, user_id=user_id).count() == 1


def test_only_analysis_owner_can_add_or_remove_feedback():
    user_id, analysis_id = _create_user_and_analysis()
    with TestSession() as db:
        other_user = User(
            name="Other",
            email="other-feedback@example.com",
            password_hash="unused",
            is_verified=True,
        )
        db.add(other_user)
        db.commit()
        other_user_id = other_user.id

    headers = _headers(other_user_id)
    put_response = client.put(
        f"/analysis/{analysis_id}/feedback",
        json={"rating": 1},
        headers=headers,
    )
    delete_response = client.delete(
        f"/analysis/{analysis_id}/feedback",
        headers=headers,
    )

    assert put_response.status_code == 404
    assert delete_response.status_code == 404
    with TestSession() as db:
        assert db.query(Feedback).filter_by(analysis_id=analysis_id).count() == 0


def test_vote_is_replaced_and_included_in_history_and_stats():
    user_id, analysis_id = _create_user_and_analysis()
    headers = _headers(user_id)

    first = client.put(
        f"/analysis/{analysis_id}/feedback",
        json={"rating": -1, "comment": "Mauvais chiffre"},
        headers=headers,
    )
    replaced = client.put(
        f"/analysis/{analysis_id}/feedback",
        json={"rating": 1, "comment": None},
        headers=headers,
    )
    history = client.get("/analysis/history", headers=headers)
    stats = client.get("/analysis/stats", headers=headers)

    assert first.status_code == 200
    assert replaced.status_code == 200
    assert replaced.json()["id"] == first.json()["id"]
    assert replaced.json()["rating"] == 1
    assert history.json()["items"][0]["feedback"]["rating"] == 1
    assert stats.json() == {
        "like_rate": 100.0,
        "total_votes": 1,
        "recent_negative_questions": [],
    }


def test_feedback_can_be_deleted_and_stats_include_recent_negative_questions():
    user_id, analysis_id = _create_user_and_analysis()
    headers = _headers(user_id)
    voted = client.put(
        f"/analysis/{analysis_id}/feedback",
        json={"rating": -1, "comment": "Ne répond pas à la question"},
        headers=headers,
    )
    stats = client.get("/analysis/stats", headers=headers)
    history_before_delete = client.get("/analysis/history", headers=headers)
    conversation_id = None
    with TestSession() as db:
        conversation_id = db.query(Analysis).filter_by(id=analysis_id).one().conversation_id
    conversation = client.get(f"/conversations/{conversation_id}", headers=headers)
    deleted = client.delete(f"/analysis/{analysis_id}/feedback", headers=headers)
    history_after_delete = client.get("/analysis/history", headers=headers)

    assert voted.status_code == 200
    assert stats.json()["like_rate"] == 0.0
    assert stats.json()["total_votes"] == 1
    assert stats.json()["recent_negative_questions"][0]["question"] == "Quel est le total des ventes ?"
    assert history_before_delete.json()["items"][0]["feedback"]["comment"] == "Ne répond pas à la question"
    restored_feedback = conversation.json()["messages"][1]
    assert restored_feedback["analysis_id"] == analysis_id
    assert restored_feedback["result_data"]["feedback"] == {
        "rating": -1,
        "comment": "Ne répond pas à la question",
    }
    assert deleted.status_code == 204
    assert history_after_delete.json()["items"][0]["feedback"] is None
    with TestSession() as db:
        assert db.query(Feedback).filter_by(analysis_id=analysis_id, user_id=user_id).count() == 0
