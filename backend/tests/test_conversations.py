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
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.main import app
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.message import Message
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
    limiter.reset()
    app.dependency_overrides[get_db] = override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def _create_user_dataset_and_conversation() -> tuple[int, int, int, int]:
    with TestSession() as db:
        owner = User(name="Owner", email="owner-conversation@example.com", password_hash="unused", is_verified=True)
        requester = User(name="Requester", email="requester-conversation@example.com", password_hash="unused", is_verified=True)
        db.add_all([owner, requester])
        db.flush()
        dataset = Dataset(
            user_id=requester.id,
            filename="sales.csv",
            file_path="unused.csv",
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        conversation = Conversation(
            user_id=owner.id,
            title="Conversation privée",
            dataset_ids="[1]",
        )
        db.add_all([dataset, conversation])
        db.commit()
        return owner.id, requester.id, dataset.id, conversation.id


def _headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def test_conversation_id_from_another_user_is_rejected(monkeypatch):
    _, requester_id, dataset_id, foreign_conversation_id = _create_user_dataset_and_conversation()
    monkeypatch.setattr(analyses_api, "analyze_dataset", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not call LLM")))

    response = client.post(
        "/analysis/ask",
        json={
            "dataset_ids": [dataset_id],
            "conversation_id": foreign_conversation_id,
            "question": "Et en Sud ?",
        },
        headers=_headers(requester_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation introuvable."


def test_analysis_creates_and_reuses_conversation_and_history_groups_metadata(monkeypatch):
    with TestSession() as db:
        user = User(name="User", email="conversation@example.com", password_hash="unused", is_verified=True)
        db.add(user)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            filename="sales.csv",
            file_path="unused.csv",
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.commit()
        user_id, dataset_id = user.id, dataset.id

    combined_dataframe = pd.DataFrame({"region": ["Nord", "Sud"], "sales": [10, 20]})
    monkeypatch.setattr(
        analyses_api,
        "_prepare_datasets_for_llm",
        lambda _: (combined_dataframe, combined_dataframe.copy(), [], {"column_count": 0}),
    )
    received_history = []

    def fake_analyze(_question, _dataframe, **kwargs):
        received_history.append(kwargs.get("conversation_history", []))
        return {
            "answer": "Résultat.",
            "chart_config": None,
            "code": "print('résultat')",
            "retried": False,
            "code_explanation": "Le code affiche le résultat.",
        }

    monkeypatch.setattr(analyses_api, "analyze_dataset", fake_analyze)
    headers = _headers(user_id)
    first = client.post(
        "/analysis/ask",
        json={"dataset_ids": [dataset_id], "question": "Quel est le meilleur produit ?"},
        headers=headers,
    )
    conversation_id = first.json()["conversation_id"]
    second = client.post(
        "/analysis/ask",
        json={
            "dataset_ids": [dataset_id],
            "conversation_id": conversation_id,
            "question": "Et en Sud ?",
        },
        headers=headers,
    )
    history = client.get("/analysis/history", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert received_history == [
        [],
        [{
            "question": "Quel est le meilleur produit ?",
            "answer": "Résultat.",
            "code": "print('résultat')",
        }],
    ]
    assert len(history.json()["items"]) == 2
    assert {item["conversation_id"] for item in history.json()["items"]} == {conversation_id}
    assert {item["conversation_title"] for item in history.json()["items"]} == {"Quel est le meilleur produit ?"}
    assert all(item["conversation_dataset_ids"] == [dataset_id] for item in history.json()["items"])


def test_conversation_message_route_keeps_all_turns_in_one_owned_conversation(monkeypatch):
    with TestSession() as db:
        user = User(name="User", email="conversation-messages@example.com", password_hash="unused", is_verified=True)
        db.add(user)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            filename="sales.csv",
            file_path="unused.csv",
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.commit()
        user_id, dataset_id = user.id, dataset.id

    dataframe = pd.DataFrame({"region": ["Nord", "Sud"], "sales": [10, 20]})
    monkeypatch.setattr(
        analyses_api,
        "_prepare_datasets_for_llm",
        lambda _: (dataframe, dataframe.copy(), [], {"column_count": 0}),
    )
    received_history = []

    def fake_analyze(question, _dataframe, **kwargs):
        received_history.append(kwargs.get("conversation_history", []))
        return {
            "answer": f"Réponse à {question}",
            "chart_config": None,
            "code": None,
            "retried": False,
            "code_explanation": None,
        }

    monkeypatch.setattr(analyses_api, "analyze_dataset", fake_analyze)
    headers = _headers(user_id)
    created = client.post("/conversations", json={"dataset_ids": [dataset_id]}, headers=headers)
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    responses = [
        client.post(
            f"/conversations/{conversation_id}/messages",
            json={"dataset_ids": [dataset_id], "question": f"Question {index}"},
            headers=headers,
        )
        for index in range(1, 6)
    ]
    detail = client.get(f"/conversations/{conversation_id}", headers=headers)
    conversations = client.get("/conversations", headers=headers)

    assert all(response.status_code == 200 for response in responses)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Question 1"
    assert len(detail.json()["messages"]) == 10
    assert [message["role"] for message in detail.json()["messages"]] == ["user", "assistant"] * 5
    assert len(conversations.json()) == 1
    assert len(received_history[0]) == 0
    assert all(
        all(item["question"].startswith("Question ") for item in history)
        for history in received_history
    )
    with TestSession() as db:
        assert db.query(Analysis).filter_by(conversation_id=conversation_id).count() == 5
        assert db.query(Message).filter_by(conversation_id=conversation_id).count() == 10


def test_conversation_actions_update_and_delete_only_owned_conversation():
    owner_id, requester_id, _, conversation_id = _create_user_dataset_and_conversation()
    owner_headers = _headers(owner_id)
    requester_headers = _headers(requester_id)

    denied_update = client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "Not allowed"},
        headers=requester_headers,
    )
    updated = client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "Renamed", "is_favorite": True},
        headers=owner_headers,
    )
    denied = client.get(f"/conversations/{conversation_id}", headers=requester_headers)
    deleted = client.delete(f"/conversations/{conversation_id}", headers=owner_headers)
    missing = client.get(f"/conversations/{conversation_id}", headers=owner_headers)

    assert updated.status_code == 200
    assert denied_update.status_code == 404
    assert updated.json()["title"] == "Renamed"
    assert updated.json()["is_favorite"] is True
    assert denied.status_code == 404
    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_llm_context_does_not_cross_conversation_boundaries(monkeypatch):
    with TestSession() as db:
        user = User(name="User", email="isolated-conversations@example.com", password_hash="unused", is_verified=True)
        db.add(user)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            filename="sales.csv",
            file_path="unused.csv",
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.commit()
        user_id, dataset_id = user.id, dataset.id

    dataframe = pd.DataFrame({"region": ["Nord"], "sales": [10]})
    monkeypatch.setattr(
        analyses_api,
        "_prepare_datasets_for_llm",
        lambda _: (dataframe, dataframe.copy(), [], {"column_count": 0}),
    )
    received_history = []
    monkeypatch.setattr(
        analyses_api,
        "analyze_dataset",
        lambda _question, _dataframe, **kwargs: (
            received_history.append(kwargs.get("conversation_history", []))
            or {
                "answer": "Résultat.",
                "chart_config": None,
                "code": None,
                "retried": False,
                "code_explanation": None,
            }
        ),
    )
    headers = _headers(user_id)
    first = client.post("/conversations", json={"dataset_ids": [dataset_id]}, headers=headers).json()
    second = client.post("/conversations", json={"dataset_ids": [dataset_id]}, headers=headers).json()

    for conversation, question in ((first, "Question privée A"), (second, "Question privée B")):
        response = client.post(
            f"/conversations/{conversation['id']}/messages",
            json={"dataset_ids": [dataset_id], "question": question},
            headers=headers,
        )
        assert response.status_code == 200

    assert received_history == [[], []]
