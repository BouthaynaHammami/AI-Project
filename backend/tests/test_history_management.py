from uuid import uuid4

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.user import User
from app.services.file_service import UPLOAD_DIR

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
    app.dependency_overrides[get_db] = _override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def _headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def _seed():
    with TestSession() as db:
        owner = User(name="A", email=f"a-{uuid4()}@example.test", password_hash="unused", is_verified=True)
        other = User(name="B", email=f"b-{uuid4()}@example.test", password_hash="unused", is_verified=True)
        db.add_all([owner, other])
        db.flush()
        UPLOAD_DIR.mkdir(exist_ok=True)
        file_path = (UPLOAD_DIR / f"{uuid4().hex}.csv").resolve()
        pd.DataFrame({"value": [1, 2]}).to_csv(file_path, index=False)
        dataset = Dataset(
            user_id=owner.id,
            filename=file_path.name,
            file_path=str(file_path),
            file_type="csv",
            row_count=2,
            column_count=1,
        )
        db.add(dataset)
        db.flush()
        analyses = [
            Analysis(
                user_id=owner.id,
                dataset_id=dataset.id,
                question=question,
                answer=answer,
                result_type="text",
            )
            for question, answer in (
                ("Ventes janvier", "Le total vaut 50."),
                ("Recherche 100% exacte", "Réponse secondaire"),
                ("literal_under_score", "Réponse avec terme distinctif"),
            )
        ]
        db.add_all(analyses)
        db.commit()
        return owner.id, other.id, dataset.id, [item.id for item in analyses], file_path


def test_history_search_pagination_favorites_and_soft_delete():
    owner_id, _, _, analysis_ids, _ = _seed()
    headers = _headers(owner_id)
    with TestSession() as db:
        db.get(Analysis, analysis_ids[1]).is_favorite = True
        db.commit()

    by_title = client.get("/analysis/history", params={"q": "VENTES JANVIER"}, headers=headers)
    by_answer = client.get("/analysis/history", params={"q": "terme distinctif"}, headers=headers)
    escaped_wildcard = client.get("/analysis/history", params={"q": "%"}, headers=headers)
    escaped_underscore = client.get("/analysis/history", params={"q": "_"}, headers=headers)
    favorites = client.get("/analysis/history", params={"favorite": "true"}, headers=headers)
    favorite_search = client.get(
        "/analysis/history",
        params={"q": "100%", "favorite": "true"},
        headers=headers,
    )
    first_page = client.get("/analysis/history", params={"limit": 2, "offset": 0}, headers=headers)
    second_page = client.get("/analysis/history", params={"limit": 2, "offset": 2}, headers=headers)
    bounded_limit = client.get("/analysis/history", params={"limit": 1000}, headers=headers)
    deleted = client.delete(f"/analysis/{analysis_ids[0]}", headers=headers)
    history_after_delete = client.get("/analysis/history", headers=headers)
    restored = client.post(f"/analysis/{analysis_ids[0]}/restore", headers=headers)

    assert by_title.json()["total"] == 1
    assert by_answer.json()["total"] == 1
    assert escaped_wildcard.json()["total"] == 1
    assert escaped_underscore.json()["total"] == 1
    assert favorites.json()["items"][0]["id"] == analysis_ids[1]
    assert favorite_search.json()["total"] == 1
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 2
    assert first_page.json()["has_more"] is True
    assert len(second_page.json()["items"]) == 1
    assert second_page.json()["has_more"] is False
    assert bounded_limit.status_code == 422
    assert deleted.status_code == 204
    assert analysis_ids[0] not in {item["id"] for item in history_after_delete.json()["items"]}
    assert restored.status_code == 200


def test_foreign_user_cannot_access_analysis_or_dataset_and_unauthenticated_is_rejected():
    owner_id, other_id, dataset_id, analysis_ids, file_path = _seed()
    foreign_headers = _headers(other_id)

    assert client.get("/analysis/history", headers=foreign_headers).json()["items"] == []
    assert client.patch(f"/analysis/{analysis_ids[0]}", json={"title": "Intrusion"}, headers=foreign_headers).status_code == 404
    assert client.delete(f"/analysis/{analysis_ids[0]}", headers=foreign_headers).status_code == 404
    assert client.post(f"/analysis/{analysis_ids[0]}/restore", headers=foreign_headers).status_code == 404
    assert client.delete(f"/files/{dataset_id}", headers=foreign_headers).status_code == 404
    assert file_path.exists()
    assert client.get("/analysis/history").status_code == 401
    assert client.patch(f"/analysis/{analysis_ids[0]}", json={"is_favorite": True}).status_code == 401
    assert client.delete(f"/analysis/{analysis_ids[0]}").status_code == 401
    assert client.post(f"/analysis/{analysis_ids[0]}/restore").status_code == 401
    assert client.delete(f"/files/{dataset_id}").status_code == 401
    assert owner_id != other_id


def test_patch_title_validation_and_favorite_persistence():
    owner_id, _, _, analysis_ids, _ = _seed()
    headers = _headers(owner_id)

    updated = client.patch(
        f"/analysis/{analysis_ids[0]}",
        json={"title": "  Ventes 2026  ", "is_favorite": True},
        headers=headers,
    )
    empty = client.patch(f"/analysis/{analysis_ids[1]}", json={"title": ""}, headers=headers)
    too_long = client.patch(f"/analysis/{analysis_ids[2]}", json={"title": "x" * 121}, headers=headers)

    assert updated.status_code == 200
    assert updated.json()["title"] == "Ventes 2026"
    assert updated.json()["is_favorite"] is True
    assert client.get("/analysis/history", params={"q": "ventes 2026"}, headers=headers).json()["total"] == 1
    assert empty.status_code == 200
    assert empty.json()["title"] is None
    assert too_long.status_code == 422


def test_delete_and_restore_remove_the_whole_grouped_conversation():
    owner_id, _, dataset_id, analysis_ids, _ = _seed()
    headers = _headers(owner_id)
    with TestSession() as db:
        conversation = Conversation(
            user_id=owner_id,
            title="Ventes",
            dataset_ids=f"[{dataset_id}]",
        )
        db.add(conversation)
        db.flush()
        for analysis_id in analysis_ids[:2]:
            db.get(Analysis, analysis_id).conversation_id = conversation.id
        db.commit()

    deleted = client.delete(f"/analysis/{analysis_ids[0]}", headers=headers)
    history_after_delete = client.get("/analysis/history", headers=headers).json()
    restored = client.post(f"/analysis/{analysis_ids[0]}/restore", headers=headers)
    history_after_restore = client.get("/analysis/history", headers=headers).json()

    assert deleted.status_code == 204
    assert {item["id"] for item in history_after_delete["items"]} == {analysis_ids[2]}
    assert restored.status_code == 200
    assert {item["id"] for item in history_after_restore["items"]} == set(analysis_ids)


def test_dataset_delete_conflict_and_cascade_soft_deletes_analyses():
    owner_id, _, dataset_id, analysis_ids, file_path = _seed()
    headers = _headers(owner_id)
    conflict = client.delete(f"/files/{dataset_id}", headers=headers)

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["analysis_count"] == 3
    assert file_path.exists()

    deleted = client.delete(f"/files/{dataset_id}?cascade=true", headers=headers)

    assert deleted.status_code == 204
    assert not file_path.exists()
    with TestSession() as db:
        assert all(db.get(Analysis, item_id).deleted_at is not None for item_id in analysis_ids)
        assert all(db.get(Analysis, item_id).dataset_id is None for item_id in analysis_ids)
