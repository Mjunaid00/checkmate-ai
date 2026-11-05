"""
Environment probe used by scripts\start-checkmate.ps1. Run it with the env's python.exe:

    python check_env.py gpu
    python check_env.py requirements <requirements.txt>
    python check_env.py imports <module> [<module> ...]
    python check_env.py mongo [<database>]

Each mode prints exactly one line "CHECKENV_JSON:{...}" on stdout; everything the probed
libraries print is discarded, so the launcher can parse the result reliably.
Exit code 0 = fine, 1 = something is missing or broken, 2 = usage error.

  gpu          -> python, torch version, cuda (bool), cuda_version, device, torchaudio state,
                  transformers version
  requirements -> "missing": requirement lines that are not installed or have the wrong
                  version, including the direct dependencies of each line and of its
                  extras (e.g. chandra-ocr[hf] -> torch>=2.8, transformers>=5.2)
  imports      -> "missing": modules that cannot be imported, with the error
  mongo        -> pings MONGO_URI from backend/.env (the URI never appears on a command
                  line): ok, hosted (Atlas / remote), uri_host, version, documents in <database>
"""
import importlib
import importlib.metadata as md
import json
import os
import sys
import warnings

MARK = "CHECKENV_JSON:"
_REAL_STDOUT = sys.stdout


def emit(obj, code=0):
    _REAL_STDOUT.write(MARK + json.dumps(obj) + "\n")
    _REAL_STDOUT.flush()
    sys.exit(code)


def _first_line(exc):
    text = str(exc).strip()
    return (text.splitlines()[0] if text else type(exc).__name__)[:200]


# ----------------------------------------------------------------------------- gpu
def mode_gpu():
    info = {
        "python": sys.version.split()[0],
        "torch": None, "torch_error": None,
        "cuda": False, "cuda_version": None, "device": None,
        "torchaudio": None, "torchaudio_ok": False,
        "transformers": None,
    }
    try:
        import torch  # noqa: WPS433  (slow import, that is fine here)
        info["torch"] = torch.__version__
        info["cuda_version"] = torch.version.cuda
        info["cuda"] = bool(torch.cuda.is_available())
        if info["cuda"]:
            info["device"] = torch.cuda.get_device_name(0)
    except Exception as exc:  # ImportError, OSError (WinError 126) ...
        info["torch_error"] = _first_line(exc)
    try:
        info["torchaudio"] = md.version("torchaudio")
        try:
            importlib.import_module("torchaudio")
            info["torchaudio_ok"] = True
        except Exception:
            info["torchaudio_ok"] = False
    except md.PackageNotFoundError:
        pass
    try:
        info["transformers"] = md.version("transformers")
    except md.PackageNotFoundError:
        pass
    emit(info, 0 if info["cuda"] else 1)


# ----------------------------------------------------------------- requirements
def _requirement_class():
    try:
        from packaging.requirements import Requirement
    except ImportError:  # packaging is always vendored inside pip
        from pip._vendor.packaging.requirements import Requirement
    return Requirement


def _applies(req, extra):
    """Does this requirement apply to the running interpreter (for the given extra)?"""
    if req.marker is None:
        return True
    try:
        return bool(req.marker.evaluate({"extra": extra or ""}))
    except Exception:
        return False


def _check(req, Requirement, problems, seen, depth):
    """Check one requirement; at depth 0 also check its direct deps (incl. extras)."""
    try:
        version = md.version(req.name)
    except md.PackageNotFoundError:
        problems.append(f"{req} (not installed)")
        return
    if req.specifier and not req.specifier.contains(version, prereleases=True):
        problems.append(f"{req} (installed {version})")
        return
    key = req.name.lower()
    if depth >= 1 or key in seen:
        return
    seen.add(key)
    extras = {e.lower() for e in req.extras}
    for dep_str in md.requires(req.name) or []:
        try:
            dep = Requirement(dep_str)
        except Exception:
            continue
        if not (_applies(dep, "") or any(_applies(dep, e) for e in extras)):
            continue
        sub = []
        _check(dep, Requirement, sub, seen, depth + 1)
        problems.extend(f"{p} <- {req}" for p in sub)


def mode_requirements(path):
    Requirement = _requirement_class()
    problems, seen, checked = [], set(), 0
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-"):  # blank, comment, --index-url, -r ...
                continue
            try:
                req = Requirement(line)
            except Exception:
                problems.append(f"{line} (unparsable line)")
                continue
            if not _applies(req, ""):
                continue
            checked += 1
            _check(req, Requirement, problems, seen, 0)
    emit({"file": os.path.basename(path), "checked": checked, "missing": problems},
         1 if problems else 0)


# ---------------------------------------------------------------------- imports
def mode_imports(modules):
    missing = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:
            missing.append(f"{name}: {type(exc).__name__}: {_first_line(exc)}")
    emit({"ok": not missing, "missing": missing}, 1 if missing else 0)


# ------------------------------------------------------------------------ mongo
def mode_mongo(db_name):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
    info = {"ok": False, "hosted": False, "uri_host": None, "version": None, "documents": None, "error": None}
    try:
        import config  # loads backend/.env
        from pymongo import MongoClient
        uri = config.MONGO_URI
        info["hosted"] = uri.startswith("mongodb+srv://") or not any(h in uri for h in ("localhost", "127.0.0.1"))
        try:
            info["uri_host"] = uri.split("://", 1)[1].split("@")[-1].split("/", 1)[0].split("?", 1)[0]
        except Exception:
            pass
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        info["version"] = client.server_info()["version"]
        db = client[db_name or config.DATABASE_NAME]
        info["documents"] = sum(db[n].estimated_document_count()
                                for n in db.list_collection_names() if not n.startswith("system."))
        info["ok"] = True
    except Exception as exc:
        info["error"] = _first_line(exc)
    emit(info, 0 if info["ok"] else 1)


def main(argv):
    warnings.filterwarnings("ignore")
    # Libraries print banners / warnings; keep stdout clean for the JSON line.
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    if len(argv) < 2:
        emit({"error": "usage: check_env.py gpu | requirements <file> | imports <module>..."}, 2)
    mode = argv[1]
    if mode == "gpu":
        mode_gpu()
    elif mode == "requirements" and len(argv) >= 3 and os.path.isfile(argv[2]):
        mode_requirements(argv[2])
    elif mode == "imports" and len(argv) >= 3:
        mode_imports(argv[2:])
    elif mode == "mongo":
        mode_mongo(argv[2] if len(argv) >= 3 else None)
    else:
        emit({"error": f"bad arguments: {argv[1:]}"}, 2)


if __name__ == "__main__":
    main(sys.argv)
