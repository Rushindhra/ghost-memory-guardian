"""GHOST backend entry point (FastAPI)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import ai, documents, memories, oral, privacy, system
from .core.config import REPO_ROOT, Settings, get_settings
from .core.context import AppContext, build_context

log = logging.getLogger("ghost")


class _QuietAccessFilter(logging.Filter):
    """Drop uvicorn access lines for API paths: query strings can contain search words."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "?" not in record.getMessage()


def create_app(settings: Settings | None = None, ctx: AppContext | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ctx = ctx or build_context(settings)
        logging.getLogger("uvicorn.access").addFilter(_QuietAccessFilter())
        yield

    app = FastAPI(title="GHOST - private memory guardian", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):  # never echo request data or internals
        log.error("Unhandled %s", type(exc).__name__)
        return JSONResponse({"detail": "Internal error. Check the backend console for the error type."}, 500)

    for r in (system.public, privacy.public, system.router, privacy.router, memories.router, ai.router,
              oral.router, documents.router):
        app.include_router(r)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    # Production-style run: serve the built React app from the same origin (no CORS, one process).
    dist = REPO_ROOT / "frontend" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found."}, 404)
            target = (dist / path).resolve()
            if path and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


app = create_app() if __name__ != "__main__" else None
