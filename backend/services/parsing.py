"""
Module 7: Parsing Module
- Split answers by question numbers
- Clean text (remove noise, normalize whitespace)
- Match student answers to question numbers
- Prepare structured input for grading
"""
import re
from typing import List, Dict, Optional


def clean_text(text: str) -> str:
    """Remove OCR noise, normalize whitespace, fix common artifacts."""
    # Remove non-printable characters except newlines
    text = re.sub(r"[^\x20-\x7E\n\u0600-\u06FF\u0750-\u077F]", " ", text)
    # Normalize multiple spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def split_answers(text: str) -> List[Dict[str, any]]:
    """
    Split text into individual answers based on question number patterns.
    Recognizes patterns like:
    - Q1, Q2, Q.1, Q 1
    - Question 1, Question 2
    - 1., 2., 3.
    - 1), 2), 3)
    - (a), (b), (c)
    - Ans 1, Answer 1
    """
    # Common question/answer number patterns
    patterns = [
        r"(?:^|\n)\s*(?:Q(?:uestion)?\.?\s*)(\d+)[.):]\s*",
        r"(?:^|\n)\s*(?:Ans(?:wer)?\.?\s*)(\d+)[.):]\s*",
        r"(?:^|\n)\s*(\d+)\s*[.)]\s+",
        r"(?:^|\n)\s*\(([a-zA-Z])\)\s+",
    ]

    # Try each pattern to find the best split
    best_splits = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        if len(matches) >= 2 and len(matches) > len(best_splits):
            best_splits = matches

    if not best_splits:
        # No question markers found, return entire text as one answer
        return [{"question_number": "1", "answer_text": clean_text(text), "raw_position": 0}]

    answers = []
    for i, match in enumerate(best_splits):
        q_num = match.group(1)
        start = match.end()
        end = best_splits[i + 1].start() if i + 1 < len(best_splits) else len(text)
        answer_text = text[start:end].strip()
        answers.append({
            "question_number": str(q_num),
            "answer_text": clean_text(answer_text),
            "raw_position": match.start(),
        })

    return answers


def match_questions_to_rubric(
    student_answers: List[Dict],
    rubric_text: str,
) -> List[Dict[str, any]]:
    """
    Match student answers to rubric questions.
    Returns paired list of {question, expected_keywords, student_answer}.
    """
    rubric_questions = split_answers(rubric_text)

    matched = []
    rubric_map = {q["question_number"]: q for q in rubric_questions}

    for ans in student_answers:
        q_num = ans["question_number"]
        rubric_q = rubric_map.get(q_num, None)

        matched.append({
            "question_number": q_num,
            "student_answer": ans["answer_text"],
            "rubric_text": rubric_q["answer_text"] if rubric_q else None,
            "matched": rubric_q is not None,
        })

    return matched


def prepare_grading_input(
    rubric_text: str,
    answer_text: str,
) -> Dict[str, any]:
    """
    Full pipeline: clean both texts, split answers, match to rubric.
    Returns structured data ready for the grading engine.
    """
    clean_rubric = clean_text(rubric_text)
    clean_answer = clean_text(answer_text)

    student_answers = split_answers(clean_answer)
    matched = match_questions_to_rubric(student_answers, clean_rubric)

    return {
        "total_questions_found": len(student_answers),
        "matched_pairs": matched,
        "rubric_clean": clean_rubric,
        "answer_clean": clean_answer,
    }
