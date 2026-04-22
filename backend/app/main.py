from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analysis, datasets, tools

app = FastAPI(
    title="RouteWise API",
    description="School bus route optimization with AI-powered recommendations",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(analysis.router)
app.include_router(tools.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "model": settings.model_name}
