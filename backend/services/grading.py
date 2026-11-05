"""
Unified Grading Pipeline
Integrates: OCR (M4), Language Detection (M5), Code Extraction (M6),
Parsing (M7), Code Execution (M8), Code Grading (M9), LLM Grading,
XAI Feedback (M11), and Monitoring (M12).
"""
import asyncio
from bson import ObjectId
from pathlib import Path
from typing import Optional
from config import absolute_upload_path
from database import get_db
from core.llm import grade_exam

# Module imports
from services.ocr import extract_text
from services.language_detection import classify_content
from services.code_extraction import separate_code_and_text
from services.parsing import prepare_grading_input
from services.code_grading import grade_code_submission, analyze_code_quality
from services.xai import generate_xai_feedback
from services.monitoring import log_activity


async def process_exam_background(
    submission_id: str,
    rubric_file_relative: str,
    answer_file_relative: str,
    max_marks: int,
    grading_prompt: Optional[str] = None,
):
    """
    Full grading pipeline for a student submission.
    Pipeline: OCR -> Language Detection -> Code Extraction -> Parsing ->
              LLM Grading (images) + Code Grading (if code found) ->
              XAI Feedback -> Save Results
    """
    db = get_db()
    if db is None:
        print("[ERROR] Database not reachable for background processing.")
        return

    obj_id = ObjectId(submission_id)
    print(f"[Grading Pipeline] Started processing submission {submission_id}")

    await db["submissions"].update_one(
        {"_id": obj_id},
        {"$set": {"status": "processing"}}
    )

    try:
        rubric_path = absolute_upload_path(rubric_file_relative)
        answer_path = absolute_upload_path(answer_file_relative)

        # ── Step 1: OCR — Extract text from documents ───────────────
        print(f"[Pipeline] Step 1: OCR text extraction")
        rubric_text = ""
        answer_text = ""
        try:
            # OCR blocks on model inference -> run in a worker thread so the API stays responsive
            rubric_text = await asyncio.to_thread(extract_text, rubric_path)
            answer_text = await asyncio.to_thread(extract_text, answer_path)
            print(f"[Pipeline] OCR extracted: rubric={len(rubric_text)} chars, answer={len(answer_text)} chars")
        except Exception as ocr_err:
            print(f"[Pipeline] OCR failed (will use LLM vision only): {ocr_err}")

        # ── Step 2: Language Detection ──────────────────────────────
        print(f"[Pipeline] Step 2: Language & content detection")
        content_analysis = classify_content(answer_text) if answer_text else {
            "content_type": "descriptive",
            "natural_language": "en",
            "programming_language": None,
            "code_ratio": 0,
        }
        print(f"[Pipeline] Content type: {content_analysis['content_type']}, "
              f"Language: {content_analysis.get('programming_language', 'N/A')}")

        # ── Step 3: Code Extraction ─────────────────────────────────
        code_data = None
        if answer_text and content_analysis["content_type"] in ("code", "mixed"):
            print(f"[Pipeline] Step 3: Extracting code blocks")
            code_data = separate_code_and_text(answer_text)
            print(f"[Pipeline] Found {code_data['code_count']} code block(s)")

        # ── Step 4: Parsing — Split answers ─────────────────────────
        parsed_data = None
        if rubric_text and answer_text:
            print(f"[Pipeline] Step 4: Parsing & matching answers")
            parsed_data = prepare_grading_input(rubric_text, answer_text)
            print(f"[Pipeline] Found {parsed_data['total_questions_found']} answers")

        # ── Step 5: LLM Vision Grading (always runs — primary grader) ─
        print(f"[Pipeline] Step 5: LLM vision grading")
        llm_result = await grade_exam(rubric_path, answer_path, max_marks, grading_prompt)
        score = llm_result.get("score", 0)
        feedback = llm_result.get("feedback", "")
        llm_explainable = llm_result.get("explainable_feedback", None)

        # ── Step 6: Code Grading (if code found) ───────────────────
        code_grading_result = None
        if code_data and code_data["has_code"]:
            print(f"[Pipeline] Step 6: Code execution & grading")
            lang = content_analysis.get("programming_language", "python") or "python"
            for block in code_data["code_blocks"][:3]:  # Grade up to 3 code blocks
                try:
                    code_result = await asyncio.to_thread(
                        grade_code_submission,
                        code=block["code"],
                        language=lang,
                        max_marks=max_marks,
                    )
                    quality = analyze_code_quality(block["code"], lang)
                    code_grading_result = {
                        "execution": code_result,
                        "quality": quality,
                        "language": lang,
                    }
                    print(f"[Pipeline] Code grading: {code_result['summary']}")
                except Exception as code_err:
                    print(f"[Pipeline] Code grading failed: {code_err}")

        # ── Step 7: XAI Feedback Generation ─────────────────────────
        print(f"[Pipeline] Step 7: Generating XAI feedback")
        xai_feedback = generate_xai_feedback(
            rubric_text=rubric_text if rubric_text else None,
            student_text=answer_text if answer_text else "",
            score=score,
            max_marks=max_marks,
            llm_feedback=llm_explainable,
        )

        # ── Build final explainable feedback ────────────────────────
        explainable_feedback = llm_explainable or {}

        # Merge XAI data into explainable feedback
        explainable_feedback["xai"] = {
            "keyword_analysis": xai_feedback.get("keyword_analysis"),
            "mistakes_detected": xai_feedback.get("mistakes_detected"),
            "recommendations": xai_feedback.get("recommendations"),
            "performance_level": xai_feedback.get("performance_level"),
        }

        # Add content analysis metadata
        explainable_feedback["content_analysis"] = {
            "content_type": content_analysis["content_type"],
            "natural_language": content_analysis.get("natural_language"),
            "programming_language": content_analysis.get("programming_language"),
            "ocr_extracted": len(answer_text) > 0,
        }

        # Add code grading if available
        if code_grading_result:
            explainable_feedback["code_grading"] = code_grading_result

        # Add parsed question matching if available
        if parsed_data:
            explainable_feedback["parsed_answers"] = {
                "total_questions_found": parsed_data["total_questions_found"],
                "matched_pairs_count": sum(
                    1 for p in parsed_data["matched_pairs"] if p["matched"]
                ),
            }

        print(f"[Grading Pipeline] Complete. Score: {score}/{max_marks}")

        # ── Save results to MongoDB ─────────────────────────────────
        await db["submissions"].update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "graded",
                "score": score,
                "feedback": feedback,
                "explainable_feedback": explainable_feedback,
            }}
        )

        # ── Step 8: Log activity for monitoring ─────────────────────
        submission = await db["submissions"].find_one({"_id": obj_id})
        if submission:
            await log_activity(db, submission["student_id"], "submission_graded", {
                "submission_id": submission_id,
                "score": score,
                "max_marks": max_marks,
                "content_type": content_analysis["content_type"],
            })

            # Notify student that grading is complete
            from services.notifications import notify_user
            from bson import ObjectId as _OID
            assignment = await db["assignments"].find_one({"_id": _OID(submission["assignment_id"])}) if _OID.is_valid(submission["assignment_id"]) else None
            assignment_title = assignment.get("title", "your assignment") if assignment else "your assignment"
            await notify_user(
                db,
                user_id=submission["student_id"],
                title="Your submission is graded",
                body=f"'{assignment_title}' — scored {score}/{max_marks}",
                link="/",
                category="grading",
            )

            # If teacher enabled plagiarism check, run it after each grading completes
            if assignment and assignment.get("plagiarism_check"):
                try:
                    # Cache the OCR'd text on this submission for future plagiarism runs
                    if answer_text:
                        await db["submissions"].update_one(
                            {"_id": obj_id},
                            {"$set": {"extracted_text": answer_text}},
                        )
                    from services.plagiarism import check_assignment_plagiarism
                    pl_result = await check_assignment_plagiarism(db, submission["assignment_id"])
                    print(f"[Plagiarism] {pl_result.get('flagged_pairs', 0)} flagged pair(s) on assignment {submission['assignment_id']}")
                except Exception as pl_err:
                    print(f"[Plagiarism] Auto-check failed: {pl_err}")

    except Exception as e:
        print(f"[Grading Pipeline] Error processing submission {submission_id}: {e}")
        import traceback
        traceback.print_exc()
        await db["submissions"].update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "failed",
                "feedback": f"System Error: {str(e)}"
            }}
        )
