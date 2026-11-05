"""
Module 4: OCR Module
- Extract text from images/PDFs (scanned or handwritten)
- Pluggable backend, chosen by OCR_BACKEND in backend/.env:

    lmstudio (default)  Sends each page image to the vision model that is
                        already loaded in LM Studio. No extra model, no torch.
    chandra             Chandra OCR 2 (datalab-to/chandra-ocr-2) through
                        HuggingFace. Needs a working torch install and enough
                        free GPU memory next to the LM Studio model.
    none                OCR disabled. Grading still works (vision-only) but
                        keyword analysis, code detection, plagiarism and the
                        institution-header check are skipped.

All functions here are synchronous and block while a model runs. Call them
from async code with `await asyncio.to_thread(...)`.
"""
from pathlib import Path
from typing import List, Optional

import httpx

from config import OCR_BACKEND, LM_STUDIO_URL, LM_STUDIO_MODEL
from core.llm import file_to_base64_images

SUPPORTED_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg")

_OCR_SYSTEM_PROMPT = "You are a precise OCR engine. You output only the transcribed text."
_OCR_USER_PROMPT = (
    "Transcribe ALL text in this image exactly as written. Preserve line breaks, "
    "headings, question numbers, lists and tables (use markdown for tables). "
    "Include handwritten text. Do not summarise, translate, correct or comment. "
    "If the image contains no text, reply with an empty response."
)


# ── LM Studio backend ────────────────────────────────────────────────────────
def _lmstudio_ocr(images: List[str]) -> str:
    """Run OCR on a list of base64 data-URL images using the LM Studio vision model."""
    if not images:
        return ""
    pages: List[str] = []
    with httpx.Client(timeout=300.0) as client:
        for image_url in images:
            payload = {
                "model": LM_STUDIO_MODEL or "default",
                "messages": [
                    {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _OCR_USER_PROMPT},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                "temperature": 0.0,
                "max_tokens": 4096,
                "stream": False,
            }
            response = client.post(LM_STUDIO_URL, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"LM Studio OCR error {response.status_code}: {response.text[:300]}")
            content = response.json()["choices"][0]["message"]["content"]
            pages.append((content or "").strip())
    return "\n\n".join(p for p in pages if p)


# ── Chandra backend (lazy; imports torch on first use) ──────────────────────
_inference_manager = None


def _chandra_manager():
    global _inference_manager
    if _inference_manager is None:
        from chandra.model import InferenceManager  # heavy import
        _inference_manager = InferenceManager(method="hf")
    return _inference_manager


def _chandra_ocr(file_path: Path, first_page_only: bool) -> str:
    from chandra.model.schema import BatchInputItem
    from chandra.input import load_image, load_pdf_images

    manager = _chandra_manager()
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        images = load_pdf_images(str(file_path), page_range=[0] if first_page_only else [])
    else:
        images = [load_image(str(file_path))]
    if not images:
        return ""
    results = manager.generate([BatchInputItem(image=img) for img in images])
    return "\n\n".join(r.markdown.strip() for r in results if getattr(r, "markdown", None))


# ── Public API ───────────────────────────────────────────────────────────────
def _ocr(file_path: Path, first_page_only: bool) -> str:
    file_path = Path(file_path)
    if OCR_BACKEND == "none":
        return ""
    if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return ""
    if OCR_BACKEND == "chandra":
        return _chandra_ocr(file_path, first_page_only)
    images = file_to_base64_images(file_path)
    if first_page_only:
        images = images[:1]
    return _lmstudio_ocr(images)


def extract_text(file_path: Path) -> str:
    """Extract text from a PDF / PNG / JPG. Returns '' for unsupported files or when OCR is disabled."""
    return _ocr(file_path, first_page_only=False)


def extract_text_from_first_page(file_path: Path) -> str:
    """Extract text from only the first page/image — used for fast header checks."""
    return _ocr(file_path, first_page_only=True)


def ocr_status() -> dict:
    """Describe the active OCR backend for /health/full."""
    info = {"backend": OCR_BACKEND, "available": True, "detail": None}
    if OCR_BACKEND == "none":
        info["detail"] = "OCR disabled (OCR_BACKEND=none)"
    elif OCR_BACKEND == "chandra":
        try:
            import torch  # noqa: F401
            import chandra  # noqa: F401
            info["detail"] = f"Chandra OCR via HuggingFace; CUDA available: {torch.cuda.is_available()}"
        except Exception as e:  # ImportError or broken DLLs
            info["available"] = False
            info["detail"] = f"Chandra/torch not importable: {str(e)[:160]}"
    else:
        info["detail"] = "Uses the LM Studio vision model (see lm_studio check)"
    return info
