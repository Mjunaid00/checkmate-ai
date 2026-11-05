# CheckMate AI — Code Review, Fixes and One-Click Launcher (2026-11-04)

This document records a full review of the backend (FastAPI + Motor) and frontend
(React 19 + Vite 8), the bugs that were fixed, the problems that remain, and the
new one-click launcher. Originals of every modified file are in
`_backup_before_fixes_2026-11-04/` (same relative paths) so any change can be reverted.

## 1. Summary

* **Fixed 14 backend and 6 frontend defects**, several of which broke core features:
  teacher dashboard always showed zeros, any user could read every submission of any
  assignment, quizzes auto-submitted instantly on machines east of UTC, deadlines were
  shifted by the UTC offset, code execution never worked on Windows, and the whole API
  froze while OCR or grading ran.
* **Made the app runnable on this laptop**: the Chandra OCR dependency (torch) was broken
  in the conda env, so OCR now defaults to the vision model already loaded in LM Studio.
  The launcher now repairs the env (CUDA torch + missing requirements, see section 5), so
  Chandra remains available with `OCR_BACKEND=chandra`.
* **Added `Start-CheckMate.bat`** (plus `Stop-CheckMate.bat`): checks project files,
  Python env, Node, GPU, RAM, MongoDB (starts the service, elevating once if needed),
  LM Studio (starts the server, loads the model with a 16k context), then launches the
  backend and frontend, verifies `/health/full`, prints a PASS/WARN/FAIL table and opens
  the browser.
* **Verified**: 20 unit tests pass; the launcher passes all checks; an end-to-end run
  (register → class → assignment → enrol → submit → OCR header check → AI grading →
  dashboard → quiz generation) passed against the real stack.

## 2. Environment findings on this machine (read first)

| Finding | Impact | What to do |
| --- | --- | --- |
| **MongoDB Windows service is stopped** and last crashed on 2026-10-27 with `out of memory` (see `C:\Program Files\MongoDB\Server\8.2\log\mongod.log`). Starting it needs administrator rights. | Nothing works without it. | The launcher starts it and asks for UAC approval once. If it refuses to start, check the log above. |
| **torch in the `checkmate-ai` conda env was broken**: the env runs Python 3.11.15 but the installed torch wheel was `cp310` (`torch/_C.cp310-win_amd64.pyd`), so `import torch` failed with `WinError 126`; `transformers` was missing too. A plain `pip install -r requirements.txt` would have made it worse: `chandra-ocr[hf]` needs torch ≥ 2.8 and the torch on PyPI is CPU-only on Windows. | Chandra OCR could not run → every student upload failed with HTTP 500 (header check). | Default is now `OCR_BACKEND=lmstudio`. The launcher repairs the env automatically: it installs the CUDA build from `backend/requirements-torch-cuda.txt` (torch 2.14.1+cu126, torchvision 0.29.1+cu126) **before** `pip install -r requirements.txt`, which then adds `transformers`/`accelerate`. Chandra works again with `OCR_BACKEND=chandra`, but is not recommended on an 8 GB GPU that also hosts the LM Studio model. |
| **Memory is very tight**: 15.7 GB RAM with < 1 GB free during testing, 8 GB VRAM fully used by the 7B vision model. | OCR of one page took ~2 minutes and grading ~2 minutes under this pressure. Earlier it crashed MongoDB. | Close other apps before grading; the launcher now prints a RAM warning. A smaller model (e.g. a 3B vision model) would help. |
| `gcc`, `g++`, `javac`/`java` are not installed. | C, C++ and Java code grading report "Toolchain not available". Python and JavaScript work. | Install MinGW-w64 and a JDK if those languages matter. |
| The institution-header check (`routers/submissions.py`) requires the SZABIST name on page 1. None of the sample files in `uploads/submissions/` contain it. | Re-uploading the samples is rejected. | Set `REQUIRE_INSTITUTION_HEADER=false` in `backend/.env` for demos, or use files with the header. |
| `conda` is not on PATH and the env is Python 3.11 although the exported `environment.yml` says 3.10. | `conda activate` from a plain shell fails. | The launcher finds Anaconda itself (`%USERPROFILE%\anaconda3`, miniconda3, `%LOCALAPPDATA%`, `C:\ProgramData`; override `CHECKMATE_CONDA_ROOT`) and `run-backend.cmd` activates the env with `Scripts\activate.bat` before starting uvicorn, so the backend runs exactly as under `conda activate checkmate-ai`. |

## 3. Bugs fixed

### Backend

| # | File | Problem | Fix |
| --- | --- | --- | --- |
| B1 | `routers/dashboard.py` | `/dashboard/stats` matched `teacher_id` on the `submissions` collection, which has no such field → always `0 / 0 / 0.0`. | Resolve the teacher's assignments first, then aggregate their submissions (`summarize_submissions`). Also added an ownership check to `/dashboard/exams/{id}`. |
| B2 | `routers/submissions.py` | `GET /submissions/assignment/{id}` had no ownership check: any logged-in user, including students, could read every submission, score and feedback. | Teachers/admins must own the assignment; students only get their own rows. |
| B3 | `routers/auth.py` | `register` wrapped `HTTPException` in a generic handler, so "Email already registered" came back as HTTP 500. | Re-raise `HTTPException`. |
| B4 | `core/timeutil.py` (new), `routers/assignments.py`, `quizzes.py`, `omr.py` | Deadlines were parsed with `datetime.fromisoformat()` as naive values and compared with `utcnow()`. Combined with the browser sending local time, every deadline was off by the UTC offset (+9 h here). | `parse_deadline()` accepts `Z`/offsets and converts to naive UTC. |
| B5 | `services/grading.py`, `routers/submissions.py`, `services/plagiarism.py` | OCR and code execution are blocking calls made from `async def` routes/tasks, so the whole API stopped answering while a model ran. | Run them with `asyncio.to_thread`. Verified: the API served polling requests while grading. |
| B6 | `services/code_execution.py` | On Windows the temp file was deleted while still open → `PermissionError` → every Python/JS run reported an error. Files were written in the ANSI code page. | Close before run/unlink, UTF-8 everywhere, use `sys.executable`, clear "toolchain missing" message. |
| B7 | `core/llm.py` | LLM `score` was stored as whatever the model returned (string/float/out of range); JSON parsing failed on any prose around the object; errors were double-wrapped. | `extract_json_object()`, `coerce_score()` (int, clamped to `[0, max_marks]`), criteria coerced, single `chat_completion()` helper shared with `quiz_generator.py` and `omr_processor.py`. |
| B8 | `config.py` (new) | `.env` was loaded by whichever module imported first; `core/llm.py` read `LM_STUDIO_*` before that; the real `.env` had no LM Studio keys; `UPLOAD_DIR` was relative to the current working directory. | One `config.py` loads `backend/.env` by absolute path; paths resolve relative to `backend/`; new keys added to `.env` and `.env.example`. |
| B9 | `routers/submissions.py` | `MAX_UPLOAD_SIZE_MB` existed in `.env` but was never enforced; empty uploads were accepted. | 413 for oversize, 400 for empty. |
| B10 | `database.py` | No indexes: duplicate submissions/enrollments/attempts were possible under concurrent requests, and lookups scanned collections. | `ensure_indexes()` at startup (unique: `users.email`, `submissions(assignment_id, student_id)`, `enrollments(class_id, student_id)`, `quiz_attempts(quiz_id, student_id)`; plus sort indexes). Failures are logged, never fatal. |
| B11 | `services/ocr.py` | `from chandra.model import InferenceManager` at import time; first use loaded torch and failed. | Pluggable backends `lmstudio` / `chandra` / `none`, lazy imports, `ocr_status()` for health. |
| B12 | `core/llm.py` | A 4-page PDF plus rubric at 2× render is ~12k image tokens; LM Studio's default 4k context truncates the request. | Page images are downscaled to `LLM_IMAGE_MAX_SIDE` (1600 px) and the launcher loads the model with `LM_STUDIO_CONTEXT_LENGTH` (16384). |
| B13 | `main.py` | Only a trivial `/health`. | `/health/full` checks MongoDB ping, LM Studio reachability + loaded model, OCR backend, upload-dir writability. The launcher relies on it. |
| B14 | `main.py` | CORS origins hard-coded; `127.0.0.1:5173` was rejected. | `CORS_ORIGINS` in `.env`. |

### Frontend

| # | File | Problem | Fix |
| --- | --- | --- | --- |
| F1 | `services/api.js`, `utils/dateFormat.js`, `UploadWidget.jsx`, `QuizBuilderModal.jsx`, `OMRTemplateModal.jsx`, `QuizEditModal.jsx`, `EditClassModal.jsx` | The API returns naive UTC strings; `new Date()` parsed them as local time. On this +09:00 machine `QuizTaker` saw a start time 9 h in the past and **auto-submitted every quiz with all answers blank on load**; deadline badges, countdowns and "x minutes ago" were all shifted; `EditClassModal` moved an assignment's deadline 9 h earlier on every save. | Response interceptor appends `Z` to naive ISO timestamps; senders convert the `datetime-local` value with `toApiDatetime()` (UTC ISO); `EditClassModal` uses `toDatetimeLocalValue`. |
| F2 | `services/api.js` | The 401 interceptor redirected on a failed login, wiping the "Incorrect email or password" message. | No redirect for `/auth/login` and `/auth/register`. |
| F3 | `pages/StudentDashboard.jsx`, `pages/TeacherDashboard.jsx` | Nothing refreshed after upload; users had to reload to see "graded". | Poll every 5 s while any visible submission is `uploaded`/`processing`. |
| F4 | `pages/StudentDashboard.jsx` | On first load `handleClassSelect` read a stale empty `classes` closure and showed "No assignments" for the auto-selected class. | Pass the freshly fetched list. |
| F5 | `vite.config.js` | If port 5173 was busy Vite silently moved to 5174 and every API call failed CORS. | `strictPort: true`. |
| F6 | `components/DeadlinesWidget.jsx` | Bars bucketed by UTC day; unused variable failed `npm run lint`. | Local-day keys; variable removed. |

## 4. Still open (recommended, not changed)

Security
* `routers/admin.py` creates `admin@checkmate.ai / admin123` at first start when `ADMIN_EMAIL`/`ADMIN_PASSWORD` are unset, and prints it. Set those variables and change the password.
* `JWT_SECRET` is still the placeholder in `backend/.env` (the backend now warns at start). Generate a long random value.
* `services/code_execution.py` is not a sandbox: student code runs with the server's privileges and network access. Use Docker/`subprocess` job objects or disable the feature on shared machines.
* No rate limiting on `/auth/login`; tokens live in `localStorage`.
* `Login.txt` in the project root holds demo credentials; delete it before sharing the repo.

Correctness / behaviour
* Quiz time limit is not enforced server-side (`routers/quizzes.py::submit_quiz` only records `time_taken`).
* `services/grading.py`: code-grading results are stored but never influence the score, and only the last of up to three blocks is kept.
* `routers/auth.py::delete_account` and `admin.py::delete_user` leave enrollments, notifications, messages and quiz attempts behind for teachers; students keep notifications/messages.
* `routers/classes.py::_attach_counts` and `messages.py::class_threads` issue one query per class/student (N+1); fine for a class, slow for a school.
* `routers/upload.py` and `models/exam.py` are dead code (the router is not mounted and calls `process_exam_background` with the wrong signature). Delete them.
* `requirements.txt` has no version pins, lists `passlib[bcrypt]` (unused scheme) and omits `pypdfium2`; `Conda env file/*.yml` say Python 3.10 but the env is 3.11.
* `services/xai.py` uses `Dict[str, any]` (builtin `any`, not `typing.Any`) — harmless but wrong.
* README links to `docs/API.md`, `docs/USER_GUIDE.md`, `docs/PROJECT_REPORT.md`, which do not exist.

Frontend quality
* `useToast` exists but is used nowhere; errors in `TeacherDashboard`, `TeacherClasses`, `QuizList`, `OMRList`, `StudentDashboard`, `Settings`, `ClassReportModal`, `Analytics` are swallowed with `console.error`. Wire the toast provider into these handlers.
* `npm run lint` still reports 28 pre-existing errors (empty `catch {}` blocks in `QuizTaker.jsx`, unused `Icon`/`err` variables, suppressed `exhaustive-deps`).
* `EditClassModal.jsx` cannot clear `max_students`; `/archive` is a placeholder route linked from the sidebar; keyless fragments in `TeacherDashboard.jsx`, `StudentDashboard.jsx`, `OMRResultsModal.jsx`; `TeacherDashboard.jsx:142` divides by `total_marks` (NaN when 0).
* Duplicated code worth consolidating: `TeacherDashboard` vs `TeacherClasses` (class cards/handlers), the two explainable-feedback panels, `timeAgo` ×2, CSV download ×2, label components in the three modals.
* `frontend/dist/` is a stale build from April; it is git-ignored, delete it or rebuild.

## 5. One-click launcher

Files: `Start-CheckMate.bat`, `Stop-CheckMate.bat`, `scripts/start-checkmate.ps1`,
`scripts/stop-checkmate.ps1`, `scripts/run-backend.cmd`, `scripts/run-frontend.cmd`,
`scripts/tee_run.py` (console + `logs/*.log`), `scripts/check_env.py` (environment probe),
`backend/requirements-torch-cuda.txt` (CUDA PyTorch pins), `scripts/e2e_smoke.py`.

Behaviour worth knowing
* Reuses anything already running (MongoDB, LM Studio server, backend, frontend).
* Python environment: creates the `checkmate-ai` conda env if it is missing (Python 3.11),
  installs the CUDA PyTorch pins from `backend/requirements-torch-cuda.txt` when torch is
  missing, cannot import or has no CUDA, runs `pip install -r requirements.txt` when
  `scripts/check_env.py` finds a requirement (or a direct dependency of one, extras included)
  missing or at the wrong version, then checks that the backend's modules import and reports
  **PyTorch CUDA** with the device name. `-NoInstall` turns all installing off; pip output
  goes to `logs/pip-install.log`.
* The backend is started through `run-backend.cmd`, which activates the conda env
  (`Scripts\activate.bat`) first, so it runs with the env's PATH and DLLs like
  `conda activate checkmate-ai` would (`CHECKMATE_CONDA_ENV` / `CHECKMATE_CONDA_ROOT` /
  `CHECKMATE_PYTHON` override the choice).
* If the MongoDB service is stopped it runs `net start MongoDB` in an elevated cmd window
  (one UAC prompt), the same command that works by hand in an administrator cmd; if the
  launcher itself already runs as administrator it runs the command directly. `-NoElevate`
  disables the prompt and the summary then tells you to run the command yourself.
* If no MongoDB service exists it starts `mongod.exe` with a data directory under
  `%LOCALAPPDATA%\CheckMateAI\mongodb-data` (a separate, empty database).
* Loads `LM_STUDIO_MODEL` with `--context-length LM_STUDIO_CONTEXT_LENGTH` and warns when an
  already-loaded model has a context below 8k or is not a vision model.
* The backend runs **without** `--reload`; restart the backend window after code changes.
* Exit code 1 and a red summary when any check fails; the browser is not opened in that case.
* Review `scripts/start-checkmate.ps1` before using it on another machine: it looks for
  Anaconda/Miniconda in the usual install locations and the LM Studio CLI at
  `%USERPROFILE%\.lmstudio\bin\lms.exe` (override with `CHECKMATE_CONDA_ROOT`,
  `CHECKMATE_CONDA_ENV`, `CHECKMATE_PYTHON`, `CHECKMATE_LMS`). The CUDA pins in
  `backend/requirements-torch-cuda.txt` (cu126) need NVIDIA driver 560 or newer.

## 6. Verification record

* `backend/tests/test_fixes.py`: 20 tests (JSON extraction, score coercion, Windows code
  execution, OCR backend selection, dashboard aggregation, deadline parsing) — all pass.
* Launcher: all checks PASS on this laptop (GPU/RAM show WARN when memory is low).
* `scripts/e2e_smoke.py` against the running stack: all steps passed; the sample answer was
  graded 8/10 with three criteria, keyword analysis and recommendations; dashboard stats
  reported 1 submission / 1 graded / 80 %; deadline remaining was computed correctly; quiz
  generation returned questions.
* Note: the first end-to-end run and launcher test used a temporary MongoDB started for the
  session because the Windows service cannot be started without administrator rights. The UAC
  elevation path in the launcher (`net start MongoDB` in an elevated cmd) is therefore untested
  here; the command itself is the one that works by hand in an administrator cmd.

### Launcher round 3 (env repair, auto-install, conda activation) - 2026-11-04

* `Start-CheckMate.bat -ChecksOnly` on the laptop (MongoDB service already running):
  detected the broken torch, installed `torch 2.14.1+cu126` + `torchvision 0.29.1+cu126`
  (2.6 GB, about 5 min), removed the incompatible `torchaudio 2.5.1+cu121`, found
  `transformers`/`accelerate` missing for `chandra-ocr[hf]`, ran `pip install -r
  requirements.txt`, then reported **Python env PASS** and **PyTorch CUDA PASS** (RTX 4070
  Laptop GPU, CUDA 12.6). All checks passed in 501 s; a second run needs no installs.
* Full launch (`-NoBrowser`, backend pointed at a throwaway database through
  `DATABASE_NAME`): all checks passed in 42 s, `/health/full` OK with MongoDB, the loaded
  vision model, OCR=lmstudio and a writable uploads dir. The backend was started by
  `run-backend.cmd` through `Scripts\activate.bat` (conda env activation verified
  separately: `CONDA_PREFIX` and `python` both resolve to the env).
* `scripts/e2e_smoke.py` against that stack: all steps passed (register/duplicate/wrong
  password, class, assignment with UTC deadline, enrolment, header-checked submission,
  grading finished at 3/10 with two criteria and XAI output, dashboard 1/1/30 %, deadline
  maths, quiz generation). The throwaway database and the uploaded test files were removed
  afterwards; the real `checkmate_ai` database was not touched.
* Note: the score differs from the earlier 8/10 for the same answer image; grading by a
  local 7B model is not deterministic, which is worth telling teachers.

## 7. Admin privileges (2026-11-04, follow-up)

* `routers/deps.py`: `get_current_teacher` now accepts role `admin` as well (`TEACHER_ROLES`),
  so every teacher endpoint (classes, assignments, submissions review, dashboard, analytics,
  reports, quizzes, OMR, messages, uploads) is open to admins, who act as the teacher of the
  content they create. Ownership checks are unchanged: an admin sees and edits its own
  classes/assignments, not other teachers' (that would be the next step if wanted).
  Student-only endpoints (submit, enrol, take quiz) remain student-only.
* `routers/classes.py` and `routers/auth.py`: the two explicit `role == "teacher"` branches
  (class listing, account deletion clean-up) include admins.
* Frontend: `/`, `/classes`, `/analytics` and the sidebar treat admins like teachers; admins
  land on the teacher dashboard and keep the Admin Panel link. `QuizResults` and the welcome
  header handle the admin role.
* `scripts/create_admin.py`: creates or promotes an admin directly in MongoDB with the
  backend's own password hashing (password via prompt or `CHECKMATE_ADMIN_PASSWORD`).
* Tests: `backend/tests/test_roles.py` (6 cases) covers the dependency behaviour.
* Still open: the bootstrap default admin `admin@checkmate.ai` / `admin123` remains in the
  database until deleted from the Admin Panel; the API's 6-character password minimum is not
  enforced for accounts created with the script (it warns instead).
