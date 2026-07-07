from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.core.config import settings
from src.db.bootstrap import ensure_runtime_schema
from src.services.daily_refresh_service import daily_refresh_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await ensure_runtime_schema()
    daily_refresh_service.start()
    try:
        yield
    finally:
        await daily_refresh_service.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Portfolio Advisor API",
        version="0.1.0",
        description="Read-only portfolio intelligence API for multi-tenant Zerodha users.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-User-Id"],
    )
    app.include_router(router)
    return app


app = create_app()
