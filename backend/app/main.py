from fastapi import FastAPI

from app.core.database import Base, engine
from app.models import Analysis, Dataset
from app.api.datasets import router as datasets_router
from app.api.analyses import router as analyses_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Data Analyst API")
app.include_router(datasets_router)
app.include_router(analyses_router)

@app.get("/")
def root():
    return {"message": "AI Data Analyst API is running"}