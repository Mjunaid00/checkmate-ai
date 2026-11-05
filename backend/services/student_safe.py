"""
Views of teacher data that are safe to hand to students.
"""
import copy
from datetime import datetime
from typing import Any, Dict, Optional


def student_safe_assignment(doc: Dict[str, Any]) -> Dict[str, Any]:
    """The grading prompt describes what earns marks: never send it to students."""
    out = dict(doc)
    out["grading_prompt"] = None
    return out


def redact_keyword_analysis(submission: Dict[str, Any], deadline: Optional[datetime], now: datetime) -> Dict[str, Any]:
    """
    The rubric keyword lists in the XAI feedback reveal the rubric. A student may see them
    only once the assignment deadline has passed (so they cannot be passed on to classmates
    who have not submitted). Without a deadline they stay hidden. keyword_coverage stays.
    """
    xai = (submission.get("explainable_feedback") or {}).get("xai") or {}
    analysis = xai.get("keyword_analysis")
    if not isinstance(analysis, dict):
        return submission
    if deadline is not None and now >= deadline:
        return submission
    out = copy.deepcopy(submission)
    redacted = out["explainable_feedback"]["xai"]["keyword_analysis"]
    for key in ("rubric_keywords", "matched_keywords", "missing_keywords"):
        if key in redacted:
            redacted[key] = []
    redacted["hidden_until_deadline"] = True
    return out
