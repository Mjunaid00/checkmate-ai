"""
OMR / Structured Sheet Processor
Uses the LM Studio vision model to read filled OMR / True-False bubble sheets.

Per question the model returns the index of the marked option, -1 when the bubble is
blank or unreadable, and -2 when more than one bubble is filled. Multiple marks and
mostly-blank sheets are flagged for the teacher's review (needs_review).

Before the image goes to the model it is prepared (prepare_sheet_image): EXIF rotation
applied, converted to greyscale, contrast stretched, and capped to MAX_SHEET_SIDE pixels.
"""
import base64
import io
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageOps

from config import absolute_upload_path
from core.llm import chat_completion, extract_json_object

MAX_SHEET_SIDE = 1600
BLANK = -1
MULTIPLE = -2


def prepare_sheet_image(img: Image.Image) -> Image.Image:
    """Rotation from EXIF, greyscale, contrast stretch, size cap. Returns a new image."""
    out = ImageOps.exif_transpose(img) or img
    out = out.convert("L")
    out = ImageOps.autocontrast(out, cutoff=0.5)
    if max(out.size) > MAX_SHEET_SIDE:
        out = out.copy()
        out.thumbnail((MAX_SHEET_SIDE, MAX_SHEET_SIDE), Image.LANCZOS)
    return out


def load_sheet_image(file_path: Path) -> Tuple[Image.Image, List[str]]:
    """Open an image or render the first PDF page. Returns (prepared image, warnings)."""
    suffix = file_path.suffix.lower()
    warnings: List[str] = []
    if suffix in (".png", ".jpg", ".jpeg"):
        with Image.open(file_path) as img:
            img.load()
            return prepare_sheet_image(img), warnings
    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(file_path))
            try:
                if len(doc) == 0:
                    raise RuntimeError("PDF has no pages")
                if len(doc) > 1:
                    warnings.append(f"PDF has {len(doc)} pages; only the first page was read")
                pil_img = doc[0].render(scale=2).to_pil()
            finally:
                doc.close()
            return prepare_sheet_image(pil_img), warnings
        except Exception as e:
            raise RuntimeError(f"Failed to convert PDF: {e}") from e
    raise RuntimeError(f"Unsupported file type: {suffix}")


def _to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def clean_detected_answers(answers: Any, num_questions: int, options_per_question: int) -> List[int]:
    """Exactly num_questions entries: a valid option index, BLANK (-1) or MULTIPLE (-2)."""
    if not isinstance(answers, list):
        answers = []
    cleaned: List[int] = []
    for i in range(num_questions):
        a = answers[i] if i < len(answers) else BLANK
        if isinstance(a, bool) or not isinstance(a, int):
            cleaned.append(BLANK)
        elif a in (BLANK, MULTIPLE) or 0 <= a < options_per_question:
            cleaned.append(a)
        else:
            cleaned.append(BLANK)
    return cleaned


async def detect_omr_answers(
    sheet_path: Path,
    num_questions: int,
    options_per_question: int,
    sheet_type: str = "mcq",
) -> Tuple[List[int], List[str]]:
    """
    Send the prepared sheet image to the vision model and extract marked answers.
    Returns (answers, warnings): one entry per question, option index / -1 blank / -2 multiple.
    """
    image, warnings = load_sheet_image(sheet_path)
    image_url = _to_data_url(image)

    if sheet_type == "true_false":
        option_labels = "T (True) or F (False)"
        option_explainer = "T=0, F=1"
    else:
        labels = [chr(65 + i) for i in range(options_per_question)]
        option_labels = " / ".join(labels)
        option_explainer = ", ".join(f"{label}={i}" for i, label in enumerate(labels))

    system_prompt = (
        "You are a strict OMR sheet grader. You ONLY return valid JSON with no extra text or markdown. "
        "Detect which bubble is filled per question. Return -1 when the question is blank or unreadable, "
        "and -2 when MORE THAN ONE bubble is filled for the same question."
    )

    user_prompt = (
        f"This is a filled {'True/False' if sheet_type == 'true_false' else 'multiple-choice'} answer sheet with "
        f"{num_questions} questions and {options_per_question} options per question ({option_labels}).\n"
        f"Index each option as 0-based: {option_explainer}.\n\n"
        f"For each question 1 through {num_questions}, identify which bubble is filled (darkened/marked). "
        "The photo may be slightly rotated, shadowed or creased; judge by the darkest bubble in each row.\n"
        f"Return ONLY this JSON shape:\n"
        '{\n'
        '  "answers": [<int>, <int>, ... ]\n'
        '}\n\n'
        f"Rules:\n"
        f"- The list MUST have exactly {num_questions} entries.\n"
        f"- Each entry is an integer in [0, {options_per_question - 1}], or -1 if blank/unreadable, or -2 if several bubbles are filled.\n"
        f"- Do NOT explain. Do NOT wrap in markdown. Output ONLY the JSON object."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]

    raw = await chat_completion(messages, temperature=0.0, max_tokens=2048, timeout=180.0)
    try:
        result = extract_json_object(raw)
    except ValueError as e:
        print(f"[OMR] Invalid JSON from LLM: {e}")
        print(f"[OMR] Raw: {raw[:300]}")
        raise RuntimeError(f"OMR detection returned invalid JSON: {e}") from e

    return clean_detected_answers(result.get("answers", []), num_questions, options_per_question), warnings


def grade_omr_answers(
    detected: List[int],
    answer_key: List[int],
    marks_per_question: int,
    negative_marking: float = 0.0,
) -> Dict[str, Any]:
    """
    Compare detected answers to the key. Blank (-1) and multiple-marked (-2) questions earn
    nothing and are not penalised; multiple marks are listed in `multiple_marked` and set
    `needs_review`, as does a sheet that is more than half blank (probably a bad scan).
    """
    correct = incorrect = blank = multiple = 0
    multiple_marked: List[int] = []
    for i, ans in enumerate(detected):
        if i >= len(answer_key):
            break
        if ans == MULTIPLE:
            multiple += 1
            multiple_marked.append(i)
        elif ans == BLANK:
            blank += 1
        elif ans == answer_key[i]:
            correct += 1
        else:
            incorrect += 1

    total_marks = len(answer_key) * marks_per_question
    raw_score = (correct * marks_per_question) - (incorrect * negative_marking)
    score = max(0.0, round(raw_score, 2))
    percentage = round((score / max(total_marks, 1)) * 100, 1)

    return {
        "correct_count": correct,
        "incorrect_count": incorrect,
        "blank_count": blank,
        "multiple_count": multiple,
        "multiple_marked": multiple_marked,
        "needs_review": multiple > 0 or (len(answer_key) > 0 and blank > len(answer_key) / 2),
        "score": score,
        "total_marks": total_marks,
        "percentage": percentage,
    }


async def process_omr_sheet(
    db,
    submission_id: str,
    sheet_relative_path: str,
    template: dict,
) -> None:
    """
    Background task: detect answers on a sheet, grade, save results.
    """
    from bson import ObjectId
    obj_id = ObjectId(submission_id)

    await db["omr_submissions"].update_one(
        {"_id": obj_id},
        {"$set": {"status": "processing"}},
    )

    try:
        sheet_path = absolute_upload_path(sheet_relative_path)

        detected, warnings = await detect_omr_answers(
            sheet_path,
            num_questions=template["num_questions"],
            options_per_question=template["options_per_question"],
            sheet_type=template.get("sheet_type", "mcq"),
        )

        result = grade_omr_answers(
            detected,
            template["answer_key"],
            template.get("marks_per_question", 1),
            template.get("negative_marking", 0.0),
        )

        await db["omr_submissions"].update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "graded",
                "detected_answers": detected,
                "correct_count": result["correct_count"],
                "incorrect_count": result["incorrect_count"],
                "blank_count": result["blank_count"],
                "multiple_count": result["multiple_count"],
                "multiple_marked": result["multiple_marked"],
                "needs_review": result["needs_review"],
                "warnings": warnings,
                "score": result["score"],
                "percentage": result["percentage"],
            }},
        )

        # Notify
        from services.notifications import notify_user
        sub = await db["omr_submissions"].find_one({"_id": obj_id})
        if sub and sub.get("submitter_id") and sub.get("submitter_role") == "student":
            review_note = " (flagged for teacher review)" if result["needs_review"] else ""
            await notify_user(
                db,
                user_id=sub["submitter_id"],
                title="OMR sheet graded",
                body=f"'{template.get('title', 'OMR')}' — scored {result['score']}/{result['total_marks']} ({result['percentage']}%){review_note}",
                link="/",
                category="grading",
            )

    except Exception as e:
        print(f"[OMR] Failed to process {submission_id}: {e}")
        await db["omr_submissions"].update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "failed",
                "error_message": str(e),
            }},
        )
