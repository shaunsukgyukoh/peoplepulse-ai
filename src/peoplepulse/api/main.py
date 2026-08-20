from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from peoplepulse.api.activity import router as activity_router
from peoplepulse.api.dashboard import router as dashboard_router
from peoplepulse.config import get_settings

app = FastAPI(
    title="PeoplePulse AI API",
    version="0.7.0",
    description="Privacy-aware People Analytics portfolio API",
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(activity_router)
app.include_router(dashboard_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "peoplepulse-api"}
