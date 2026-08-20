from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from peoplepulse.api.activity import router as activity_router
from peoplepulse.api.dashboard import router as dashboard_router
from peoplepulse.api.monitoring import router as monitoring_router
from peoplepulse.config import get_settings
from peoplepulse.monitoring.prometheus import observe_request, refresh_monitoring_gauges

app = FastAPI(
    title="PeoplePulse AI API",
    version="0.8.0",
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
app.include_router(monitoring_router)


@app.middleware("http")
async def prometheus_http_metrics(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route_obj = request.scope.get("route")
        route = getattr(route_obj, "path", None) or request.url.path
        observe_request(request.method, route, status, time.perf_counter() - started)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "peoplepulse-api"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    refresh_monitoring_gauges(settings.mlops_monitoring_summary_path)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
