"""FastAPI application entrypoint, error envelope middleware, and lifecycle hooks."""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from noema.api.router import router as api_v1_router
from noema.config import get_settings
from noema.persistence.db import init_db
from noema.worker.runner import drain_background_jobs


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    settings = get_settings()
    stop_event = threading.Event()
    worker_thread: threading.Thread | None = None

    if settings.enable_background_worker:

        def _organizer_loop() -> None:
            while not stop_event.wait(1.5):
                try:
                    drain_background_jobs(max_jobs=10)
                except Exception:
                    pass

        worker_thread = threading.Thread(
            target=_organizer_loop,
            name="noema-background-organizer",
            daemon=True,
        )
        worker_thread.start()

    try:
        yield
    finally:
        stop_event.set()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Noema API",
        version="0.1.0",
        description="Local-first personal knowledge environment API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        detail: Any = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            payload = {
                "error": {
                    "code": str(detail["code"]),
                    "message": str(detail["message"]),
                    "details": detail.get("details", {}),
                }
            }
        else:
            payload = {
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": str(detail),
                    "details": {},
                }
            }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        first_loc = ".".join(str(x) for x in errors[0].get("loc", [])) if errors else ""
        code = "validation_error"
        if "tag" in first_loc:
            code = "unsupported_annotation_tag"
        elif "span" in first_loc:
            code = "invalid_span"
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": code,
                    "message": "Request validation failed.",
                    "details": {"field": first_loc},
                }
            },
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_v1_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dist), html=True),
            name="frontend",
        )

    return app


app = create_app()

