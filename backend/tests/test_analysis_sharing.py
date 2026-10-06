import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.analysis import Analysis
from app.models.share_link import ShareLink
from app.models.user import User

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


def _seed():
    with TestSession() as db:
        owner = User(
            name="Private Owner Name",
            email=f"owner-{uuid4()}@example.test",
            password_hash="unused",
            is_verified=True,
        )
        db.add(owner)
        db.flush()
        analysis = Analysis(
            user_id=owner.id,
            dataset_id=None,
            question="What is the total?",
            answer="The total is 42.",
            result_type="text",
            result_data='{"private": "result rows"}',
            chart_config='{"type":"bar","title":"Totals","labels":["A"],"values":[42]}',
            generated_code="private generated code",
        )
        db.add(analysis)
        db.commit()
        token = create_access_token(str(owner.id), owner.token_version)
        return owner.id, analysis.id, {"Authorization": f"Bearer {token}"}, token


def test_public_link_stores_only_hash_and_exposes_only_safe_analysis_fields():
    _, analysis_id, headers, _ = _seed()
    created = client.post(
        f"/analysis/{analysis_id}/share",
        json={"expires_in_days": 7},
        headers=headers,
    )

    assert created.status_code == 201
    share_token = created.json()["token"]
    with TestSession() as db:
        share = db.query(ShareLink).one()
        assert share.token_hash == hashlib.sha256(share_token.encode()).hexdigest()
        assert share.token_hash != share_token
        assert share.created_by

    public = client.get(f"/public/analysis/{share_token}")
    assert public.status_code == 200
    assert set(public.json()) == {"question", "answer", "chart_config", "created_at"}
    assert public.json()["question"] == "What is the total?"
    assert public.json()["answer"] == "The total is 42."
    assert "private" not in public.text
    assert "generated_code" not in public.text
    assert public.headers["x-robots-tag"].startswith("noindex")
    assert "no-store" in public.headers["cache-control"]
    assert public.headers["referrer-policy"] == "no-referrer"

    listed = client.get(f"/analysis/{analysis_id}/share", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "token" not in listed.json()[0]
    assert "token_hash" not in listed.json()[0]
    with TestSession() as db:
        assert db.query(ShareLink).one().view_count == 1

    # A share token is not an authentication token and grants no API access.
    assert client.get(
        "/analysis/history",
        headers={"Authorization": f"Bearer {share_token}"},
    ).status_code == 401


def test_wrong_expired_and_revoked_tokens_have_the_same_not_found_response():
    _, analysis_id, headers, _ = _seed()
    created = client.post(
        f"/analysis/{analysis_id}/share",
        json={"expires_in_days": 1},
        headers=headers,
    )
    token = created.json()["token"]
    invalid = client.get("/public/analysis/not-a-real-token")
    assert invalid.status_code == 404
    assert invalid.headers["x-robots-tag"].startswith("noindex")
    assert "no-store" in invalid.headers["cache-control"]
    assert invalid.headers["referrer-policy"] == "no-referrer"

    with TestSession() as db:
        share = db.query(ShareLink).one()
        share.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    expired = client.get(f"/public/analysis/{token}")
    assert expired.status_code == 404
    assert expired.json() == invalid.json()

    with TestSession() as db:
        share = db.query(ShareLink).one()
        share.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        db.commit()
    revoked = client.delete(
        f"/analysis/{analysis_id}/share/{created.json()['id']}",
        headers=headers,
    )
    assert revoked.status_code == 204
    unavailable = client.get(f"/public/analysis/{token}")
    assert unavailable.status_code == 404
    assert unavailable.json() == invalid.json()


def test_share_creation_requires_owner_and_expiry_is_limited_to_supported_choices():
    owner_id, analysis_id, headers, _ = _seed()
    with TestSession() as db:
        other = User(
            name="Other",
            email=f"other-{uuid4()}@example.test",
            password_hash="unused",
            is_verified=True,
        )
        db.add(other)
        db.commit()
        other_token = create_access_token(str(other.id), other.token_version)

    unauthorized_owner = client.post(
        f"/analysis/{analysis_id}/share",
        json={"expires_in_days": 7},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    invalid_expiry = client.post(
        f"/analysis/{analysis_id}/share",
        json={"expires_in_days": 5},
        headers=headers,
    )
    assert unauthorized_owner.status_code == 404
    assert invalid_expiry.status_code == 422


def test_delete_share_endpoint_revokes_all_active_links():
    _, analysis_id, headers, _ = _seed()
    first = client.post(
        f"/analysis/{analysis_id}/share",
        json={"expires_in_days": 1},
        headers=headers,
    ).json()
    second = client.post(
        f"/analysis/{analysis_id}/share",
        json={"expires_in_days": 30},
        headers=headers,
    ).json()

    revoked = client.delete(f"/analysis/{analysis_id}/share", headers=headers)

    assert revoked.status_code == 204
    assert client.get(f"/analysis/{analysis_id}/share", headers=headers).json() == []
    for created in (first, second):
        public = client.get(f"/public/analysis/{created['token']}")
        assert public.status_code == 404
