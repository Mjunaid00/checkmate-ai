"""
Central configuration for the CheckMate AI backend.

Loads backend/.env exactly once using an explicit path, so settings are the
same no matter which directory uvicorn is started from. Every other module
should import settings from here instead of calling os.getenv() directly.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "true" if default else "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI = _env("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = _env("DATABASE_NAME", "checkmate_ai")

# ── JWT ──────────────────────────────────────────────────────────────────────
JWT_SECRET = _env("JWT_SECRET", "changeme_use_a_long_random_string_here")
JWT_ALGORITHM = _env("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(_env("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# ── Upload storage ───────────────────────────────────────────────────────────
# Relative values are resolved against backend/, not the current working dir.
_upload_raw = Path(_env("UPLOAD_DIR", "../uploads"))
UPLOAD_DIR = _upload_raw if _upload_raw.is_absolute() else (BACKEND_DIR / _upload_raw).resolve()
MAX_UPLOAD_SIZE_MB = int(_env("MAX_UPLOAD_SIZE_MB", "32"))

# ── LM Studio (OpenAI-compatible local LLM) ──────────────────────────────────
LM_STUDIO_URL = _env("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions").strip()
LM_STUDIO_MODEL = _env("LM_STUDIO_MODEL", "").strip()
# Base server URL (http://host:port) derived from the chat-completions URL.
LM_STUDIO_BASE = LM_STUDIO_URL.split("/v1/")[0] if "/v1/" in LM_STUDIO_URL else LM_STUDIO_URL.rstrip("/")
# Context window the launcher asks LM Studio to load the model with. A 5-page
# submission is ~12k image tokens, so the 4k default truncates grading requests.
LM_STUDIO_CONTEXT_LENGTH = int(_env("LM_STUDIO_CONTEXT_LENGTH", "16384"))
# Longest side (px) of page images sent to the vision model (0 = no downscale).
LLM_IMAGE_MAX_SIDE = int(_env("LLM_IMAGE_MAX_SIDE", "1600"))

# ── OCR ──────────────────────────────────────────────────────────────────────
# lmstudio : send page images to the vision model already loaded in LM Studio (default)
# chandra  : Chandra OCR 2 via HuggingFace (needs a working torch install + free GPU memory)
# none     : OCR disabled; grading uses the vision model only
OCR_BACKEND = _env("OCR_BACKEND", "lmstudio").strip().lower() or "lmstudio"
if OCR_BACKEND not in ("lmstudio", "chandra", "none"):
    print(f"[config] Unknown OCR_BACKEND={OCR_BACKEND!r}; falling back to 'lmstudio'")
    OCR_BACKEND = "lmstudio"

# Reject student submissions whose first page lacks the institution header.
# Requires OCR; automatically skipped when OCR_BACKEND=none.
REQUIRE_INSTITUTION_HEADER = _env_bool("REQUIRE_INSTITUTION_HEADER", True)

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS = [
    o.strip()
    for o in _env(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    ).split(",")
    if o.strip()
]


# ── Path helpers ─────────────────────────────────────────────────────────────
def relative_upload_path(path: Path) -> str:
    """
    Convert a saved file path into the string stored in MongoDB.
    Paths under the project root are stored relative to it (forward slashes),
    which matches the records created by earlier versions of the app.
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def absolute_upload_path(stored: str) -> Path:
    """Inverse of relative_upload_path()."""
    p = Path(stored or "")
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
