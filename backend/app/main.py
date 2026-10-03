import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.analyses import router as analyses_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.core.database import Base, engine

Base.metadata.create_all(bind=engine)
if engine.url.get_backend_name() == "postgresql":
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT 'Utilisateur'"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo TEXT"))
elif engine.url.get_backend_name() == "sqlite":
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "profile_photo" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN profile_photo TEXT"))

app = FastAPI(title="AI Data Analyst API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
allowed_origins = list(dict.fromkeys([
    frontend_origin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(analyses_router)


@app.get("/")
def root():
    return {"message": "AI Data Analyst API is running"}