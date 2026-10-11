import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.analyses import router as analyses_router
from app.api.conversations import router as conversations_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.shares import analysis_router as shares_router, public_router
from app.api.usage import admin_router, usage_router
from app.core.database import Base, engine
from app.models.share_link import ShareLink
from app.models.usage_event import UsageEvent
from app.models.user import DEFAULT_MONTHLY_QUOTA

initial_admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()

Base.metadata.create_all(bind=engine)
if engine.url.get_backend_name() == "postgresql":
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT 'Utilisateur'"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo TEXT"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_email VARCHAR(255)"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'"))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_quota INTEGER NOT NULL "
            f"DEFAULT {DEFAULT_MONTHLY_QUOTA}"
        ))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_pending_email ON users (pending_email)"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS generated_code TEXT"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS code_explanation TEXT"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS code_retried BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS title VARCHAR(120)"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"))
        connection.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        foreign_keys = inspect(connection).get_foreign_keys("analyses")
        dataset_fk = next(
            (item for item in foreign_keys if item.get("constrained_columns") == ["dataset_id"]),
            None,
        )
        if dataset_fk and dataset_fk.get("options", {}).get("ondelete", "").upper() != "SET NULL":
            constraint_name = dataset_fk.get("name")
            if constraint_name:
                connection.execute(text(f'ALTER TABLE analyses DROP CONSTRAINT "{constraint_name}"'))
            connection.execute(text("ALTER TABLE analyses ALTER COLUMN dataset_id DROP NOT NULL"))
            connection.execute(text(
                "ALTER TABLE analyses ADD CONSTRAINT fk_analyses_dataset_id "
                "FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL"
            ))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_analyses_user_deleted_created ON analyses (user_id, deleted_at, created_at)"))
        connection.execute(text("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS pii_preferences TEXT NOT NULL DEFAULT '{}'"))
        if initial_admin_email:
            connection.execute(
                text("UPDATE users SET role = 'admin' WHERE lower(email) = :email"),
                {"email": initial_admin_email},
            )
elif engine.url.get_backend_name() == "sqlite":
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    missing_user_columns = []
    if "profile_photo" not in user_columns:
        missing_user_columns.append("ALTER TABLE users ADD COLUMN profile_photo TEXT")
    if "is_verified" not in user_columns:
        missing_user_columns.append("ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 0")
    if "pending_email" not in user_columns:
        missing_user_columns.append("ALTER TABLE users ADD COLUMN pending_email VARCHAR(255)")
    if "token_version" not in user_columns:
        missing_user_columns.append("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
    if "role" not in user_columns:
        missing_user_columns.append("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
    if "monthly_quota" not in user_columns:
        missing_user_columns.append(
            "ALTER TABLE users ADD COLUMN monthly_quota INTEGER NOT NULL "
            f"DEFAULT {DEFAULT_MONTHLY_QUOTA}"
        )
    if "is_active" not in user_columns:
        missing_user_columns.append("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
    if missing_user_columns:
        with engine.begin() as connection:
            for statement in missing_user_columns:
                connection.execute(text(statement))
    dataset_columns = {column["name"] for column in inspect(engine).get_columns("datasets")}
    if "pii_preferences" not in dataset_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE datasets ADD COLUMN pii_preferences TEXT NOT NULL DEFAULT '{}'"))
    analysis_columns = {column["name"] for column in inspect(engine).get_columns("analyses")}
    missing_analysis_columns = []
    if "generated_code" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN generated_code TEXT")
    if "code_explanation" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN code_explanation TEXT")
    if "code_retried" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN code_retried BOOLEAN NOT NULL DEFAULT 0")
    if "conversation_id" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL")
    if "title" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN title VARCHAR(120)")
    if "is_favorite" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0")
    if "deleted_at" not in analysis_columns:
        missing_analysis_columns.append("ALTER TABLE analyses ADD COLUMN deleted_at DATETIME")
    if missing_analysis_columns:
        with engine.begin() as connection:
            for statement in missing_analysis_columns:
                connection.execute(text(statement))
    conversation_columns = {column["name"] for column in inspect(engine).get_columns("conversations")}
    if "is_favorite" not in conversation_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE conversations ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"))
    if "updated_at" not in conversation_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE conversations ADD COLUMN updated_at DATETIME"))
            connection.execute(text("UPDATE conversations SET updated_at = created_at WHERE updated_at IS NULL"))
    analysis_columns = {column["name"]: column for column in inspect(engine).get_columns("analyses")}
    analysis_foreign_keys = inspect(engine).get_foreign_keys("analyses")
    dataset_fk = next(
        (item for item in analysis_foreign_keys if item.get("constrained_columns") == ["dataset_id"]),
        None,
    )
    if (
        not analysis_columns["dataset_id"]["nullable"]
        or not dataset_fk
        or dataset_fk.get("options", {}).get("ondelete", "").upper() != "SET NULL"
    ):
        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            connection.commit()
            with connection.begin():
                connection.execute(text("""
                    CREATE TABLE analyses_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
                        dataset_id INTEGER REFERENCES datasets(id) ON DELETE SET NULL,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        result_type VARCHAR(20) NOT NULL,
                        result_data TEXT,
                        chart_config TEXT,
                        generated_code TEXT,
                        code_explanation TEXT,
                        code_retried BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL,
                        title VARCHAR(120),
                        is_favorite BOOLEAN NOT NULL DEFAULT 0,
                        deleted_at DATETIME
                    )
                """))
                connection.execute(text("""
                    INSERT INTO analyses_new (
                        id, user_id, conversation_id, dataset_id, question, answer,
                        result_type, result_data, chart_config, generated_code,
                        code_explanation, code_retried, created_at, title,
                        is_favorite, deleted_at
                    )
                    SELECT
                        id, user_id, conversation_id, dataset_id, question, answer,
                        result_type, result_data, chart_config, generated_code,
                        code_explanation, code_retried, created_at, title,
                        is_favorite, deleted_at
                    FROM analyses
                """))
                connection.execute(text("DROP TABLE analyses"))
                connection.execute(text("ALTER TABLE analyses_new RENAME TO analyses"))
                for statement in (
                    "CREATE INDEX IF NOT EXISTS ix_analyses_id ON analyses (id)",
                    "CREATE INDEX IF NOT EXISTS ix_analyses_user_id ON analyses (user_id)",
                    "CREATE INDEX IF NOT EXISTS ix_analyses_conversation_id ON analyses (conversation_id)",
                    "CREATE INDEX IF NOT EXISTS ix_analyses_user_deleted_created ON analyses (user_id, deleted_at, created_at)",
                ):
                    connection.execute(text(statement))
            connection.execute(text("PRAGMA foreign_keys=ON"))
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_pending_email ON users (pending_email)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_analyses_user_deleted_created ON analyses (user_id, deleted_at, created_at)"))
        if initial_admin_email:
            connection.execute(
                text("UPDATE users SET role = 'admin' WHERE lower(email) = :email"),
                {"email": initial_admin_email},
            )

app = FastAPI(title="AI Data Analyst API")

from app.core.rate_limit import limiter

app.state.limiter = limiter


async def rate_limit_error(request: Request, exc: RateLimitExceeded):
    retry_after_by_path = {
        "/auth/signup": 3600,
        "/auth/login": 60,
        "/auth/verify-email": 60,
        "/auth/resend-code": 600,
        "/auth/forgot-password": 600,
        "/auth/reset-password": 60,
    }
    retry_after = retry_after_by_path.get(request.url.path, 60)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Trop de tentatives, réessayez dans {retry_after} secondes."},
        headers={"Retry-After": str(retry_after)},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_error)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGIN", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Auth-Email", "X-CSRF-Token"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/public/analysis/"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(analyses_router)
app.include_router(conversations_router)
app.include_router(shares_router)
app.include_router(public_router)
app.include_router(usage_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {"message": "AI Data Analyst API is running"}