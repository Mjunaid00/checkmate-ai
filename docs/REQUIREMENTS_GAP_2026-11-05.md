# CheckMate AI - requirements gap analysis (2026-11-05)

Status of the code against the "Core Feature Requirements" list. Line numbers refer to the
code on this date.

| # | Requirement | Status | What exists / what is missing |
|---|-------------|--------|-------------------------------|
| 1a | Manual authoring (MCQ, true/false, short answer, essay) | PARTIAL | `POST /quizzes/` and the manual step of `QuizBuilderModal.jsx` accept hand-written questions, but `_validate_questions` (`routers/quizzes.py:108-112`) allows only 4-option single-answer MCQs; no question `type`. Assignments are one uploaded file, not structured questions. |
| 1b | LLM question generation from objectives / grade level / subject | PARTIAL | `POST /quizzes/generate` takes topic, count, difficulty (`quizzes.py:84-88`, prompt in `services/quiz_generator.py`). No grade level, subject or learning-objective inputs; MCQ only; generator errors surface as HTTP 500. |
| 1c | Reference documents (PDF, TXT, DOCX) as source material | PARTIAL | `POST /quizzes/generate-from-pdf` extracts text with PyMuPDF (`quizzes.py:23-49`, 6000-char cap). PDF only, no TXT/DOCX, no OCR for scanned PDFs, source file not stored with the quiz. |
| 1d | Question bank (save, edit, organise, reuse) | MISSING | Questions live only inside each `quizzes` document. No bank collection, router or UI. |
| 2a | VLM-driven OMR for photos / scanned PDFs | IMPLEMENTED | Templates (`routers/omr.py:102-151`), student and batch uploads (207-368), background processing with the vision model (`services/omr_processor.py:157-225`), results UI (`OMRResultsModal.jsx`). |
| 2b | Robust recognition (rotation, shadows, crumpled paper, handwriting) | MISSING | Only a prompt rule ("-1 when blank, unclear or multiply marked"). No deskew / contrast preprocessing, no retries, no per-question confidence, multi-page PDFs cut to page 1 (`omr_processor.py:32`). |
| 2c | Extraction, grading, anomaly flags, gradebook ingestion | PARTIAL | `grade_omr_answers` scores against the key with negative marking and writes `omr_submissions`. Multiple-bubble marks are not flagged separately (folded into blank), batch sheets are not linked to students (`omr.py:329`), OMR results are absent from class reports / CSV, no manual correction of a detected answer. |
| 3a | Strict single submission, locked after submit / deadline | PARTIAL | Assignments: duplicate (409) and deadline checks plus a unique index. Quizzes: `/start` checks deadline and existing attempt, `/submit` checks duplicates. Missing: deadline check on `/quizzes/{id}/submit` (`quizzes.py:498-571`), server-side time limit (`started_at` comes from the client), explicit lock/status flag, unique index on `omr_submissions`. |
| 3b | Teacher override for a retry with audit logging | MISSING | No reset/retry endpoint; teachers can only delete whole quizzes or OMR submissions, unlogged. No audit collection (`activity_log` is written only on `submission_graded`). |
| 4 | Reference uploads (TXT/PDF) for questions and rubrics | PARTIAL | Assignments take one rubric file (PDF/JPEG/PNG) plus a free-text grading prompt; grading sends rubric pages as images to the VLM (`core/llm.py:201-308`). No TXT/DOCX, no structured rubric/answer-key fields, no LLM rubric generation, rubric file cannot be replaced after creation. |
| 5a | Analytics: weak concepts, averages, distributions | PARTIAL | Teacher overview, per-class and per-student analytics, per-quiz per-question correct rate, 14-day timeline. Missing: score distribution / histogram, aggregated weak concepts, quizzes and OMR in class reports. Ownership checks missing on `/analytics/class/{id}`, `/student/{id}`, `/predict/{id}`, `/alerts/{id}`. |
| 5b | Export CSV / Excel | PARTIAL | CSV for class grade matrix and per-student report (`routers/reports.py`). No Excel, no quiz or OMR export, no analytics export. |
| 6a | Teacher vs student (vs admin) roles on endpoints | IMPLEMENTED | JWT + `get_current_teacher` / `get_current_student` / `get_current_admin` (`routers/deps.py`), ownership checks on quizzes, OMR, reports, assignments. Gap: `get_current_user` ignores `is_active` (a deactivated user's token keeps working until it expires). |
| 6b | Students cannot see answer keys or change status flags | PARTIAL | Quiz answers stripped for students, OMR answer key hidden, scores computed server-side, status set server-side. Leaks: `grading_prompt` is returned to students by `GET /assignments/class/{id}` (`models/school.py:56`); rubric keywords (`rubric_keywords`, `missing_keywords`) reach students in `explainable_feedback`. Quiz PATCH can change answers after attempts exist (only the UI prevents it). |

## Bugs found during the review

1. **Route shadowing**: `GET /analytics/student/deadlines` (`routers/analytics.py:79`) is declared after `GET /analytics/student/{student_id}` (line 28), so a student requesting deadlines hits the teacher-only route and gets 403.
2. **Unmounted router**: `routers/upload.py` is not included in `main.py`, and its call `process_exam_background(exam_id, path, total_marks)` (line 95) does not match the 5-argument function in `services/grading.py:25`. Dead code; remove or fix.
3. **Undeclared dependency**: `pypdfium2` is imported by `services/omr_processor.py` and `core/llm.py` but is not listed in `requirements.txt` (it is installed only as a transitive dependency).

## Suggested order of work

1. Security and correctness fixes (small): hide `grading_prompt` and rubric keywords from students, ownership checks on analytics routes, `is_active` check in `get_current_user`, deadline check on quiz submit, route order fix, remove or mount `upload.py`, declare `pypdfium2`.
2. Single-submission hardening and teacher override with audit log (3a, 3b): attempt record on `/start`, server-side time limit, `locked` status, `POST /quizzes/{id}/attempts/{student}/reset` and the same for submissions, written to an `audit_log` collection with who / what / why / when, visible to admins.
3. Question types and question bank (1a, 1d): `type` field (mcq, true_false, short_answer, essay) with per-type validation and auto-grading for the first two, `question_bank` collection with tags, pick-from-bank in the quiz builder.
4. Document ingestion for generation (1b, 1c, 4): TXT and DOCX (python-docx), OCR fallback for scanned PDFs, grade level / subject / objectives in the prompt, store the source document reference on the quiz.
5. OMR improvements (2b, 2c): image preprocessing (auto-rotate, deskew, contrast), all PDF pages, per-question confidence and a `multiple_marks` anomaly flag with a review queue, link batch sheets to students, teacher correction of detected answers, OMR in reports.
6. Analytics and export (5a, 5b): score histograms, weak-concept aggregation across submissions and quizzes, quizzes and OMR in class reports, Excel export (openpyxl).

## Update after the 2026-11-05 fixes

| # | Requirement | Now | Change |
|---|-------------|-----|--------|
| 1a | Manual authoring | PARTIAL | True/false questions added (`type` field, `services/quiz_logic.py`); MCQs may have 2-6 options. Short-answer and essay questions still missing. |
| 1b | LLM generation context | IMPLEMENTED | `question_type` (mcq / true_false / mixed), `grade_level`, `subject`, `objectives` feed the prompt; model failures return HTTP 502 instead of 500. |
| 1c | Reference documents | PARTIAL | PDF, TXT, MD and DOCX accepted (`services/document_text.py`, `POST /quizzes/generate-from-document`). Still no OCR for scanned PDFs; the source file is not stored. |
| 1d | Question bank | MISSING | unchanged |
| 2b/2c | OMR robustness / anomalies | unchanged | not in this round |
| 3a | Single submission (quizzes) | IMPLEMENTED | Server-side start time in `quiz_sessions`, time limit and deadline enforced on `/submit` (2-minute grace), expired attempts refused, stable shuffle per attempt, questions locked after the first attempt. Assignments unchanged (already locked). OMR still has no unique index. |
| 3b | Teacher override + audit log | MISSING | unchanged |
| 5a | Analytics | PARTIAL | Score distribution bands, weakest quiz questions and per-class quiz averages added to `/analytics/teacher/overview` and the Analytics page; ownership checks on class / student / predict / alerts routes. Class reports and CSVs still cover assignments only. |
| 5b | Export | PARTIAL | unchanged (CSV only) |
| 6a | Roles | IMPLEMENTED | Deactivated accounts are refused on every request (`is_active`). |
| 6b | Answer-key protection | IMPLEMENTED | Grading prompt removed from student responses; rubric keyword lists hidden until the deadline; quiz `PATCH` refuses question changes once attempted. |

Bugs 1-3 above are fixed (route order, dead `routers/upload.py` removed, `pypdfium2` and
`python-docx` declared). `backend/.env` now carries a random `JWT_SECRET` (the placeholder
would let anyone forge tokens on the public tunnel); existing sessions had to log in again.
Verified by 67 unit tests and `scripts/e2e_quiz.py` (40 checks, including generation from a
TXT and a DOCX file with the local model).

## Update after the second round (same day)

| # | Requirement | Now | Change |
|---|-------------|-----|--------|
| 1a | Manual authoring | PARTIAL | Short-answer questions added (accepted answers, normalised matching). Essay questions (manual grading) still missing. |
| 1d | Question bank | PARTIAL | Questions of another quiz in the same class can be imported in the builder. No separate bank with tags yet. |
| 2b | OMR robustness | PARTIAL | EXIF auto-rotation, greyscale, contrast stretch and a size cap before the model reads the sheet (`prepare_sheet_image`); multi-page PDFs produce a warning. No deskew or per-question confidence. |
| 2c | OMR anomalies | PARTIAL | Multiple-mark questions are detected (`-2`), listed in `multiple_marked`, and the sheet gets `needs_review`; shown in the results modal. Batch sheets are still not linked to students; no manual correction. |
| 3b | Teacher override + audit log | IMPLEMENTED | `POST /quizzes/{id}/attempts/{student}/reset` and `POST /submissions/{id}/allow-resubmission` need a reason, notify the student and write to `audit_log`; `GET /audit/` (admin: all, teacher: own) feeds the Admin Panel. |
| 5b | Export | IMPLEMENTED | Excel export for class and student reports; quiz attempts included in CSV and Excel. |

Verified by 94 unit tests and `scripts/e2e_quiz.py` (57 live checks).

## Update 2026-11-09 (two bugs reported after use)

| Report | Root cause (verified) | Fix |
|---|---|---|
| "Number of MCQs is always 1 even when 5 is selected" | LM Studio's server log shows the model answered the real requests for 5 questions about "LLM" with a single question (it mirrored the one-item JSON example in the prompt). The code passed the number correctly end to end. | Prompt says *exactly N* and shows N example items; `generate_quiz_questions` tops up the missing questions (max 3 rounds, no repeats); UI note when the model still falls short; e2e asserts the exact count. |
| "Assignment submission button not working" | Reproduced in Chrome: the student dashboard wrapper keeps a `transform` after its fade-in animation, so the `position: fixed` upload dialog was centred in the 2186 px page, 356 px above the viewport; the confirmation dialog likewise. No request ever reached the backend. | Fade-in animates opacity only and no longer keeps its end state; the modal's own scale-in drops `forwards`. Verified in Chrome: both dialogs fully inside the viewport, and the final submit reaches `POST /submissions/`. |
| (found in the backend log) `POST /quizzes/{id}/start` 500 `DuplicateKeyError` | Two simultaneous starts both inserted a session. | `services/quiz_sessions.get_or_create_session` returns the winner's start time on a duplicate-key error. |
