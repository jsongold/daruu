"""FastAPI application entry point."""
import time
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.admin_routes import admin_router
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Daru PDF Simple", version="0.1.0", lifespan=lifespan)

    class LatencyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start = time.perf_counter()
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            response.headers["Server-Timing"] = f"total;dur={ms:.1f}"
            return response

    app.add_middleware(LatencyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok"}

    return app


app = create_app()
