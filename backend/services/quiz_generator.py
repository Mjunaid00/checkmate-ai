"""
AI question generator - asks the LM Studio model for multiple-choice and/or true/false
questions about a topic, optionally grounded in uploaded reference material and shaped by
grade level, subject and learning objectives.

build_prompt() and clean_generated_questions() are pure and unit-tested; only
generate_quiz_questions() talks to the model. It asks for exactly the requested number and,
when the model returns fewer (a 7B model copying the one-item example was returning a single
question for short topics), asks again for the missing ones - up to MAX_GENERATION_ROUNDS.
"""
from typing import Dict, List, Optional

from core.llm import chat_completion, extract_json_object
from services.quiz_logic import normalize_answer

SOURCE_TEXT_LIMIT = 6000
QUESTION_TYPES = ("mcq", "true_false", "mixed")
TRUE_FALSE_OPTIONS = ["True", "False"]
MAX_QUESTIONS = 25
MAX_GENERATION_ROUNDS = 3  # first request + up to two top-up requests for missing questions


class GenerationError(RuntimeError):
    """The model did not answer or did not return usable JSON."""


def _example_item(label: str, example_type: str, example_options: str, example_ci: str) -> str:
    return (
        "    {\n"
        f'      "type": {example_type},\n'
        f'      "question_text": "<{label}>",\n'
        f'      "options": {example_options},\n'
        f'      "correct_index": {example_ci},\n'
        '      "marks": 1,\n'
        '      "explanation": "<brief reason why the correct answer is right>"\n'
        "    }"
    )


def build_prompt(topic: str, num_questions: int, difficulty: str, question_type: str = "mcq",
                 source_text: Optional[str] = None, grade_level: Optional[str] = None,
                 subject: Optional[str] = None, objectives: Optional[str] = None,
                 avoid: Optional[List[str]] = None) -> str:
    num_questions = max(1, min(int(num_questions or 1), MAX_QUESTIONS))
    question_type = question_type if question_type in QUESTION_TYPES else "mcq"

    context_lines = []
    if subject and subject.strip():
        context_lines.append(f"Subject: {subject.strip()}")
    if grade_level and grade_level.strip():
        context_lines.append(f"Grade level / audience: {grade_level.strip()}")
    if objectives and objectives.strip():
        context_lines.append(f"Learning objectives the questions must assess:\n{objectives.strip()}")
    context = ("\n" + "\n".join(context_lines)) if context_lines else ""

    material = ""
    if source_text and source_text.strip():
        material = f"\n\nBase the questions ONLY on this reference material:\n---\n{source_text.strip()[:SOURCE_TEXT_LIMIT]}\n---\n"

    avoid_block = ""
    existing = [str(a).strip() for a in (avoid or []) if str(a).strip()]
    if existing:
        avoid_block = "\n\nDo not repeat these questions (they already exist) - cover different facts or angles:\n" + "\n".join(f"- {a}" for a in existing) + "\n"

    if question_type == "true_false":
        kind = f"Generate exactly {num_questions} true/false questions about: {topic}"
        rules = (
            '- Each question is a single clear statement; "options" MUST be exactly ["True", "False"]\n'
            '- "type" MUST be "true_false"; correct_index is 0 when the statement is true, 1 when it is false\n'
            "- Mix true and false statements; avoid trick wording\n"
        )
        example_type, example_options, example_ci = '"true_false"', '["True", "False"]', "<0|1>"
    elif question_type == "mixed":
        kind = f"Generate exactly {num_questions} questions about: {topic} - a mix of multiple-choice and true/false"
        rules = (
            '- Multiple-choice questions: "type" "mcq", exactly 4 options, exactly ONE correct, plausible distractors\n'
            '- True/false questions: "type" "true_false", "options" exactly ["True", "False"], correct_index 0 for true / 1 for false\n'
            "- Roughly half of each kind\n"
        )
        example_type, example_options, example_ci = '"<mcq|true_false>"', '["<option A>", "<option B>", "<option C>", "<option D>"]', "<index of the correct option>"
    else:
        kind = f"Generate exactly {num_questions} multiple-choice questions about: {topic}"
        rules = (
            '- "type" MUST be "mcq"; each question MUST have exactly 4 options\n'
            "- Mark exactly ONE option as correct\n"
            "- Make distractors plausible but clearly wrong on close reading\n"
        )
        example_type, example_options, example_ci = '"mcq"', '["<option A>", "<option B>", "<option C>", "<option D>"]', "<0|1|2|3>"

    # The example array shows one item per requested question (first, second, ..., last) so the
    # model cannot mistake a one-item example for the expected length.
    if num_questions == 1:
        items = _example_item("question 1", example_type, example_options, example_ci)
    elif num_questions == 2:
        items = ",\n".join(_example_item(f"question {i}", example_type, example_options, example_ci) for i in (1, 2))
    else:
        items = (
            _example_item("question 1", example_type, example_options, example_ci) + ",\n"
            + _example_item("question 2", example_type, example_options, example_ci) + ",\n"
            + f"    ... one object per question, up to\n"
            + _example_item(f"question {num_questions}", example_type, example_options, example_ci)
        )

    return (
        f"{kind}\n"
        f"Difficulty: {difficulty}{context}{material}{avoid_block}\n\n"
        "Rules:\n"
        f'- The "questions" array MUST contain exactly {num_questions} items (question 1 to question {num_questions}); '
        "fewer is wrong, each about a different fact\n"
        f"{rules}"
        "- Include a brief explanation of the correct answer\n"
        "- Each question is worth 1 mark unless clearly harder\n\n"
        "Return ONLY this JSON structure:\n"
        "{\n"
        '  "questions": [\n'
        f"{items}\n"
        "  ]\n"
        "}"
    )


def _infer_type(q: Dict) -> str:
    explicit = str(q.get("type") or "").strip().lower()
    if explicit in ("mcq", "true_false"):
        return explicit
    options = q.get("options")
    if isinstance(options, list) and len(options) == 2 and {str(o).strip().lower() for o in options} == {"true", "false"}:
        return "true_false"
    return "mcq"


def _true_false_index(value) -> Optional[int]:
    if isinstance(value, bool):
        return 0 if value else 1
    if isinstance(value, int) and value in (0, 1):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("0", "true", "t"):
            return 0
        if v in ("1", "false", "f"):
            return 1
    return None


def clean_generated_questions(result: Dict, question_type: str = "mcq") -> List[Dict]:
    """Keep only well-formed questions of the requested kind; normalise their shape."""
    questions = result.get("questions", []) if isinstance(result, dict) else []
    if not isinstance(questions, list):
        return []
    valid: List[Dict] = []
    for q in questions:
        if not isinstance(q, dict) or not str(q.get("question_text") or "").strip():
            continue
        qtype = _infer_type(q)
        if question_type == "mcq" and qtype != "mcq":
            continue
        if question_type == "true_false" and qtype != "true_false":
            continue
        options = q.get("options")
        if not isinstance(options, list):
            continue
        if qtype == "true_false":
            if len(options) != 2 or {str(o).strip().lower() for o in options} != {"true", "false"}:
                continue
            ci = _true_false_index(q.get("correct_index"))
            if ci is None:
                continue
            clean_options = list(TRUE_FALSE_OPTIONS)
        else:
            if len(options) != 4:
                continue
            ci = q.get("correct_index")
            if isinstance(ci, bool) or not isinstance(ci, int) or ci < 0 or ci > 3:
                continue
            clean_options = [str(o).strip() for o in options]
            if any(not o for o in clean_options):
                continue
        try:
            marks = max(1, int(q.get("marks", 1)))
        except (TypeError, ValueError):
            marks = 1
        valid.append({
            "type": qtype,
            "question_text": str(q["question_text"]).strip(),
            "options": clean_options,
            "correct_index": ci,
            "marks": marks,
            "explanation": str(q.get("explanation") or "").strip() or None,
        })
    return valid


async def _ask_model(prompt: str) -> Dict:
    messages = [
        {"role": "system", "content": "You are an expert exam writer. You ONLY return valid JSON, never any other text or markdown."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await chat_completion(messages, temperature=0.4, max_tokens=4096, timeout=180.0)
        return extract_json_object(raw)
    except ValueError as e:
        raise GenerationError(f"The AI returned invalid JSON: {e}") from e
    except Exception as e:
        raise GenerationError(f"Question generation failed: {e}") from e


async def generate_quiz_questions(
    topic: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    source_text: Optional[str] = None,
    question_type: str = "mcq",
    grade_level: Optional[str] = None,
    subject: Optional[str] = None,
    objectives: Optional[str] = None,
) -> List[Dict]:
    """
    Ask the model and return up to num_questions cleaned, de-duplicated questions.
    Asks again for the missing ones when a round returns fewer than requested.
    Raises GenerationError only when the first round fails; a failed top-up round keeps
    what was already generated.
    """
    wanted = max(1, min(int(num_questions or 1), MAX_QUESTIONS))
    qtype = question_type if question_type in QUESTION_TYPES else "mcq"
    collected: List[Dict] = []
    seen = set()
    for _round in range(MAX_GENERATION_ROUNDS):
        missing = wanted - len(collected)
        if missing <= 0:
            break
        prompt = build_prompt(topic, missing, difficulty, qtype, source_text, grade_level, subject, objectives,
                              avoid=[q["question_text"] for q in collected] or None)
        try:
            result = await _ask_model(prompt)
        except GenerationError:
            if not collected:
                raise
            break
        for q in clean_generated_questions(result, qtype):
            key = normalize_answer(q["question_text"])
            if not key or key in seen:
                continue
            seen.add(key)
            collected.append(q)
            if len(collected) >= wanted:
                break
    return collected
