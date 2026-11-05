"""
AI Quiz Generator — uses LM Studio to generate MCQ questions
from a topic/description or from extracted document text.
"""
from typing import List, Dict, Optional

from core.llm import chat_completion, extract_json_object


async def generate_quiz_questions(
    topic: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    source_text: Optional[str] = None,
) -> List[Dict]:
    """
    Generate MCQ questions using the LLM.
    Returns a list of {question_text, options[4], correct_index, marks, explanation}.
    """
    num_questions = max(1, min(num_questions, 25))

    context = ""
    if source_text:
        # Limit source text to keep prompt manageable
        context = f"\n\nBase the questions on this material:\n---\n{source_text[:6000]}\n---\n"

    system_prompt = (
        "You are an expert exam writer. You ONLY return valid JSON, never any other text or markdown."
    )

    user_prompt = (
        f"Generate {num_questions} multiple-choice questions about: {topic}\n"
        f"Difficulty: {difficulty}{context}\n\n"
        "Rules:\n"
        "- Each question MUST have exactly 4 options\n"
        "- Mark exactly ONE option as correct\n"
        "- Make distractors plausible but clearly wrong on close reading\n"
        "- Include a brief explanation for the correct answer\n"
        "- Each question worth 1 mark\n\n"
        "Return ONLY this JSON structure:\n"
        '{\n'
        '  "questions": [\n'
        '    {\n'
        '      "question_text": "<the question>",\n'
        '      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],\n'
        '      "correct_index": <0|1|2|3>,\n'
        '      "marks": 1,\n'
        '      "explanation": "<brief reason why the correct answer is right>"\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = await chat_completion(messages, temperature=0.4, max_tokens=4096, timeout=180.0)
        result = extract_json_object(raw)
    except ValueError as e:
        print(f"Quiz generator returned invalid JSON: {e}")
        raise RuntimeError(f"AI returned invalid JSON: {e}") from e
    except Exception as e:
        print(f"Error generating quiz via LM Studio: {e}")
        raise RuntimeError(f"Failed to generate quiz: {e}") from e

    questions = result.get("questions", [])
    if not isinstance(questions, list):
        return []

    # Validate and clean questions
    valid = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
            continue
        ci = q.get("correct_index")
        if not isinstance(ci, int) or ci < 0 or ci > 3:
            continue
        if not q.get("question_text"):
            continue
        try:
            marks = max(1, int(q.get("marks", 1)))
        except (TypeError, ValueError):
            marks = 1
        valid.append({
            "question_text": str(q["question_text"]).strip(),
            "options": [str(o).strip() for o in q["options"]],
            "correct_index": ci,
            "marks": marks,
            "explanation": str(q.get("explanation", "")).strip() or None,
        })

    return valid
