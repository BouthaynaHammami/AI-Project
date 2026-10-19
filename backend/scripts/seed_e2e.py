import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.getenv("E2E_TEST_DATABASE") != "1":
    raise RuntimeError("This script is only for the isolated Playwright test database.")

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models import Analysis, ShareLink, User

if engine.url.get_backend_name() != "sqlite":
    raise RuntimeError("Playwright fixtures must use an isolated SQLite database.")

email = os.environ["E2E_USER_EMAIL"]
password = os.environ["E2E_USER_PASSWORD"]
other_email = os.environ["E2E_OTHER_USER_EMAIL"]
share_token = os.environ["E2E_SHARE_TOKEN"]

Base.metadata.create_all(bind=engine)
now = datetime.now(timezone.utc)

with SessionLocal() as db:
    owner = User(
        name="E2E Owner",
        email=email,
        password_hash=get_password_hash(password),
        is_verified=True,
        is_active=True,
    )
    other_user = User(
        name="E2E Other",
        email=other_email,
        password_hash=get_password_hash(password),
        is_verified=True,
        is_active=True,
    )
    db.add_all([owner, other_user])
    db.flush()

    analysis = Analysis(
        user_id=owner.id,
        dataset_id=None,
        question="Quel est le total des ventes ?",
        answer="Le total des ventes est de 1 250.",
        result_type="text",
        result_data="1250",
        title="Analyse E2E",
        created_at=now,
    )
    public_analysis = Analysis(
        user_id=owner.id,
        dataset_id=None,
        question="Quel est le total public ?",
        answer="Le total public est de 1 250.",
        result_type="text",
        result_data="1250",
        title="Analyse publique E2E",
        created_at=now,
    )
    db.add_all([analysis, public_analysis])
    db.flush()

    db.add(
        ShareLink(
            analysis_id=public_analysis.id,
            created_by=owner.id,
            token_hash=hashlib.sha256(share_token.encode("utf-8")).hexdigest(),
            created_at=now,
            expires_at=now + timedelta(days=7),
        )
    )
    db.commit()
