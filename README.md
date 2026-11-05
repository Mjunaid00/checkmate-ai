# CheckMate AI

AI-powered exam grading platform with Explainable AI (XAI) feedback, built for teachers and students.

![1.00](docs/screenshots/dashboard-dark.png)

## Features

* **Role-based Access** - Separate Teacher and Student portals
* **AI Grading** - Automatic grading using LM Studio vision models (Qwen2.5-VL)
* **Explainable AI** - Detailed feedback with keyword analysis, criterion breakdown, strengths/improvements
* **OCR** - Chandra OCR 2 for handwriting and document recognition (90+ languages)
* **Code Grading** - Sandboxed execution for Python, C, C++, Java, JavaScript
* **Performance Prediction** - Trend analysis and risk-level predictions for students
* **Theme Support** - Light, Dark, Gray, and Night Light modes
* **Class Management** - Create classes, set deadlines, upload rubrics with grading prompts

## Tech Stack

| Layer    | Technology                                    |
| -------- | --------------------------------------------- |
| Frontend | React 19, Vite 8, Recharts, Lucide Icons      |
| Backend  | FastAPI, Motor (async MongoDB)                |
| Database | MongoDB                                       |
| AI/LLM   | LM Studio (Qwen2.5-VL), OpenAI-compatible API |
| OCR      | Chandra OCR 2 (HuggingFace)                   |
| Auth     | JWT (python-jose), PBKDF2 password hashing    |

## Quick Start

### One click (Windows)

Double-click **`Start-CheckMate.bat`** in the project root. It checks and starts
everything, prints a PASS / WARN / FAIL table, and opens the app:

1. project files, `backend/.env` (created from `.env.example` if missing)
2. the `checkmate-ai` Anaconda environment: created if missing; the CUDA build of PyTorch is
   installed from `backend/requirements-torch-cuda.txt` when torch is missing, broken or
   CPU-only; `pip install -r requirements.txt` runs when anything from it is missing; then an
   import check and a `torch.cuda.is_available()` check (shown as **PyTorch CUDA**)
3. Node.js (`npm install` when `node_modules` is missing)
4. GPU (nvidia-smi) and free system RAM
5. MongoDB — if the Windows service is stopped it runs `net start MongoDB` in an
   administrator window (one UAC prompt), the same as doing it by hand in an admin cmd
6. LM Studio — starts the local server and loads `LM_STUDIO_MODEL` with a 16k context
7. backend on <http://localhost:8000>, started inside the conda env (`run-backend.cmd`
   activates it first), and its `/health/full` readiness probe
8. frontend on <http://localhost:5173>

Options: `Start-CheckMate.bat -ChecksOnly`, `-NoBrowser`, `-SkipModelLoad`, `-NoElevate`,
`-NoInstall` (report only, never install anything).
Environment overrides: `CHECKMATE_CONDA_ENV` (default `checkmate-ai`), `CHECKMATE_CONDA_ROOT`,
`CHECKMATE_PYTHON`, `CHECKMATE_LMS`. pip output is kept in `logs/pip-install.log`.
**`Stop-CheckMate.bat`** stops the backend and frontend and unloads the model.
Each server runs in its own window and also logs to `logs/backend.log` / `logs/frontend.log`.

Important `backend/.env` keys:

| Key | Default | Meaning |
| --- | --- | --- |
| `LM_STUDIO_MODEL` | `qwen/qwen2.5-vl-7b` | model key from `lms ls`; must be a vision model |
| `LM_STUDIO_CONTEXT_LENGTH` | `16384` | context the launcher loads the model with (multi-page PDFs need ≥ 12k) |
| `OCR_BACKEND` | `lmstudio` | `lmstudio` (reuses the loaded vision model), `chandra` (needs working torch + GPU memory), `none` |
| `REQUIRE_INSTITUTION_HEADER` | `true` | reject submissions whose first page lacks the institution name (needs OCR) |
| `LLM_IMAGE_MAX_SIDE` | `1600` | page images are downscaled to this longest side before being sent to the model |

Smoke test against a running stack: `python scripts\e2e_smoke.py` (from `backend/`).
Unit tests: `python -m pytest tests -q` (from `backend/`).

### Admin account

An admin can do everything a teacher can (classes, assignments, grading, analytics) plus the
Admin Panel (`/admin`: users, roles, passwords). Public registration cannot create admins;
create or promote one directly in the database (backend running or not):

```Shell
python scripts\create_admin.py --email admin@university.edu --name Admin   # prompts for the password
```

The first backend start also creates a default admin (`admin@checkmate.ai`, see
`backend/routers/admin.py`) unless `ADMIN_EMAIL` / `ADMIN_PASSWORD` are set in `backend/.env`;
change its password or delete it from the Admin Panel.

### Moving the database with the project

MongoDB and its data are installed per machine, so a copy of the project folder has no
accounts or submissions in it. To take them along:

```Shell
python scripts\db_backup.py        # writes db-backup\checkmate_ai.jsonl.gz (all collections, one file)
```

Ship that file inside the project folder. On the other machine `Start-CheckMate.bat` loads it
automatically the first time it finds the database empty (`-NoRestore` disables this). Into a
database that already has data use `python scripts\db_restore.py --replace` (drops and reloads
the file's collections, asks to confirm) or `--merge` (upserts by id); `--info` only lists the
contents. The backup holds every account with its password hash and all student data, so keep
it confidential; `db-backup/` is git-ignored so it never lands in a repository by accident.

### Hosting it for free (GitHub Pages + MongoDB Atlas + a tunnel to this PC)

Everything except the vision model can live on free services. The model and the backend stay on
the PC with the GPU and are reached through a tunnel, so the site works while that PC is running
`Start-CheckMate.bat`.

| Part | Where | How |
| --- | --- | --- |
| Frontend | GitHub Pages | `.github/workflows/deploy-pages.yml` builds `frontend/` on every push to `main` and publishes it at `https://<user>.github.io/<repo>/` |
| Database | MongoDB Atlas (free M0 cluster) | `MONGO_URI=mongodb+srv://...` in `backend/.env`; `python scripts\db_restore.py` loads the local backup into it once |
| Backend + LM Studio | this PC | `Start-CheckMate.bat` as usual; it also opens the tunnel and shows the public address |
| Tunnel | ngrok (one fixed free domain) or cloudflared | `TUNNEL_PROVIDER` / `TUNNEL_DOMAIN` in `backend/.env` |

1. **Atlas** - create a free cluster and a database user, and allow access from anywhere
   (`0.0.0.0/0`; this PC's address changes). Put the connection string into `backend/.env` as
   `MONGO_URI` (the database name still comes from `DATABASE_NAME`), then run
   `python scripts\db_restore.py` - or let the launcher load the backup on the first start, when
   it finds the database empty.
2. **Tunnel** - ngrok gives one fixed free domain per account: install it
   (`winget install Ngrok.Ngrok`), run `ngrok config add-authtoken <token>` once, and set
   `TUNNEL_PROVIDER=ngrok` and `TUNNEL_DOMAIN=<yours>.ngrok-free.app`. With your own domain on
   Cloudflare use `TUNNEL_PROVIDER=cloudflared` with `TUNNEL_NAME` and `TUNNEL_DOMAIN` (named
   tunnel). `cloudflared` without a domain works too, but the address changes on every start.
3. **CORS** - add the site to `CORS_ORIGINS` in `backend/.env`, e.g. `...,https://<user>.github.io`.
4. **Frontend** - set `VITE_API_URL=https://<tunnel domain>` in `frontend/.env.production`, push
   to `main`, and once enable Pages with source "GitHub Actions" (repository Settings -> Pages).
   The workflow sets the `/<repo>/` sub-path and writes `404.html` so page refreshes work.
5. Run `Start-CheckMate.bat`. The summary shows the public API address and the tunnel check;
   `-NoTunnel` skips it.

Uploads (`uploads/`) stay on this PC. GitHub Pages on a free account needs a public repository,
so secrets must stay out of it: `backend/.env`, `db-backup/`, `uploads/`, `logs/` and `Login.txt`
are git-ignored. ngrok's free plan allows about 1 GB of traffic a month and shows a one-time
warning page when a browser opens an API link directly (the app's own requests skip it).

### Manual start

### Prerequisites

* Python 3.10+ (Anaconda recommended)
* Node.js 18+
* MongoDB running on `localhost:27017`
* LM Studio with a vision model loaded (e.g. `qwen2.5-vl-7b`)

### Backend

```Shell
cd backend
conda activate checkmate-ai
pip install -r requirements-torch-cuda.txt   # CUDA PyTorch first (NVIDIA GPU, ~3 GB download)
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Clear cache and start
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API available at <http://localhost:8000> | Docs at <http://localhost:8000/docs>

### Frontend

```Shell
cd frontend
npm install
npm run dev
```

App available at <http://localhost:5173>

### LM Studio

1. Download and install [LM Studio](https://lmstudio.ai)
2. Search and download `qwen2.5-vl-7b` (vision model)
3. Load the model and start the local server (port 1234)

## Project Structure

```
checkmate-ai/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── database.py             # MongoDB connection
│   ├── core/
│   │   ├── llm.py              # LM Studio integration
│   │   └── security.py         # JWT + password hashing
│   ├── models/
│   │   ├── user.py             # User schemas
│   │   └── school.py           # Class/Assignment/Submission schemas
│   ├── routers/
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── classes.py          # Class CRUD
│   │   ├── assignments.py      # Assignment management
│   │   ├── submissions.py      # Student submissions
│   │   ├── enrollment.py       # Class enrollment
│   │   ├── dashboard.py        # Teacher stats
│   │   └── analytics.py        # Performance analytics
│   └── services/
│       ├── grading.py          # Unified grading pipeline
│       ├── ocr.py              # Chandra OCR 2
│       ├── language_detection.py
│       ├── code_extraction.py
│       ├── code_execution.py
│       ├── code_grading.py
│       ├── parsing.py
│       ├── xai.py              # Explainable AI feedback
│       └── monitoring.py       # Analytics & prediction
├── frontend/
│   └── src/
│       ├── pages/              # Login, Dashboard, Settings, etc.
│       ├── components/         # Sidebar, UploadWidget, ThemeSwitcher
│       ├── contexts/           # Theme + Toast providers
│       └── services/api.js     # Axios HTTP client
└── docs/                       # Documentation
```

## Documentation

* [API Reference](docs/API.md)
* [User Guide](docs/USER_GUIDE.md)
* [Project Report](docs/PROJECT_REPORT.md)

## Team

| Name            | Contribution                          |
| --------------- | ------------------------------------- |
| Hassan Jahangir | Full-Stack Development                |
| Muhammad Ibad   | Backend / AI Integration              |
| Muhammad Muneeb | Frontend / UI/UX, AI, XAI & LLM       |

No designated team lead; the project was built jointly.

## License

This project was developed as the BS Artificial Intelligence (BS-AI) Final Year Project
at SZABIST Islamabad.

CheckMate AI — an AI-powered exam grading platform (SZABIST Islamabad, BS-AI FYP).

Stack:

Backend: FastAPI + Motor (async MongoDB), JWT auth
Frontend: React 19 + Vite 8, Recharts, Lucide
AI: LM Studio (Qwen2.5-VL vision model) via OpenAI-compatible API
OCR: Chandra OCR 2 (HuggingFace, 90+ languages)
Layout (README.md:71-109):

backend/ — FastAPI app with routers (auth, classes, assignments, submissions, analytics) and services for the grading pipeline (grading.py, ocr.py, xai.py, code_execution.py, monitoring.py)
frontend/ — React app (pages, components, theme/toast contexts, Axios client)
widget/ — separate upload widget
uploads/ — submission storage
docs/ — API, user guide, project report
Core flow: Teachers create classes/assignments with rubrics → students submit files → backend OCRs, detects language, extracts/executes code, grades with a vision LLM, and returns XAI feedback (keywords, criteria breakdown, strengths/improvements) plus performance-prediction analytics.

Roles: separate Teacher and Student portals; role-based access via JWT.
