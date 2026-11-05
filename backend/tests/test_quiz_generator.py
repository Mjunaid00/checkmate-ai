"""
Quiz generator: prompt building and cleaning of the model's JSON for MCQ / true-false / mixed.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_clean_keeps_valid_mcq_and_drops_broken_ones():
    from services.quiz_generator import clean_generated_questions
    result = {"questions": [
        {"question_text": "Q1", "options": ["a", "b", "c", "d"], "correct_index": 1, "marks": "2", "explanation": "b"},
        {"question_text": "", "options": ["a", "b", "c", "d"], "correct_index": 1},
        {"question_text": "Q3", "options": ["a", "b"], "correct_index": 0},
        {"question_text": "Q4", "options": ["a", "b", "c", "d"], "correct_index": 9},
    ]}
    out = clean_generated_questions(result, "mcq")
    assert [q["question_text"] for q in out] == ["Q1"]
    assert out[0]["type"] == "mcq" and out[0]["marks"] == 2


def test_clean_true_false_normalises_options_and_type():
    from services.quiz_generator import clean_generated_questions
    result = {"questions": [
        {"type": "true_false", "question_text": "Water boils at 100 C at sea level.", "options": ["true", "false"], "correct_index": 0},
        {"type": "true_false", "question_text": "Bad", "options": ["True", "False", "Maybe"], "correct_index": 0},
        {"type": "true_false", "question_text": "Answer given as text", "options": ["True", "False"], "correct_index": "False"},
    ]}
    out = clean_generated_questions(result, "true_false")
    assert [q["question_text"] for q in out] == ["Water boils at 100 C at sea level.", "Answer given as text"]
    assert out[0]["options"] == ["True", "False"] and out[0]["correct_index"] == 0
    assert out[1]["correct_index"] == 1
    assert all(q["type"] == "true_false" for q in out)


def test_clean_mixed_accepts_both_types_and_infers_true_false_from_options():
    from services.quiz_generator import clean_generated_questions
    result = {"questions": [
        {"question_text": "M", "options": ["a", "b", "c", "d"], "correct_index": 2},
        {"question_text": "T", "options": ["True", "False"], "correct_index": 1},
    ]}
    out = clean_generated_questions(result, "mixed")
    assert [q["type"] for q in out] == ["mcq", "true_false"]


def test_clean_requested_type_mcq_drops_true_false_questions():
    from services.quiz_generator import clean_generated_questions
    result = {"questions": [{"question_text": "T", "options": ["True", "False"], "correct_index": 1}]}
    assert clean_generated_questions(result, "mcq") == []


def test_prompt_mentions_context_fields_and_type():
    from services.quiz_generator import build_prompt
    p = build_prompt(topic="Photosynthesis", num_questions=3, difficulty="easy", question_type="true_false",
                     grade_level="Grade 9", subject="Biology", objectives="Explain light reactions")
    assert "Grade 9" in p and "Biology" in p and "Explain light reactions" in p
    assert "true/false" in p.lower()
    assert '"True", "False"' in p


def test_prompt_mixed_asks_for_both_kinds():
    from services.quiz_generator import build_prompt
    p = build_prompt(topic="X", num_questions=4, difficulty="medium", question_type="mixed")
    assert "multiple-choice" in p.lower() and "true/false" in p.lower()


def test_prompt_includes_source_material_truncated():
    from services.quiz_generator import build_prompt, SOURCE_TEXT_LIMIT
    p = build_prompt(topic="X", num_questions=2, difficulty="medium", question_type="mcq", source_text="~" * (SOURCE_TEXT_LIMIT + 50))
    assert p.count("~") == SOURCE_TEXT_LIMIT
