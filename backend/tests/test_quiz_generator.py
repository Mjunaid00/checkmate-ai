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


# ── requested count: prompt wording and top-up rounds ────────────────────────
import asyncio
import json


def _reply(texts, kind="mcq"):
    qs = []
    for t in texts:
        if kind == "true_false":
            qs.append({"type": "true_false", "question_text": t, "options": ["True", "False"], "correct_index": 0})
        else:
            qs.append({"type": "mcq", "question_text": t, "options": ["a", "b", "c", "d"], "correct_index": 1})
    return json.dumps({"questions": qs})


def test_prompt_states_the_exact_count_and_shows_numbered_placeholders():
    from services.quiz_generator import build_prompt
    p = build_prompt(topic="LLM", num_questions=5, difficulty="medium", question_type="mcq")
    assert "exactly 5" in p
    assert "question 1" in p.lower() and "question 5" in p.lower()
    # the single-item example was what the model copied: the example must show more than one item
    assert p.count('"question_text"') >= 2


def test_prompt_lists_questions_that_must_not_be_repeated():
    from services.quiz_generator import build_prompt
    p = build_prompt(topic="LLM", num_questions=4, difficulty="medium", question_type="mcq",
                     avoid=["What does LLM stand for?", "Who trains LLMs?"])
    assert "Do not repeat" in p
    assert "What does LLM stand for?" in p and "Who trains LLMs?" in p
    assert "exactly 4" in p


def test_generate_asks_again_until_the_requested_count_is_reached(monkeypatch):
    import services.quiz_generator as g
    replies = [_reply(["Q1"]), _reply(["Q2", "Q3", "Q4", "Q5"])]
    prompts = []

    async def fake_chat(messages, **kwargs):
        prompts.append(messages[-1]["content"])
        return replies.pop(0)

    monkeypatch.setattr(g, "chat_completion", fake_chat)
    out = asyncio.run(g.generate_quiz_questions("LLM", 5, "medium"))
    assert [q["question_text"] for q in out] == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert len(prompts) == 2
    assert "exactly 4" in prompts[1] and "Q1" in prompts[1]


def test_generate_drops_repeats_and_stops_after_the_last_round(monkeypatch):
    import services.quiz_generator as g
    calls = []

    async def fake_chat(messages, **kwargs):
        calls.append(1)
        return _reply(["What does LLM stand for?", "what does llm stand for"])

    monkeypatch.setattr(g, "chat_completion", fake_chat)
    out = asyncio.run(g.generate_quiz_questions("LLM", 5, "medium"))
    assert [q["question_text"] for q in out] == ["What does LLM stand for?"]
    assert len(calls) == g.MAX_GENERATION_ROUNDS


def test_generate_trims_extra_questions_to_the_requested_count(monkeypatch):
    import services.quiz_generator as g

    async def fake_chat(messages, **kwargs):
        return _reply([f"Q{i}" for i in range(7)])

    monkeypatch.setattr(g, "chat_completion", fake_chat)
    out = asyncio.run(g.generate_quiz_questions("LLM", 5, "medium"))
    assert len(out) == 5


def test_generate_keeps_the_first_round_when_a_top_up_round_fails(monkeypatch):
    import services.quiz_generator as g
    replies = [_reply(["Q1", "Q2"]), "this is not json at all"]

    async def fake_chat(messages, **kwargs):
        return replies.pop(0)

    monkeypatch.setattr(g, "chat_completion", fake_chat)
    out = asyncio.run(g.generate_quiz_questions("LLM", 5, "medium"))
    assert [q["question_text"] for q in out] == ["Q1", "Q2"]


def test_generate_raises_when_the_first_round_fails(monkeypatch):
    import services.quiz_generator as g
    import pytest

    async def fake_chat(messages, **kwargs):
        return "no json here"

    monkeypatch.setattr(g, "chat_completion", fake_chat)
    with pytest.raises(g.GenerationError):
        asyncio.run(g.generate_quiz_questions("LLM", 5, "medium"))
