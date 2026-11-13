"""FastAPI entry point for the Spoonfuls web and phone shell."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import auth, db

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run migrations when the configured database is available."""

    if os.environ.get("SPOONFULS_AUTO_MIGRATE", "1") == "1":
        try:
            db.apply_migrations()
        except Exception:  # pragma: no cover - the health endpoint reports the failure
            logger.exception("database migrations are not available yet")
    if (
        os.environ.get("SPOONFULS_ALLOW_PRIVILEGED_DATABASE_ROLE") != "1"
        and not db.runtime_role_is_safe()
    ):
        raise RuntimeError(
            "Spoonfuls refuses to start with a superuser or RLS-bypass database role"
        )
    yield


app = FastAPI(title="Spoonfuls", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response


@app.get("/", response_class=Response)
async def index() -> Response:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for asset in ("app.js", "style.css"):
        digest = sha256((STATIC_DIR / asset).read_bytes()).hexdigest()
        html = html.replace(f"/static/{asset}", f"/static/{asset}?v={digest}")
    return Response(content=html, media_type="text/html")


@app.get("/api/health")
async def health() -> JSONResponse:
    database_ok = db.is_ready()
    return JSONResponse({"ok": database_ok, "db": database_ok})
