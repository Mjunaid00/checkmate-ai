"""
Load a db_backup.py file into MongoDB.

    cd <project>
    python scripts\\db_restore.py                    # db-backup\\<DATABASE_NAME>.jsonl.gz into an EMPTY database
    python scripts\\db_restore.py --info             # only show what the file contains
    python scripts\\db_restore.py --replace          # drop the collections in the file first, then load (asks to confirm)
    python scripts\\db_restore.py --merge            # keep existing documents, upsert the file's documents by _id
    python scripts\\db_restore.py --file x.jsonl.gz --db other_name --yes

Connection settings come from backend/.env (MONGO_URI, DATABASE_NAME). Without --replace
or --merge the target database must be empty; the script refuses otherwise so nothing is
lost by accident. Stop the backend before restoring. The backend recreates its indexes on
the next start.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402  (loads backend/.env)
from bson import json_util  # noqa: E402
from pymongo import MongoClient, ReplaceOne  # noqa: E402

FORMAT = "checkmate-db-backup"
BATCH = 500


def read_manifest(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        manifest = json.loads(fh.readline())
    if manifest.get("format") != FORMAT:
        raise SystemExit(f"error: {path} is not a {FORMAT} file")
    return manifest


def iter_docs(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        fh.readline()  # manifest
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            yield rec["c"], json_util.loads(json.dumps(rec["d"]), json_options=json_util.CANONICAL_JSON_OPTIONS)


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore a CheckMate database backup.")
    ap.add_argument("--file", default=None, help="backup file (default: db-backup/<db>.jsonl.gz)")
    ap.add_argument("--db", default=config.DATABASE_NAME, help="target database (default: DATABASE_NAME from backend/.env)")
    ap.add_argument("--info", action="store_true", help="show the file's manifest and exit")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--replace", action="store_true", help="drop the collections contained in the file before loading")
    mode.add_argument("--merge", action="store_true", help="upsert documents by _id, keeping everything else")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation (needed for --replace when not interactive)")
    args = ap.parse_args()

    path = Path(args.file) if args.file else ROOT / "db-backup" / f"{args.db}.jsonl.gz"
    if not path.is_file():
        print(f"error: backup file not found: {path}")
        return 2
    manifest = read_manifest(path)
    total = sum(manifest["collections"].values())
    print(f"file: {path}")
    print(f"  exported {manifest.get('exported_at')} from database '{manifest.get('database')}': "
          f"{total} documents in {len(manifest['collections'])} collections")
    for name, n in manifest["collections"].items():
        print(f"  {name:18} {n}")
    if args.info:
        return 0

    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"error: MongoDB not reachable: {exc}")
        return 1
    db = client[args.db]
    existing = {n: db[n].estimated_document_count() for n in db.list_collection_names() if not n.startswith("system.")}
    has_data = any(c > 0 for c in existing.values())

    if has_data and not (args.replace or args.merge):
        print(f"error: database '{args.db}' already holds data ({sum(existing.values())} documents). "
              "Use --replace (drop the file's collections first) or --merge (upsert by _id).")
        return 3
    if args.replace and has_data:
        if not args.yes:
            if not sys.stdin.isatty():
                print("error: --replace on a non-empty database needs --yes when not run interactively")
                return 3
            typed = input(f"This DROPS the collections {sorted(manifest['collections'])} in '{args.db}'. "
                          f"Type the database name to continue: ")
            if typed.strip() != args.db:
                print("aborted")
                return 3
        for name in manifest["collections"]:
            db[name].drop()
        print("dropped:", ", ".join(sorted(manifest["collections"])))

    # Empty collections carry no documents, so create them explicitly to mirror the source.
    for name, n in manifest["collections"].items():
        if n == 0 and name not in db.list_collection_names():
            db.create_collection(name)

    inserted = upserted = 0
    batch_coll, batch = None, []

    def flush():
        nonlocal inserted, upserted, batch
        if not batch:
            return
        if args.merge:
            res = db[batch_coll].bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in batch], ordered=False)
            upserted += res.upserted_count + res.modified_count + res.matched_count
        else:
            db[batch_coll].insert_many(batch, ordered=False)
            inserted += len(batch)
        batch = []

    for coll, doc in iter_docs(path):
        if coll != batch_coll:
            flush()
            batch_coll = coll
        batch.append(doc)
        if len(batch) >= BATCH:
            flush()
    flush()

    if args.merge:
        print(f"merged {upserted} documents into database '{args.db}'")
    else:
        print(f"restored {inserted} documents into database '{args.db}'")
    print("start the backend (Start-CheckMate.bat) to recreate the indexes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
