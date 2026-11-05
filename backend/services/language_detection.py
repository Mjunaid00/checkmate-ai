"""
Module 5: Language Detection Module
- Detect natural language of text (English, Urdu, etc.)
- Detect programming language from code snippets
- Classify content type (descriptive text vs code vs mixed)
"""
import re
from typing import Dict, Literal

# Programming language detection patterns
LANG_PATTERNS: Dict[str, list] = {
    "python": [
        r"\bdef\s+\w+\s*\(", r"\bimport\s+\w+", r"\bclass\s+\w+\s*[:\(]",
        r"\bprint\s*\(", r"\bif\s+.*:", r"\bfor\s+\w+\s+in\s+",
        r"\bwhile\s+.*:", r"\breturn\s+", r"\bself\.", r"\belif\s+",
    ],
    "java": [
        r"\bpublic\s+(static\s+)?void\s+main", r"\bSystem\.out\.print",
        r"\bclass\s+\w+\s*\{", r"\bimport\s+java\.", r"\bprivate\s+\w+",
        r"\bnew\s+\w+\(", r"\bpublic\s+class\b", r"\bString\[\]\s+args",
    ],
    "c": [
        r"#include\s*<\w+\.h>", r"\bprintf\s*\(", r"\bscanf\s*\(",
        r"\bint\s+main\s*\(", r"\bvoid\s+\w+\s*\(", r"\bmalloc\s*\(",
        r"\bstruct\s+\w+", r"->",
    ],
    "cpp": [
        r"#include\s*<iostream>", r"\bcout\s*<<", r"\bcin\s*>>",
        r"\busing\s+namespace\s+std", r"\bstd::", r"\bclass\s+\w+\s*\{",
        r"\bvector\s*<", r"\btemplate\s*<",
    ],
    "javascript": [
        r"\bfunction\s+\w+\s*\(", r"\bconst\s+\w+\s*=", r"\blet\s+\w+\s*=",
        r"\bconsole\.log\s*\(", r"\bdocument\.\w+", r"=>\s*\{",
        r"\brequire\s*\(", r"\bmodule\.exports",
    ],
    "sql": [
        r"\bSELECT\b.*\bFROM\b", r"\bINSERT\s+INTO\b", r"\bUPDATE\b.*\bSET\b",
        r"\bCREATE\s+TABLE\b", r"\bDROP\s+TABLE\b", r"\bALTER\s+TABLE\b",
        r"\bWHERE\b", r"\bJOIN\b",
    ],
}


def detect_programming_language(text: str) -> Dict[str, any]:
    """
    Detect the most likely programming language in a text block.
    Returns: {"language": str, "confidence": float, "is_code": bool}
    """
    scores = {}
    for lang, patterns in LANG_PATTERNS.items():
        count = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE | re.MULTILINE))
        scores[lang] = count / len(patterns)

    if not scores or max(scores.values()) < 0.15:
        return {"language": "none", "confidence": 0.0, "is_code": False}

    best_lang = max(scores, key=scores.get)
    confidence = scores[best_lang]

    return {
        "language": best_lang,
        "confidence": round(confidence, 2),
        "is_code": confidence >= 0.2,
    }


def detect_natural_language(text: str) -> str:
    """
    Simple natural language detection based on Unicode ranges and common words.
    Returns language code: 'en', 'ur', 'ar', 'unknown'
    """
    # Check for Urdu/Arabic script
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    total_alpha = len(re.findall(r"[a-zA-Z\u0600-\u06FF]", text)) or 1

    if arabic_chars / total_alpha > 0.3:
        # Distinguish Urdu from Arabic using common Urdu words
        urdu_markers = ["ہے", "کے", "کا", "میں", "سے", "نے", "کی", "ہیں", "کو"]
        if any(m in text for m in urdu_markers):
            return "ur"
        return "ar"

    return "en"


ContentType = Literal["descriptive", "code", "mixed"]


def classify_content(text: str) -> Dict[str, any]:
    """
    Classify content as descriptive text, code, or mixed.
    Returns full analysis with language info.
    """
    prog_info = detect_programming_language(text)
    nat_lang = detect_natural_language(text)

    # Count code-like lines vs prose lines
    lines = text.strip().split("\n")
    code_indicators = 0
    for line in lines:
        stripped = line.strip()
        if (
            re.match(r"^[{}();]$", stripped)
            or re.match(r"^\s*(#|//|/\*|\*)", stripped)
            or re.search(r"[{};]\s*$", stripped)
            or re.search(r"^\s*(def |class |import |from |#include|public |private )", stripped)
        ):
            code_indicators += 1

    code_ratio = code_indicators / max(len(lines), 1)

    if code_ratio > 0.4 and prog_info["is_code"]:
        content_type: ContentType = "code"
    elif code_ratio > 0.15 or prog_info["is_code"]:
        content_type = "mixed"
    else:
        content_type = "descriptive"

    return {
        "content_type": content_type,
        "natural_language": nat_lang,
        "programming_language": prog_info["language"] if prog_info["is_code"] else None,
        "programming_confidence": prog_info["confidence"],
        "code_ratio": round(code_ratio, 2),
    }
