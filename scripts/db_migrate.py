"""Apply supabase/migrations/*.sql to the Supabase database, in filename order.

Each migration runs in its own transaction and is recorded in public._schema_migrations,
so re-running the script applies only new files. The connection string comes from
SUPABASE_DB_URL in .env (session pooler) and is never printed.

    python scripts/db_migrate.py            # apply pending migrations
    python scripts/db_migrate.py --status   # list applied and pending migrations
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"

TRACKING_DDL = """
CREATE TABLE IF NOT EXISTS public._schema_migrations (
    filename TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE public._schema_migrations ENABLE ROW LEVEL SECURITY;
"""


def file_digest(path: Path) -> str:
    """SHA-256 of the file with line endings normalised, so a CRLF checkout matches."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--status", action="store_true", help="show applied/pending migrations and exit")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        print("SUPABASE_DB_URL is not set in .env", file=sys.stderr)
        return 1

    files = sorted(MIGRATIONS.glob("*.sql"))
    conn = psycopg2.connect(db_url, connect_timeout=20)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(TRACKING_DDL)
            cur.execute("SELECT filename, sha256 FROM public._schema_migrations")
            applied = dict(cur.fetchall())

        changed = [f.name for f in files if f.name in applied and applied[f.name] != file_digest(f)]
        pending = [f for f in files if f.name not in applied]

        for f in files:
            state = "applied" if f.name in applied else "pending"
            if f.name in changed:
                state = "applied, BUT FILE CHANGED SINCE"
            print(f"  {state:32} {f.name}")
        if changed:
            print("Refusing to continue: an applied migration was edited. Add a new migration instead.",
                  file=sys.stderr)
            return 2
        if args.status or not pending:
            print("Nothing to apply." if not pending else f"{len(pending)} pending.")
            return 0

        for f in pending:
            sql = f.read_text(encoding="utf-8")
            with conn, conn.cursor() as cur:  # one transaction per file
                cur.execute(sql)
                cur.execute("INSERT INTO public._schema_migrations (filename, sha256) VALUES (%s, %s)",
                            (f.name, file_digest(f)))
            print(f"  applied                          {f.name}")
        return 0
    except psycopg2.Error as e:
        print(f"Migration failed: {e.pgerror or e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
