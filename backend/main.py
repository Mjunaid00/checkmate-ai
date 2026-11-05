"""
CheckMate AI — FastAPI application entry point.

Run (from backend/):
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Docs:
    http://localhost:8000/docs    ← Swagger UI
    http://localhost:8000/redoc  ← ReDoc
Health:
    http://localhost:8000/health        ← liveness only
    http://localhost:8000/health/full   ← MongoDB + LM Studio + OCR + storage
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config  # loads backend/.env first, regardless of the working directory
from database import connect_db, close_db, get_db, ping as db_ping, ensure_indexes
from routers import (
    auth, dashboard, classes, assignments, submissions, enrollment, analytics,
    reports, quizzes, messages, notifications, omr, admin,
)
from routers.admin import ensure_admin_bootstrap


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to MongoDB on startup, create indexes, bootstrap admin; close on shutdown."""
    await connect_db()
    try:
        await ensure_indexes()
    except Exception as e:
        print(f"[indexes] skipped: {e}")
    try:
        await ensure_admin_bootstrap(get_db())
    except Exception as e:
        print(f"[admin-bootstrap] skipped: {e}")
    print(
        f"[config] OCR backend: {config.OCR_BACKEND} | LM Studio: {config.LM_STUDIO_BASE} "
        f"| model: {config.LM_STUDIO_MODEL or '(server default)'}"
    )
    print(f"[config] Uploads: {config.UPLOAD_DIR}")
    yield
    await close_db()


# ── App instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="CheckMate AI",
    description="AI-powered exam grading platform with explainable feedback.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(classes.router)
app.include_router(assignments.router)
app.include_router(submissions.router)
app.include_router(enrollment.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(quizzes.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(omr.router)
app.include_router(admin.router)


# ── Root / health ────────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
async def root():
    return {
        "project": "CheckMate AI",
        "version": app.version,
        "status": "running",
        "docs": "/docs",
        "health": "/health/full",
    }


@app.get("/health", tags=["health"])
async def health():
    """Lightweight liveness probe."""
    return {"status": "ok"}


def _uploads_writable() -> dict:
    """Make sure the upload directory exists and accepts writes."""
    try:
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        probe = config.UPLOAD_DIR / f".healthcheck-{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"path": str(config.UPLOAD_DIR), "writable": True}
    except Exception as e:
        return {"path": str(config.UPLOAD_DIR), "writable": False, "error": str(e)[:160]}


@app.get("/health/full", tags=["health"])
async def health_full():
    """
    Readiness probe used by the one-click launcher.
    Checks MongoDB, LM Studio (server + loaded model), the OCR backend and
    upload storage. Returns status "ok" only when everything grading needs is up.
    """
    from core.llm import lmstudio_status
    from services.ocr import ocr_status

    checks = {
        "mongodb": await db_ping(),
        "lm_studio": await lmstudio_status(),
        "ocr": ocr_status(),
        "uploads": _uploads_writable(),
    }
    ok = (
        checks["mongodb"]["ok"]
        and checks["lm_studio"]["reachable"]
        and checks["lm_studio"]["model_loaded"]
        and checks["ocr"]["available"]
        and checks["uploads"]["writable"]
    )
    return {"status": "ok" if ok else "degraded", "version": app.version, "checks": checks}
