import os
import glob
import psycopg
from dotenv import load_dotenv

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL is required (check {ENV_PATH})")

MIGRATIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "migrations"))

def ensure_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

def applied_versions(conn) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}

def main():
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if not files:
        print("No migrations found.")
        return

    with psycopg.connect(DATABASE_URL) as conn:
        conn.autocommit = False
        ensure_table(conn)
        done = applied_versions(conn)

        for path in files:
            version = os.path.basename(path)
            if version in done:
                continue

            sql = open(path, "r", encoding="utf-8").read()
            print(f"Applying {version}...")
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()

    print("Migrations complete.")

if __name__ == "__main__":
    main()
