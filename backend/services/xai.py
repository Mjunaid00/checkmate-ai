"""
Module 11: Explainable AI (XAI) Module
- Explain grading results with detailed reasoning
- Highlight missing keywords from rubric
- Show specific mistakes in student answers
- Generate actionable feedback
"""
import re
from typing import List, Dict, Optional


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract important keywords from rubric/expected answer text."""
    # Remove common stop words
    stop_words = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "but",
        "in", "with", "to", "for", "of", "not", "no", "can", "has", "have",
        "had", "are", "was", "were", "be", "been", "being", "do", "does",
        "did", "will", "would", "could", "should", "may", "might", "shall",
        "this", "that", "these", "those", "it", "its", "they", "them",
        "their", "what", "when", "where", "how", "why", "who", "whom",
        "from", "into", "each", "every", "all", "both", "few", "more",
        "most", "other", "some", "such", "than", "too", "very", "also",
    }

    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    keywords = [w for w in words if len(w) >= min_length and w not in stop_words]

    # Count frequency and return unique keywords sorted by frequency
    freq = {}
    for w in keywords:
        freq[w] = freq.get(w, 0) + 1

    sorted_kw = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)
    return sorted_kw[:30]  # Top 30 keywords


def find_missing_keywords(rubric_text: str, student_text: str) -> Dict[str, any]:
    """
    Compare rubric keywords against student answer.
    Returns matched and missing keywords.
    """
    rubric_kw = extract_keywords(rubric_text)
    student_lower = student_text.lower()

    matched = []
    missing = []

    for kw in rubric_kw:
        if kw in student_lower:
            matched.append(kw)
        else:
            missing.append(kw)

    coverage = len(matched) / max(len(rubric_kw), 1)

    return {
        "rubric_keywords": rubric_kw,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "keyword_coverage": round(coverage * 100, 1),
    }


def detect_mistakes(student_text: str) -> List[Dict[str, str]]:
    """
    Detect common mistakes in student answers.
    Returns list of {type, description, location}.
    """
    mistakes = []

    # Check for very short answers
    words = student_text.split()
    if len(words) < 10:
        mistakes.append({
            "type": "incomplete",
            "description": "Answer appears very short and may be incomplete",
            "severity": "high",
        })

    # Check for repeated content (copy-paste)
    sentences = re.split(r"[.!?]+", student_text)
    seen = set()
    for s in sentences:
        s_clean = s.strip().lower()
        if len(s_clean) > 20 and s_clean in seen:
            mistakes.append({
                "type": "repetition",
                "description": f"Repeated content detected: '{s.strip()[:50]}...'",
                "severity": "medium",
            })
        seen.add(s_clean)

    # Check for off-topic indicators
    off_topic_phrases = [
        "i don't know", "i dont know", "no idea", "skip", "not sure",
        "i can't answer", "leave blank", "n/a",
    ]
    for phrase in off_topic_phrases:
        if phrase in student_text.lower():
            mistakes.append({
                "type": "unanswered",
                "description": f"Student indicated they cannot answer: '{phrase}'",
                "severity": "high",
            })

    return mistakes


def generate_xai_feedback(
    rubric_text: Optional[str],
    student_text: str,
    score: int,
    max_marks: int,
    llm_feedback: Optional[Dict] = None,
) -> Dict[str, any]:
    """
    Generate comprehensive explainable feedback combining all XAI signals.
    Returns structured feedback with keyword analysis, mistakes, and recommendations.
    """
    # Keyword analysis
    keyword_analysis = None
    if rubric_text:
        keyword_analysis = find_missing_keywords(rubric_text, student_text)

    # Mistake detection
    mistakes = detect_mistakes(student_text)

    # Performance level
    percentage = (score / max(max_marks, 1)) * 100
    if percentage >= 85:
        performance = "excellent"
    elif percentage >= 70:
        performance = "good"
    elif percentage >= 50:
        performance = "average"
    elif percentage >= 30:
        performance = "below_average"
    else:
        performance = "needs_improvement"

    # Build recommendations
    recommendations = []
    if keyword_analysis and keyword_analysis["missing_keywords"]:
        top_missing = keyword_analysis["missing_keywords"][:5]
        recommendations.append(
            f"Review these key concepts: {', '.join(top_missing)}"
        )
    if any(m["type"] == "incomplete" for m in mistakes):
        recommendations.append("Provide more detailed and complete answers")
    if any(m["type"] == "repetition" for m in mistakes):
        recommendations.append("Avoid repeating the same points — add new information instead")
    if percentage < 50:
        recommendations.append("Revisit the topic fundamentals and study the rubric guidelines")

    return {
        "score": score,
        "max_marks": max_marks,
        "percentage": round(percentage, 1),
        "performance_level": performance,
        "keyword_analysis": keyword_analysis,
        "mistakes_detected": mistakes,
        "recommendations": recommendations,
        "llm_feedback": llm_feedback,
    }
