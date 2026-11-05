"""
OMR / Structured Sheet Processor
Uses LM Studio vision model to read filled OMR / True-False bubble sheets.
Returns the index of the marked option per question.
"""
import base64
import io
from pathlib import Path
from typing import List, Dict, Any

from config import absolute_upload_path
from core.llm import chat_completion, extract_json_object


def _file_to_base64_png(file_path: Path) -> str:
    """Convert any supported file (PDF first page, PNG, JPG) to a base64 PNG data URL."""
    suffix = file_path.suffix.lower()

    if suffix in (".png", ".jpg", ".jpeg"):
        with open(file_path, "rb") as f:
            raw = f.read()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(file_path))
            if len(doc) == 0:
                raise RuntimeError("PDF has no pages")
            page = doc[0]
            bitmap = page.render(scale=2)
            pil_img = bitmap.to_pil()
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            doc.close()
            return f"data:image/png;base64,{b64}"
        except Exception as e:
            raise RuntimeError(f"Failed to convert PDF: {e}") from e

    raise RuntimeError(f"Unsupported file type: {suffix}")


async def detect_omr_answers(
    sheet_path: Path,
    num_questions: int,
    options_per_question: int,
    sheet_type: str = "mcq",
) -> List[int]:
    """
    Send the filled sheet image to the vision LLM and extract marked answers.
    Returns a list of length num_questions; each entry is the marked option index
    (0-based) or -1 if the bubble is blank/unclear/multiple-marked.
    """
    image_url = _file_to_base64_png(sheet_path)

    if sheet_type == "true_false":
        option_labels = "T (True) or F (False)"
        option_explainer = "T=0, F=1"
    else:
        labels = [chr(65 + i) for i in range(options_per_question)]
        option_labels = " / ".join(labels)
        option_explainer = ", ".join(f"{label}={i}" for i, label in enumerate(labels))

    system_prompt = (
        "You are a strict OMR sheet grader. You ONLY return valid JSON with no extra text or markdown. "
        "Detect which bubble is filled per question. If multiple bubbles are filled or the answer is unclear or blank, return -1 for that question."
    )

    user_prompt = (
        f"This is a filled {'True/False' if sheet_type == 'true_false' else 'multiple-choice'} answer sheet with "
        f"{num_questions} questions and {options_per_question} options per question ({option_labels}).\n"
        f"Index each option as 0-based: {option_explainer}.\n\n"
        f"For each question 1 through {num_questions}, identify which bubble is filled (darkened/marked).\n"
        f"Return ONLY this JSON shape:\n"
        '{\n'
        '  "answers": [<int>, <int>, ... ]\n'
        '}\n\n'
        f"Rules:\n"
        f"- The list MUST have exactly {num_questions} entries.\n"
        f"- Each entry is an integer in [0, {options_per_question - 1}] OR -1 if blank/unclear/multi-marked.\n"
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

    answers = result.get("answers", [])
    if not isinstance(answers, list):
        answers = []

    cleaned: List[int] = []
    for i in range(num_questions):
        a = answers[i] if i < len(answers) else -1
        if isinstance(a, bool):
            a = -1
        if isinstance(a, int) and -1 <= a < options_per_question:
            cleaned.append(a)
        else:
            cleaned.append(-1)
    return cleaned


def grade_omr_answers(
    detected: List[int],
    answer_key: List[int],
    marks_per_question: int,
    negative_marking: float = 0.0,
) -> Dict[str, Any]:
    """Compare detected answers to the key and compute score breakdown."""
    correct = 0
    incorrect = 0
    blank = 0
    for i, ans in enumerate(detected):
        if i >= len(answer_key):
            break
        if ans == -1:
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

        detected = await detect_omr_answers(
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
                "score": result["score"],
                "percentage": result["percentage"],
            }},
        )

        # Notify
        from services.notifications import notify_user
        sub = await db["omr_submissions"].find_one({"_id": obj_id})
        if sub and sub.get("submitter_id") and sub.get("submitter_role") == "student":
            await notify_user(
                db,
                user_id=sub["submitter_id"],
                title="OMR sheet graded",
                body=f"'{template.get('title', 'OMR')}' — scored {result['score']}/{result['total_marks']} ({result['percentage']}%)",
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
