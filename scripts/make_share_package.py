"""
Build a zip of CheckMate AI that another Windows laptop with an NVIDIA GPU can run locally.

    cd <project>
    python scripts\\make_share_package.py              # dist-share\\CheckMateAI-<date>.zip, WITH the database copy and uploads
    python scripts\\make_share_package.py --no-data    # code only (recipient starts with the default admin account)
    python scripts\\make_share_package.py --out D:\\somewhere

What goes in: backend, frontend (sources, no node_modules), scripts, launcher .bat files,
README and docs (markdown only), a fresh backend\\.env (random JWT secret, no tunnel, local
settings), and - unless --no-data - a fresh db-backup\\checkmate_ai.jsonl.gz plus uploads\\.
Left out: .git, logs, caches, node_modules, the demo video and screenshots, Login.txt, the
pre-fix snapshot, your real backend\\.env and the ngrok address in frontend\\.env.production.

The database copy holds every account (password hashes) and all student data: only share
the zip with people who may have it. Review this script before use elsewhere.
"""
import argparse
import fnmatch
import secrets
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR_NAME = "CheckMateAI"

INCLUDE_TOP = ["backend", "frontend", "scripts", "docs", "Start-CheckMate.bat", "Stop-CheckMate.bat", "README.md", ".gitignore"]
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "dist", ".vite", ".git", "logs", "screen_shorts", "testvideo"}
EXCLUDE_FILES = {".env", "Login.txt", ".env.production", "backend.log", "frontend.log"}
EXCLUDE_GLOBS = ["*.pyc", "*.log", "*.part"]

START_HERE = """CheckMate AI - run it on this laptop
=====================================

Install once, in this order (all free):
  1. An NVIDIA GPU with 8 GB of VRAM and a current driver (the vision model needs about 6 GB).
  2. Anaconda or Miniconda, default install location      https://www.anaconda.com/download
  3. MongoDB Community Server, installed as a Windows service   https://www.mongodb.com/try/download/community
  4. Node.js 22 LTS                                       https://nodejs.org
  5. LM Studio                                            https://lmstudio.ai
     Open it once, search for  qwen/qwen2.5-vl-7b  and download it (about 5 GB).

Then unzip this folder anywhere (a path without spaces is safest) and double-click
Start-CheckMate.bat.

The first start takes 5 to 15 minutes. It creates the "checkmate-ai" conda environment,
installs the CUDA build of PyTorch and all Python packages, installs the frontend packages,
starts MongoDB (one administrator prompt), starts LM Studio's server and loads the model,
restores the included database copy (if any), and opens http://localhost:5173 in the browser.
Later starts take about a minute.

Accounts
  With the database copy: the sender's accounts are included. Ask the sender for the admin
  password (admin@university.edu). The built-in admin@checkmate.ai / admin123 also exists.
  Without the database copy: admin@checkmate.ai / admin123 is created on the first start.
  Change these passwords after the first login (Admin Panel).

Stop: Stop-CheckMate.bat.

If something fails, read the red FAIL line in the launcher window; details are in
logs\\backend.log, logs\\frontend.log and logs\\pip-install.log. A diagnosis without starting
anything:  powershell -ExecutionPolicy Bypass -File scripts\\start-checkmate.ps1 -ChecksOnly
More in README.md (sections "Quick Start" and "Admin account").
"""


def wanted(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts[:-1]):
        return False
    if rel.name in EXCLUDE_FILES:
        return False
    if any(fnmatch.fnmatch(rel.name, g) for g in EXCLUDE_GLOBS):
        return False
    if parts[0] == "docs" and rel.suffix.lower() != ".md":
        return False
    return True


def packaged_env() -> str:
    """backend/.env for the recipient: the example file with a fresh secret and local-only settings."""
    example = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    out = []
    for line in example.splitlines():
        if line.startswith("JWT_SECRET="):
            line = "JWT_SECRET=" + secrets.token_urlsafe(48)
        elif line.startswith("TUNNEL_PROVIDER="):
            line = "TUNNEL_PROVIDER=none"
        elif line.startswith("TUNNEL_DOMAIN=") or line.startswith("TUNNEL_NAME="):
            line = line.split("=", 1)[0] + "="
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a shareable zip of CheckMate AI.")
    ap.add_argument("--out", default=str(ROOT / "dist-share"), help="output folder (default: dist-share)")
    ap.add_argument("--no-data", action="store_true", help="leave out the database copy and uploads")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    zip_path = out_dir / f"{PACKAGE_DIR_NAME}-{stamp}.zip"

    files: list[tuple[Path, str]] = []  # (source, arcname)
    for top in INCLUDE_TOP:
        p = ROOT / top
        if p.is_file():
            files.append((p, f"{PACKAGE_DIR_NAME}/{top}"))
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(ROOT)
                    if wanted(rel):
                        files.append((f, f"{PACKAGE_DIR_NAME}/{rel.as_posix()}"))

    data_note = "no database copy (--no-data)"
    if not args.no_data:
        print("refreshing db-backup\\checkmate_ai.jsonl.gz ...")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "db_backup.py")], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            print("error: database backup failed - is MongoDB running? Use --no-data to package without it.")
            return 1
        print("  " + (r.stdout.strip().splitlines() or [""])[0])
        backup = ROOT / "db-backup" / "checkmate_ai.jsonl.gz"
        files.append((backup, f"{PACKAGE_DIR_NAME}/db-backup/checkmate_ai.jsonl.gz"))
        uploads = ROOT / "uploads"
        n_uploads = 0
        if uploads.is_dir():
            for f in sorted(uploads.rglob("*")):
                if f.is_file() and not f.name.startswith(".healthcheck"):
                    files.append((f, f"{PACKAGE_DIR_NAME}/{f.relative_to(ROOT).as_posix()}"))
                    n_uploads += 1
        data_note = f"database copy + {n_uploads} upload files included"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arc)
        zf.writestr(f"{PACKAGE_DIR_NAME}/backend/.env", packaged_env())
        zf.writestr(f"{PACKAGE_DIR_NAME}/frontend/.env.production",
                    "# Only used when the frontend is hosted elsewhere (see README). Local use ignores this file.\n"
                    "VITE_API_URL=https://REPLACE-WITH-YOUR-TUNNEL-DOMAIN\n")
        zf.writestr(f"{PACKAGE_DIR_NAME}/START-HERE.txt", START_HERE)
        zf.writestr(f"{PACKAGE_DIR_NAME}/logs/.keep", "")
        zf.writestr(f"{PACKAGE_DIR_NAME}/uploads/.keep", "")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\nwrote {zip_path}  ({size_mb:.1f} MB, {len(files) + 5} files; {data_note})")
    if not args.no_data:
        print("note: the zip contains every account (password hashes) and all student data - share it only with people who may have it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
