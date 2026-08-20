from fastapi import FastAPI

from peoplepulse.api.activity import router as activity_router

app = FastAPI(
    title="PeoplePulse AI API",
    version="0.4.1",
    description="Privacy-aware People Analytics portfolio API",
)
app.include_router(activity_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "peoplepulse-api"}
