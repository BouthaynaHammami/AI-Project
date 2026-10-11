import os

os.environ["ENV"] = "dev"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-characters"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.core.security import get_password_hash
from app.main import app
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.email_code import EmailCode
from app.models.feedback import Feedback
from app.models.share_link import ShareLink
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.services import email_service

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
client = TestClient(app)
sent_codes: list[tuple[str, str, str]] = []


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def capture_email(recipient: str, code: str, purpose: str) -> None:
    sent_codes.append((recipient, code, purpose))


auth_api.send_email_code = capture_email


def setup_function():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    sent_codes.clear()
    limiter.reset()
    app.dependency_overrides[get_db] = override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def signup(email: str = "person@example.com"):
    return client.post(
        "/auth/signup",
        json={"name": "Test User", "email": email, "password": "StrongPass123"},
    )


def create_verified_account(email: str = "person@example.com") -> str:
    response = signup(email)
    assert response.status_code == 202
    code = sent_codes[-1][1]
    verified = client.post("/auth/verify-email", json={"email": email, "code": code})
    assert verified.status_code == 200
    return verified.json()["access_token"]


def test_signup_stores_only_hash_and_verification_returns_token(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    response = signup()

    assert response.status_code == 202
    assert response.json()["delivery_mode"] == "console"
    assert "access_token" not in response.json()
    assert len(sent_codes) == 1
    email, code, purpose = sent_codes[0]
    assert email == "person@example.com"
    assert len(code) == 6 and code.isdigit()
    assert purpose == "verify"

    with TestSession() as db:
        user = db.query(User).filter_by(email=email).one()
        email_code = db.query(EmailCode).filter_by(user_id=user.id).one()
        assert user.is_verified is False
        assert email_code.code_hash != code
        assert len(email_code.code_hash) == 64

    verified = client.post("/auth/verify-email", json={"email": email, "code": code})
    assert verified.status_code == 200
    assert verified.json()["access_token"]
    with TestSession() as db:
        assert db.query(User).filter_by(email=email).one().is_verified is True
        assert db.query(EmailCode).count() == 0


def test_signup_reports_smtp_failure_and_removes_undeliverable_code(monkeypatch):
    def fail_delivery(*_args):
        raise RuntimeError("SMTP unavailable")

    monkeypatch.setattr(auth_api, "send_email_code", fail_delivery)
    response = signup()

    assert response.status_code == 503
    assert "configuration SMTP" in response.json()["detail"]
    with TestSession() as db:
        assert db.query(EmailCode).count() == 0


def test_signup_with_unavailable_local_smtp_returns_console_delivery_mode(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_FROM", "AI Data Analyst <no-reply@localhost>")
    monkeypatch.setenv("SMTP_TLS", "false")
    monkeypatch.setattr(auth_api, "send_email_code", email_service.send_email_code)

    response = signup()

    assert response.status_code == 202
    assert response.json()["delivery_mode"] == "console"
    with TestSession() as db:
        assert db.query(EmailCode).count() == 1


def test_fifth_incorrect_code_attempt_invalidates_code():
    signup()
    email, code, _ = sent_codes[0]
    wrong_code = "000000" if code != "000000" else "000001"

    for _ in range(5):
        response = client.post(
            "/auth/verify-email",
            json={"email": email, "code": wrong_code},
        )
        assert response.status_code == 400

    with TestSession() as db:
        assert db.query(EmailCode).count() == 0
    assert client.post(
        "/auth/verify-email",
        json={"email": email, "code": code},
    ).status_code == 400


def test_expired_code_is_rejected():
    signup()
    email, code, _ = sent_codes[0]
    with TestSession() as db:
        record = db.query(EmailCode).one()
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    response = client.post("/auth/verify-email", json={"email": email, "code": code})
    assert response.status_code == 400
    assert response.json()["detail"] == "Code invalide ou expiré."
    with TestSession() as db:
        assert db.query(EmailCode).count() == 0


def test_resend_is_generic_and_obeys_cooldown():
    signup()
    response = client.post("/auth/resend-code", json={"email": "person@example.com"})
    unknown = client.post("/auth/resend-code", json={"email": "unknown@example.com"})

    assert response.status_code == unknown.status_code == 202
    assert response.json() == unknown.json()
    assert len(sent_codes) == 1


def test_resend_rate_limit_includes_retry_after():
    for _ in range(3):
        response = client.post("/auth/resend-code", json={"email": "unknown@example.com"})
        assert response.status_code == 202

    limited = client.post("/auth/resend-code", json={"email": "unknown@example.com"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "600"


def test_login_requires_verified_email():
    signup()
    assert client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "StrongPass123"},
    ).status_code == 403

    email, code, _ = sent_codes[0]
    assert client.post("/auth/verify-email", json={"email": email, "code": code}).status_code == 200
    assert client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass123"},
    ).status_code == 200


def test_repeated_signup_is_rate_limited_during_code_cooldown():
    assert signup().status_code == 202
    response = signup()
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_logout_persists_token_revocation():
    token = create_verified_account()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_forgot_password_is_anti_enumerating_and_reset_revokes_sessions():
    token = create_verified_account()
    known = client.post("/auth/forgot-password", json={"email": "person@example.com"})
    known_code = sent_codes[-1][1]
    unknown = client.post("/auth/forgot-password", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert sent_codes[-1][1] == known_code

    reset = client.post(
        "/auth/reset-password",
        json={
            "email": "person@example.com",
            "code": known_code,
            "new_password": "NewStrongPass456",
        },
    )
    assert reset.status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "StrongPass123"},
    ).status_code == 401
    assert client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "NewStrongPass456"},
    ).status_code == 200


def test_account_deletion_requires_correct_current_password():
    token = create_verified_account()
    response = client.request(
        "DELETE",
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "WrongPass123"},
    )

    assert response.status_code == 400
    with TestSession() as db:
        assert db.query(User).filter_by(email="person@example.com").one()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_account_deletion_removes_related_data_and_uploads_only_for_account(tmp_path, monkeypatch):
    owner_token = create_verified_account()
    other_token = create_verified_account("other@example.com")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    uploaded_file = upload_dir / "owner.csv"
    uploaded_file.write_text("value\n1\n", encoding="utf-8")
    monkeypatch.setattr(auth_api, "UPLOAD_DIR", upload_dir)

    with TestSession() as db:
        owner = db.query(User).filter_by(email="person@example.com").one()
        other = db.query(User).filter_by(email="other@example.com").one()
        owner_dataset = Dataset(
            user_id=owner.id,
            filename="owner.csv",
            file_path=str(uploaded_file),
            file_type="csv",
            row_count=1,
            column_count=1,
        )
        other_dataset = Dataset(
            user_id=other.id,
            filename="other.csv",
            file_path=str(upload_dir / "other.csv"),
            file_type="csv",
            row_count=1,
            column_count=1,
        )
        db.add_all([owner_dataset, other_dataset])
        db.flush()

        owner_conversation = Conversation(user_id=owner.id, title="Owner", dataset_ids="[]")
        db.add(owner_conversation)
        db.flush()
        owner_analysis = Analysis(
            user_id=owner.id,
            conversation_id=owner_conversation.id,
            dataset_id=owner_dataset.id,
            question="Question",
            answer="Answer",
            result_type="text",
        )
        other_analysis = Analysis(
            user_id=other.id,
            dataset_id=other_dataset.id,
            question="Question",
            answer="Answer",
            result_type="text",
        )
        db.add_all([owner_analysis, other_analysis])
        db.flush()
        db.add_all([
            Feedback(analysis_id=owner_analysis.id, user_id=owner.id, rating=1),
            ShareLink(
                analysis_id=owner_analysis.id,
                token_hash="owner-share-token-hash",
                created_by=owner.id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ),
            UsageEvent(user_id=owner.id, type="analysis", status="success"),
            EmailCode(
                user_id=owner.id,
                purpose="reset",
                code_hash="a" * 64,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            ),
        ])
        db.commit()

    response = client.request(
        "DELETE",
        "/auth/me",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"current_password": "StrongPass123"},
    )

    assert response.status_code == 200
    assert response.json()["files_cleanup_pending"] == 0
    assert not uploaded_file.exists()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {other_token}"}).status_code == 200
    with TestSession() as db:
        other_user_id = db.query(User.id).filter_by(email="other@example.com").scalar()
        assert db.query(User).filter_by(email="person@example.com").count() == 0
        assert other_user_id is not None
        assert db.query(Dataset).filter_by(user_id=other_user_id).count() == 1
        assert db.query(Analysis).filter_by(user_id=other_user_id).count() == 1
        assert db.query(Feedback).count() == 0
        assert db.query(ShareLink).count() == 0
        assert db.query(UsageEvent).count() == 0
        assert db.query(EmailCode).count() == 0
        assert db.query(Conversation).count() == 0


def test_email_change_keeps_old_address_until_code_is_verified():
    token = create_verified_account()
    response = client.put(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "new@example.com",
            "current_password": "StrongPass123",
        },
    )
    assert response.status_code == 200
    assert response.json()["email"] == "person@example.com"
    assert response.json()["email_change_pending"] is True
    assert sent_codes[-1][0] == "new@example.com"
    code = sent_codes[-1][1]

    verified = client.post(
        "/auth/verify-email",
        json={"email": "new@example.com", "code": code},
    )
    assert verified.status_code == 200
    profile = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {verified.json()['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "new@example.com"
    assert profile.json()["email_change_pending"] is False


def test_pending_email_update_is_idempotent_and_can_be_cancelled():
    token = create_verified_account()
    headers = {"Authorization": f"Bearer {token}"}
    pending = client.put(
        "/auth/me",
        headers=headers,
        json={"email": "new@example.com", "current_password": "StrongPass123"},
    )
    assert pending.status_code == 200
    first_code = sent_codes[-1][1]

    unchanged = client.put(
        "/auth/me",
        headers=headers,
        json={
            "email": "new@example.com",
            "current_password": "StrongPass123",
            "name": "Updated Name",
        },
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["pending_email"] == "new@example.com"
    assert len(sent_codes) == 2

    cancelled = client.put(
        "/auth/me",
        headers=headers,
        json={"email": "person@example.com", "current_password": "StrongPass123"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["pending_email"] is None
    assert client.post(
        "/auth/verify-email",
        json={"email": "new@example.com", "code": first_code},
    ).status_code == 400


def test_login_rate_limit_returns_retry_after():
    for _ in range(5):
        response = client.post(
            "/auth/login",
            headers={"X-Auth-Email": "missing@example.com"},
            json={"email": "missing@example.com", "password": "StrongPass123"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/auth/login",
        headers={"X-Auth-Email": "missing@example.com"},
        json={"email": "missing@example.com", "password": "StrongPass123"},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert "Trop de tentatives" in limited.json()["detail"]


def test_login_error_is_identical_for_unknown_email_and_wrong_password():
    with TestSession() as db:
        db.add(User(
            name="Test User",
            email="person@example.com",
            password_hash=get_password_hash("StrongPass123"),
            is_verified=True,
        ))
        db.commit()

    wrong_password = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "WrongPass123"},
    )
    unknown_email = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "WrongPass123"},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_password_change_requires_current_password_and_revokes_existing_token():
    token = create_verified_account()
    headers = {"Authorization": f"Bearer {token}"}
    missing_current = client.put(
        "/auth/me",
        headers=headers,
        json={"password": "NextStrongPass789"},
    )
    assert missing_current.status_code == 422

    wrong_current = client.put(
        "/auth/me",
        headers=headers,
        json={
            "password": "NextStrongPass789",
            "current_password": "WrongPass123",
        },
    )
    assert wrong_current.status_code == 400

    changed = client.put(
        "/auth/me",
        headers=headers,
        json={
            "password": "NextStrongPass789",
            "current_password": "StrongPass123",
        },
    )
    assert changed.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "NextStrongPass789"},
    ).status_code == 200


def test_signup_rejects_weak_passwords_in_french():
    response = client.post(
        "/auth/signup",
        json={"name": "Test User", "email": "weak@example.com", "password": "password123"},
    )
    assert response.status_code == 422
    assert "mot de passe" in response.json()["detail"][0]["msg"].lower()


def test_signup_updates_existing_unverified_account_after_cooldown():
    response = signup()
    assert response.status_code == 202
    with TestSession() as db:
        record = db.query(EmailCode).one()
        record.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db.commit()

    updated = client.post(
        "/auth/signup",
        json={
            "name": "Updated User",
            "email": "person@example.com",
            "password": "DifferentPass456",
        },
    )
    assert updated.status_code == 202
    assert len(sent_codes) == 2
    with TestSession() as db:
        user = db.query(User).filter_by(email="person@example.com").one()
        assert user.name == "Updated User"
        assert user.is_verified is False
        assert db.query(User).count() == 1
    assert client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "DifferentPass456"},
    ).status_code == 403
