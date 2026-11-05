"""
LLM Grading Engine — uses LM Studio's OpenAI-compatible API.

LM Studio serves models at http://localhost:1234/v1 by default.
Load a vision model (e.g. qwen2.5-vl, llava, llama-vision) in LM Studio,
then start the local server. Configure LM_STUDIO_URL / LM_STUDIO_MODEL in
backend/.env.
"""
import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

from config import LM_STUDIO_URL, LM_STUDIO_MODEL, LM_STUDIO_BASE, LLM_IMAGE_MAX_SIDE


# ── Image helpers ────────────────────────────────────────────────────────────
def file_to_base64_images(file_path: Path) -> List[str]:
    """
    Convert any supported file (PDF, PNG, JPG) to a list of base64-encoded PNG images.
    PDFs are rendered page-by-page into images.
    Returns list of data URLs: ["data:image/png;base64,..."]
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in (".png", ".jpg", ".jpeg"):
        with Image.open(file_path) as img:
            return [_pil_to_data_url(img)]

    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(file_path))
            images = []
            for i in range(len(doc)):
                page = doc[i]
                bitmap = page.render(scale=2)  # 2x for good quality
                images.append(_pil_to_data_url(bitmap.to_pil()))
            doc.close()
            return images
        except ImportError:
            # Fallback: use PyMuPDF (fitz) if pypdfium2 not available
            import fitz
            doc = fitz.open(str(file_path))
            images = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(_pil_to_data_url(img))
            doc.close()
            return images

    return []


def _pil_to_data_url(img: Image.Image) -> str:
    """
    Downscale so the longest side is <= LLM_IMAGE_MAX_SIDE and encode as a PNG
    data URL. Vision models spend roughly one token per 28x28 px tile, so
    capping the size keeps a multi-page submission inside the context window.
    """
    rgb = img.convert("RGB")
    if LLM_IMAGE_MAX_SIDE > 0 and max(rgb.size) > LLM_IMAGE_MAX_SIDE:
        rgb.thumbnail((LLM_IMAGE_MAX_SIDE, LLM_IMAGE_MAX_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


# Backwards-compatible alias (older modules imported the private name).
_file_to_base64_images = file_to_base64_images


# ── Response parsing helpers ─────────────────────────────────────────────────
def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    Pull the first JSON object out of an LLM reply. Tolerates markdown fences
    and prose before/after the object. Raises ValueError if none is found.
    """
    if not isinstance(text, str):
        raise ValueError("LLM response is not text")
    candidate = _strip_fences(text)
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(candidate[start:end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}") from e
    raise ValueError("LLM response contained no JSON object")


def coerce_score(raw: Any, max_marks: Optional[int]) -> int:
    """
    Turn whatever the model put in "score" into a safe integer.
    Non-numeric -> 0. Clamped to [0, max_marks] when max_marks is given.
    """
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    if value != value:  # NaN
        return 0
    score = int(round(value))
    if max_marks is not None and max_marks > 0:
        return max(0, min(score, int(max_marks)))
    return max(0, score)


# ── Low-level call ───────────────────────────────────────────────────────────
async def chat_completion(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: float = 300.0,
) -> str:
    """POST to LM Studio and return the assistant message text. Raises RuntimeError on failure."""
    payload = {
        "model": LM_STUDIO_MODEL or "default",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(LM_STUDIO_URL, json=payload)
    except httpx.HTTPError as e:
        raise RuntimeError(f"LM Studio is not reachable at {LM_STUDIO_URL}: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(f"LM Studio error {response.status_code}: {response.text[:300]}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected LM Studio response: {str(data)[:300]}") from e


async def lmstudio_status(timeout: float = 5.0) -> Dict[str, Any]:
    """
    Report whether LM Studio is reachable and which models are loaded.
    Uses the native /api/v0/models endpoint (has a 'state' field) and falls
    back to the OpenAI-style /v1/models list.
    """
    out: Dict[str, Any] = {
        "reachable": False,
        "url": LM_STUDIO_BASE,
        "configured_model": LM_STUDIO_MODEL or None,
        "loaded_models": [],
        "model_loaded": False,
        "error": None,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{LM_STUDIO_BASE}/api/v0/models")
            if r.status_code == 200:
                out["reachable"] = True
                models = r.json().get("data", [])
                out["loaded_models"] = [m.get("id") for m in models if m.get("state") == "loaded"]
                out["available_models"] = [m.get("id") for m in models]
            else:
                r = await client.get(f"{LM_STUDIO_BASE}/v1/models")
                r.raise_for_status()
                out["reachable"] = True
                out["loaded_models"] = [m.get("id") for m in r.json().get("data", [])]
                out["note"] = "/v1/models cannot distinguish loaded from downloaded models"
    except Exception as e:
        out["error"] = str(e)[:200]
        return out

    if out["loaded_models"]:
        out["model_loaded"] = (LM_STUDIO_MODEL in out["loaded_models"]) if LM_STUDIO_MODEL else True
    return out


# ── Grading ──────────────────────────────────────────────────────────────────
async def grade_exam(
    rubric_path: Path,
    answer_path: Path,
    max_marks: int,
    grading_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Given an assignment rubric and a student answer (PDF or image),
    ask LM Studio to analyze them and assign a score with explainable feedback.
    PDFs are converted to images before sending to the vision model.
    """
    rubric_images = file_to_base64_images(rubric_path)
    answer_images = file_to_base64_images(answer_path)

    if not rubric_images:
        raise RuntimeError(f"Could not read rubric file: {rubric_path}")
    if not answer_images:
        raise RuntimeError(f"Could not read answer file: {answer_path}")

    print(f"[LLM] Rubric: {len(rubric_images)} page(s), Answer: {len(answer_images)} page(s)")

    teacher_instructions = ""
    if grading_prompt:
        teacher_instructions = (
            f"\n\n--- TEACHER'S GRADING GUIDELINES ---\n"
            f"{grading_prompt}\n"
            f"--- END GUIDELINES ---\n\n"
            "You MUST follow the teacher's grading guidelines above when evaluating the student's work. "
        )

    system_prompt = "You are an AI teacher grading an exam. You MUST return ONLY valid JSON, no other text."

    num_rubric, num_answer = len(rubric_images), len(answer_images)
    if num_rubric == 1 and num_answer == 1:
        image_desc = "The first image is the Teacher's Assignment Question/Rubric. The second image is the Student's Answer."
    else:
        image_desc = (
            f"The first {num_rubric} image(s) are the Teacher's Assignment Question/Rubric. "
            f"The next {num_answer} image(s) are the Student's Answer."
        )

    user_prompt = (
        f"The total possible marks are {max_marks}. "
        f"{image_desc} "
        f"{teacher_instructions}"
        "Review the student's answers against the rubric. "
        "Break down your grading into individual criteria. For EACH criterion, explain WHY "
        "the student received those marks — what was correct, what was missing, or what was wrong. "
        "Return ONLY a raw JSON object with this EXACT format:\n"
        '{\n'
        '  "score": <integer total score>,\n'
        '  "feedback": "<one-line overall summary>",\n'
        '  "explainable_feedback": {\n'
        '    "overall_comment": "<2-3 sentence overall assessment>",\n'
        '    "criteria": [\n'
        '      {\n'
        '        "criterion": "<name of grading criterion>",\n'
        '        "marks_awarded": <int>,\n'
        '        "marks_possible": <int>,\n'
        '        "reason": "<specific explanation of why these marks were given>"\n'
        '      }\n'
        '    ],\n'
        '    "strengths": ["<strength 1>", "<strength 2>"],\n'
        '    "improvements": ["<area for improvement 1>", "<area for improvement 2>"]\n'
        '  }\n'
        '}'
    )

    content: List[Dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for img_url in rubric_images + answer_images:
        content.append({"type": "image_url", "image_url": {"url": img_url}})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    raw = await chat_completion(messages, temperature=0.1, max_tokens=2048, timeout=300.0)

    try:
        result_json = extract_json_object(raw)
    except ValueError as e:
        print(f"LLM returned invalid JSON: {e}")
        print(f"Raw response: {raw[:500]}")
        raise RuntimeError(f"LLM returned invalid JSON: {e}") from e

    score = coerce_score(result_json.get("score"), max_marks)
    feedback = str(result_json.get("feedback") or "No feedback provided.")
    explainable = result_json.get("explainable_feedback")

    if not isinstance(explainable, dict):
        explainable = {"overall_comment": feedback, "criteria": [], "strengths": [], "improvements": []}
    else:
        criteria = []
        for c in explainable.get("criteria") or []:
            if isinstance(c, dict):
                criteria.append({
                    "criterion": str(c.get("criterion", "")),
                    "marks_awarded": coerce_score(c.get("marks_awarded"), None),
                    "marks_possible": coerce_score(c.get("marks_possible"), None),
                    "reason": str(c.get("reason", "")),
                })
        explainable["criteria"] = criteria
        explainable.setdefault("overall_comment", feedback)
        explainable["strengths"] = [str(s) for s in (explainable.get("strengths") or [])]
        explainable["improvements"] = [str(s) for s in (explainable.get("improvements") or [])]

    return {"score": score, "feedback": feedback, "explainable_feedback": explainable}
