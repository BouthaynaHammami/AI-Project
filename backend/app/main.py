import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.analyses import router as analyses_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.core.database import Base, engine

Base.metadata.create_all(bind=engine)
if engine.url.get_backend_name() == "postgresql":
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT 'Utilisateur'"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo TEXT"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_email VARCHAR(255)"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_pending_email ON users (pending_email)"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS generated_code TEXT"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS code_explanation TEXT"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS code_retried BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL"))
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
    if missing_user_columns:
        with engine.begin() as connection:
            for statement in missing_user_columns:
                connection.execute(text(statement))
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
    if missing_analysis_columns:
        with engine.begin() as connection:
            for statement in missing_analysis_columns:
                connection.execute(text(statement))
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_pending_email ON users (pending_email)"))

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
    return response


app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(analyses_router)


@app.get("/")
def root():
    return {"message": "AI Data Analyst API is running"}