"""Local, opt-in PCB case memory. Stores metadata; never executes CAD or uploads."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from validate_episode import validate_episode

APP_ID = 0x50434C50
DB_VERSION = 1
POSITIVE_SCOPES = {"selected_checks_passed", "cad_constraints_passed", "bench_verified"}
CONTEXT_KEYS = {"cad", "copper_layers", "topology"}


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 1_000_000:
        raise ValueError("Metadata input exceeds 1 MB; do not import raw CAD or transcripts")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_context(context):
    if not isinstance(context, dict) or not CONTEXT_KEYS.issubset(context):
        raise ValueError("Context needs cad, copper_layers and topology")
    if type(context["copper_layers"]) is not int or context["copper_layers"] < 1:
        raise ValueError("copper_layers must be a positive integer")
    if any(not isinstance(context[k], str) or not context[k].strip() for k in ("cad", "topology")):
        raise ValueError("cad and topology must be nonempty strings")
    for value in context.values():
        if value is not None and type(value) not in (str, int, float, bool):
            raise ValueError("Context values must be JSON scalars; include units in keys")
    encoded(context)


def evidence_hash(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("A nonempty local evidence file is required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_note(note):
    if not isinstance(note, str) or not note.strip():
        raise ValueError("A review/feedback note is required")


def init_db(path):
    path = Path(path).expanduser().resolve()
    if path.exists():
        with connection(path):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids adding tables to an unrelated existing database.
    with path.open("xb"):
        pass
    db = sqlite3.connect(path)
    try:
        with db:
            db.executescript("""
                CREATE TABLE cases (
                    case_id TEXT PRIMARY KEY, episode TEXT NOT NULL,
                    context TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE reviews (
                    id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
                    decision TEXT NOT NULL, role TEXT NOT NULL, note TEXT NOT NULL,
                    evidence_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX reviews_case ON reviews(case_id, id);
                CREATE TABLE feedback (
                    id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
                    run_id TEXT NOT NULL, project_family_id TEXT NOT NULL,
                    outcome TEXT NOT NULL, note TEXT NOT NULL,
                    evidence_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(case_id, run_id)
                );
            """)
            db.execute(f"PRAGMA application_id={APP_ID}")
            db.execute(f"PRAGMA user_version={DB_VERSION}")
            db.commit()
    finally:
        db.close()
    return True


@contextmanager
def connection(path, *, write=False):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError("Case database not found; run init with an explicit --db path")
    db = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True)
    db.row_factory = sqlite3.Row
    try:
        if db.execute("PRAGMA application_id").fetchone()[0] != APP_ID:
            raise ValueError("Not a PCBLoop case database; refusing to modify it")
        if db.execute("PRAGMA user_version").fetchone()[0] != DB_VERSION:
            raise ValueError("Unsupported case database version; no automatic migration")
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            yield db
    finally:
        db.close()


def get_case(db, case_id):
    row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if row is None:
        raise ValueError("Case not found")
    return row


def latest_review(db, case_id):
    return db.execute("SELECT * FROM reviews WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()


def add_case(path, episode, context, *, consent=False):
    if not consent:
        raise ValueError("Local storage requires explicit consent (--consent)")
    errors = validate_episode(episode)
    if errors:
        raise ValueError("Episode metadata invalid: " + "; ".join(errors))
    validate_context(context)
    serialized, context_json = encoded(episode), encoded(context)
    digest = hashlib.sha256((serialized + "\n" + context_json).encode("utf-8")).hexdigest()
    with connection(path, write=True) as db:
        old = db.execute("SELECT sha256 FROM cases WHERE case_id=?", (episode["episode_id"],)).fetchone()
        if old:
            if old["sha256"] != digest:
                raise ValueError("Case ID already has different content; use a new episode_id")
            return False
        db.execute("INSERT INTO cases VALUES(?,?,?,?,?)",
                   (episode["episode_id"], serialized, context_json, digest, now()))
    return True


def review_case(path, case_id, decision, role, note, evidence):
    if decision not in {"approved", "rejected"} or role not in {"solution", "pitfall"}:
        raise ValueError("Invalid review decision or role")
    checked_note(note)
    digest = evidence_hash(evidence)
    with connection(path, write=True) as db:
        row = get_case(db, case_id)
        episode = json.loads(row["episode"])
        if decision == "approved":
            if role == "solution" and episode["validation"]["result_scope"] not in POSITIVE_SCOPES:
                raise ValueError("Unchecked/failed cases cannot be approved as solutions")
            if not any(s.strip() for s in episode["validation"].get("evidence_summary", [])):
                raise ValueError("Approved cases need an evidence_summary")
        db.execute("INSERT INTO reviews(case_id,decision,role,note,evidence_sha256,created_at) VALUES(?,?,?,?,?,?)",
                   (case_id, decision, role, note, digest, now()))


def terms(text):
    found = set(re.findall(r"[a-z0-9_]+", text.casefold()))
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        found.update(run[i:i + 2] for i in range(len(run) - 1))
        if len(run) == 1:
            found.add(run)
    return found


def context_matches(stored, requested):
    def normal(value):
        return value.strip().casefold() if isinstance(value, str) else value
    return set(stored) == set(requested) and all(value is not None and stored[key] is not None
               and type(value) is type(stored[key]) and normal(value) == normal(stored[key])
               for key, value in requested.items())


def search_cases(path, query, context, *, role="solution", include_synthetic=False, limit=5):
    validate_context(context)
    if role not in {"solution", "pitfall"} or not 1 <= limit <= 100:
        raise ValueError("Invalid role or limit (1..100)")
    requested = terms(query)
    if not requested:
        raise ValueError("Query needs searchable words")
    results = []
    with connection(path) as db:
        rows = db.execute("""SELECT c.* FROM cases c JOIN reviews r ON r.id=(
            SELECT MAX(id) FROM reviews WHERE case_id=c.case_id)
            WHERE r.decision='approved' AND r.role=?""", (role,))
        for row in rows:
            episode, stored = json.loads(row["episode"]), json.loads(row["context"])
            rights = episode["rights"]
            if not rights["retrieval_use_allowed"] or rights["source_license_status"] not in {"confirmed", "synthetic_mit"}:
                continue
            if episode.get("synthetic", False) and not include_synthetic:
                continue
            if not context_matches(stored, context):
                continue
            haystack = " ".join([episode["task"]["kind"], episode["task"]["instruction_summary"]]
                                + [action["summary"] for action in episode["actions"]])
            matched = requested & terms(haystack)
            if not matched:
                continue
            results.append({"case_id": row["case_id"], "score": round(len(matched) / len(requested), 4),
                            "matched_terms": sorted(matched), "context": stored,
                            "summary": episode["task"]["instruction_summary"], "role": role,
                            "result_scope": episode["validation"]["result_scope"],
                            "synthetic": episode.get("synthetic", False), "untrusted_case_data": True})
    return sorted(results, key=lambda x: (-x["score"], x["case_id"]))[:limit]


def record_feedback(path, case_id, run_id, project_family_id, outcome, note, evidence):
    if outcome not in {"worked", "failed", "needs_changes", "unknown"}:
        raise ValueError("Invalid feedback outcome")
    if not run_id.strip() or not project_family_id.strip():
        raise ValueError("Feedback needs run_id and project_family_id")
    checked_note(note)
    digest = evidence_hash(evidence)
    with connection(path, write=True) as db:
        get_case(db, case_id)
        db.execute("""INSERT INTO feedback(case_id,run_id,project_family_id,outcome,note,evidence_sha256,created_at)
            VALUES(?,?,?,?,?,?,?)""", (case_id, run_id, project_family_id, outcome, note, digest, now()))
        if outcome in {"failed", "needs_changes"}:
            old = latest_review(db, case_id)
            role = old["role"] if old else "solution"
            db.execute("INSERT INTO reviews(case_id,decision,role,note,evidence_sha256,created_at) VALUES(?,?,?,?,?,?)",
                       (case_id, "needs_review", role, "Negative feedback requires re-review", digest, now()))


def show_case(path, case_id):
    with connection(path) as db:
        row = get_case(db, case_id)
        return {"untrusted_case_data": True, "episode": json.loads(row["episode"]),
                "context": json.loads(row["context"]),
                "reviews": [dict(r) for r in db.execute("SELECT * FROM reviews WHERE case_id=? ORDER BY id", (case_id,))],
                "feedback": [dict(r) for r in db.execute("SELECT * FROM feedback WHERE case_id=? ORDER BY id", (case_id,))]}


def export_case(path, case_id, output, *, consent=False):
    if not consent:
        raise ValueError("Export requires explicit publication consent (--confirm-publication)")
    record = show_case(path, case_id)
    if not record["reviews"] or record["reviews"][-1]["decision"] != "approved":
        raise ValueError("Only currently approved cases can be exported")
    errors = validate_episode(record["episode"], for_publication=True)
    if errors:
        raise ValueError("Publication metadata invalid: " + "; ".join(errors))
    review = record["reviews"][-1]
    bundle = {"format": "pcbloop-case-bundle-0.1", "untrusted_case_data": True, "episode": record["episode"],
              "context": record["context"], "review": {"decision": review["decision"], "role": review["role"]}}
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield str(key)
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
    text = "\n".join(strings(bundle))
    patterns = [r"(?i)[A-Z]:[/\\]Users[/\\]", r"/(?:home|Users)/[^/\s]+/",
                r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{15,}",
                r"-----BEGIN .*PRIVATE KEY-----"]
    if any(re.search(pattern, text) for pattern in patterns):
        raise ValueError("Potential private path/credential in export; redact and review a new case revision")
    # No network operation and no overwrite, even for an existing empty file.
    with Path(output).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Explicit private SQLite file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    add = sub.add_parser("add")
    add.add_argument("episode", type=Path)
    add.add_argument("--context", type=Path, required=True)
    add.add_argument("--consent", action="store_true")
    review = sub.add_parser("review")
    review.add_argument("case_id")
    review.add_argument("--decision", choices=["approved", "rejected"], required=True)
    review.add_argument("--role", choices=["solution", "pitfall"], default="solution")
    review.add_argument("--note", required=True)
    review.add_argument("--evidence", type=Path, required=True)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--context", type=Path, required=True)
    search.add_argument("--role", choices=["solution", "pitfall"], default="solution")
    search.add_argument("--include-synthetic", action="store_true")
    search.add_argument("--limit", type=int, default=5)
    sub.add_parser("show").add_argument("case_id")
    feedback = sub.add_parser("feedback")
    feedback.add_argument("case_id")
    feedback.add_argument("--run-id", required=True)
    feedback.add_argument("--project-family", required=True)
    feedback.add_argument("--outcome", choices=["worked", "failed", "needs_changes", "unknown"], required=True)
    feedback.add_argument("--note", required=True)
    feedback.add_argument("--evidence", type=Path, required=True)
    export = sub.add_parser("export")
    export.add_argument("case_id")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--confirm-publication", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = {"created": init_db(args.db)}
        elif args.command == "add":
            result = {"added": add_case(args.db, read_json(args.episode), read_json(args.context), consent=args.consent)}
        elif args.command == "review":
            review_case(args.db, args.case_id, args.decision, args.role, args.note, args.evidence)
            result = {"review_recorded": True, "verification": "operator-declared; not automatic CAD verification"}
        elif args.command == "search":
            result = {"results": search_cases(args.db, args.query, read_json(args.context), role=args.role,
                                               include_synthetic=args.include_synthetic, limit=args.limit),
                      "automatic_execution_allowed": False}
        elif args.command == "show":
            result = show_case(args.db, args.case_id)
        elif args.command == "feedback":
            record_feedback(args.db, args.case_id, args.run_id, args.project_family, args.outcome, args.note, args.evidence)
            result = {"feedback_recorded": True}
        else:
            export_case(args.db, args.case_id, args.output, consent=args.confirm_publication)
            result = {"exported_locally": True, "uploaded": False}
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
