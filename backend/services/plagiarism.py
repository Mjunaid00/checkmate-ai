"""
Plagiarism / Similarity Detection Service
- Compares submission texts using shingled token overlap (Jaccard similarity)
- Records pairwise similarity to flag potential duplicates
- Uses already-OCR'd text from the grading pipeline if available, else re-extracts
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from bson import ObjectId


SHINGLE_SIZE = 5  # token n-gram size
SIMILARITY_THRESHOLD = 0.30  # below this we don't store partner info (still flag highest)


def _normalize(text: str) -> List[str]:
    """Lowercase, strip punctuation, split into tokens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9؀-ۿ\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1]


def _shingles(tokens: List[str], k: int = SHINGLE_SIZE) -> set:
    """Generate set of k-token shingles."""
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity coefficient — |A ∩ B| / |A ∪ B|."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


async def _get_submission_text(db, submission: dict) -> Optional[str]:
    """Try to fetch the OCR-extracted text for a submission. Falls back to re-extraction."""
    # Use cached extraction if grading pipeline saved it
    cached = submission.get("extracted_text")
    if cached:
        return cached

    answer_path = submission.get("answer_file_path")
    if not answer_path:
        return None

    try:
        import asyncio
        from services.ocr import extract_text
        from config import absolute_upload_path
        full_path = absolute_upload_path(answer_path)
        if not full_path.exists():
            return None
        text = await asyncio.to_thread(extract_text, full_path)
        # Cache it on the submission for future runs
        await db["submissions"].update_one(
            {"_id": submission["_id"]},
            {"$set": {"extracted_text": text}},
        )
        return text
    except Exception as e:
        print(f"[Plagiarism] OCR failed for submission {submission.get('_id')}: {e}")
        return None


async def check_assignment_plagiarism(db, assignment_id: str) -> Dict:
    """
    Compare all submissions for the given assignment pairwise and store
    each submission's max similarity + the most-similar partner.
    Returns a summary report.
    """
    submissions = await db["submissions"].find({"assignment_id": assignment_id}).to_list(length=500)
    if len(submissions) < 2:
        return {
            "checked": len(submissions),
            "pairs": [],
            "message": "Need at least 2 submissions to compare.",
        }

    # Extract text for each submission
    texts: List[Tuple[str, set]] = []  # (submission_id, shingle_set)
    skipped: List[str] = []
    for sub in submissions:
        text = await _get_submission_text(db, sub)
        sid = str(sub["_id"])
        if not text or len(text) < 30:
            skipped.append(sid)
            continue
        sh = _shingles(_normalize(text))
        texts.append((sid, sh))

    # Pairwise comparison
    n = len(texts)
    high_pairs: List[Dict] = []
    per_submission_max: Dict[str, Tuple[float, str]] = {}  # sid -> (max_score, partner_sid)

    for i in range(n):
        sid_i, set_i = texts[i]
        for j in range(i + 1, n):
            sid_j, set_j = texts[j]
            sim = jaccard(set_i, set_j)
            if sim < 0.05:
                continue
            # Track max for each
            if sid_i not in per_submission_max or sim > per_submission_max[sid_i][0]:
                per_submission_max[sid_i] = (sim, sid_j)
            if sid_j not in per_submission_max or sim > per_submission_max[sid_j][0]:
                per_submission_max[sid_j] = (sim, sid_i)
            if sim >= SIMILARITY_THRESHOLD:
                high_pairs.append({
                    "submission_a": sid_i,
                    "submission_b": sid_j,
                    "similarity": round(sim, 3),
                })

    # Persist results on each submission
    now = datetime.utcnow()
    for sub in submissions:
        sid = str(sub["_id"])
        if sid in per_submission_max:
            sim, partner = per_submission_max[sid]
            await db["submissions"].update_one(
                {"_id": sub["_id"]},
                {"$set": {
                    "similarity_max": round(sim, 3),
                    "similarity_partner_id": partner,
                    "plagiarism_checked_at": now,
                }},
            )
        else:
            # Reset to 0 — clean
            await db["submissions"].update_one(
                {"_id": sub["_id"]},
                {"$set": {
                    "similarity_max": 0.0,
                    "similarity_partner_id": None,
                    "plagiarism_checked_at": now,
                }},
            )

    # Sort high pairs descending
    high_pairs.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "checked": len(texts),
        "skipped": len(skipped),
        "total_pairs": n * (n - 1) // 2,
        "flagged_pairs": len(high_pairs),
        "threshold": SIMILARITY_THRESHOLD,
        "pairs": high_pairs[:50],  # top 50 most similar pairs
        "completed_at": now.isoformat(),
    }


def validate_format(filename: str, content_type: str, allowed_formats: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Validate uploaded file against the assignment's allowed formats.
    Returns (ok, error_message).
    """
    base_allowed = {"application/pdf", "image/jpeg", "image/png"}
    extension = Path(filename or "").suffix.lower().lstrip(".")

    # Check base whitelist
    if content_type not in base_allowed:
        return False, f"File type '{content_type}' is not supported."

    if not allowed_formats:
        return True, ""

    # Map extensions: pdf, jpg/jpeg, png
    normalized_ext = "jpg" if extension == "jpeg" else extension
    allowed_lower = [f.lower().lstrip(".") for f in allowed_formats]
    allowed_lower = ["jpg" if a == "jpeg" else a for a in allowed_lower]

    if normalized_ext not in allowed_lower:
        return False, f"This assignment requires {', '.join(allowed_lower)} files only. You uploaded a .{extension} file."

    return True, ""
