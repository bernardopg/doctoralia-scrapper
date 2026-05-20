"""
FastAPI application composition root for the v1 API.

Route implementations live under ``src.api.v1.routers``. This module owns only
app construction, cross-cutting middleware, lifecycle hooks and the CLI starter.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1 import _state as api_state
from src.api.v1.middleware import register_api_middleware
from src.api.v1.routers import (
    analyze,
    auth,
    generate,
    health,
    jobs,
    metrics,
    scrape,
    settings,
    telegram,
)


async def startup_notification_scheduler() -> None:
    if api_state.should_disable_notification_scheduler():
        return
    api_state.get_telegram_schedule_service(start_runner=True)


async def shutdown_notification_scheduler() -> None:
    api_state.stop_telegram_schedule_service()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_notification_scheduler()
    try:
        yield
    finally:
        await shutdown_notification_scheduler()


app = FastAPI(
    title="Doctoralia Scrapper API",
    description="n8n-compatible API for scraping and analyzing medical reviews",
    version=api_state.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_api_middleware(app)

for api_router in (
    auth.router,
    health.router,
    scrape.router,
    jobs.router,
    generate.router,
    analyze.router,
    telegram.router,
    settings.router,
    metrics.router,
):
    app.include_router(api_router)


def start_api(
    host: str = "127.0.0.1", port: int = 8000
):  # pragma: no cover - thin wrapper
    """Start the API using uvicorn when the optional runtime dependency exists."""
    import importlib.util

    uvicorn_spec = importlib.util.find_spec("uvicorn")
    if uvicorn_spec is None:
        raise RuntimeError(
            "uvicorn is required to start the API. Install with 'poetry add uvicorn' or pip."
        )

    import uvicorn  # type: ignore

    uvicorn.run(app, host=host, port=port)
