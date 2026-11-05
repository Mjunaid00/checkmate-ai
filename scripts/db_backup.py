"""
Export the whole CheckMate database to one file that travels with the project.

    cd <project>
    python scripts\\db_backup.py                 # -> db-backup\\<DATABASE_NAME>.jsonl.gz (overwritten)
    python scripts\\db_backup.py --timestamp     # -> db-backup\\<DATABASE_NAME>-YYYYMMDD-HHMM.jsonl.gz
    python scripts\\db_backup.py --out path.jsonl.gz

Connection settings come from backend/.env (MONGO_URI, DATABASE_NAME; --db overrides the
name). The file is gzip-compressed JSON Lines in MongoDB Extended JSON (canonical), so
ObjectIds, dates and binary values round-trip exactly:

    line 1      manifest {"format": "checkmate-db-backup", "version": 1, "database": ..., "collections": {...}}
    other lines {"c": "<collection>", "d": {<document>}}

Restore with scripts\\db_restore.py. On a machine whose database is still empty, the launcher
restores db-backup\\<DATABASE_NAME>.jsonl.gz automatically on first start.

The file contains every account (including password hashes) and all student data: treat it
as confidential and remove it from a copy of the project you share publicly.
"""
import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402  (loads backend/.env)
from bson import json_util  # noqa: E402
from pymongo import MongoClient  # noqa: E402

FORMAT = "checkmate-db-backup"
VERSION = 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Export the CheckMate MongoDB database to one file.")
    ap.add_argument("--db", default=config.DATABASE_NAME, help="database name (default: DATABASE_NAME from backend/.env)")
    ap.add_argument("--out", default=None, help="output file (default: db-backup/<db>.jsonl.gz)")
    ap.add_argument("--timestamp", action="store_true", help="add the date and time to the default file name")
    args = ap.parse_args()

    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"error: MongoDB not reachable at {config.mask_uri(config.MONGO_URI) if hasattr(config, 'mask_uri') else config.MONGO_URI}: {exc}")
        return 1
    db = client[args.db]

    if args.out:
        out = Path(args.out)
    else:
        stamp = datetime.now().strftime("-%Y%m%d-%H%M") if args.timestamp else ""
        out = ROOT / "db-backup" / f"{args.db}{stamp}.jsonl.gz"
    out.parent.mkdir(parents=True, exist_ok=True)

    names = sorted(n for n in db.list_collection_names() if not n.startswith("system."))
    counts = {n: db[n].count_documents({}) for n in names}
    manifest = {
        "format": FORMAT,
        "version": VERSION,
        "database": args.db,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "collections": counts,
    }

    tmp = out.with_suffix(out.suffix + ".part")
    written = 0
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest) + "\n")
        for name in names:
            for doc in db[name].find({}):
                fh.write(json.dumps({"c": name, "d": json.loads(json_util.dumps(doc, json_options=json_util.CANONICAL_JSON_OPTIONS))}) + "\n")
                written += 1
    os.replace(tmp, out)

    size_kb = max(1, out.stat().st_size // 1024)
    print(f"database '{args.db}': {written} documents in {len(names)} collections -> {out} ({size_kb} KB)")
    for name in names:
        print(f"  {name:18} {counts[name]}")
    print("note: the file holds every account (password hashes included) and all student data - keep it confidential.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
