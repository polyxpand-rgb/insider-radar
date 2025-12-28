import os, sys
from dotenv import load_dotenv
import psycopg

WORKER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKER_ROOT)

ENV_PATH = os.path.abspath(os.path.join(WORKER_ROOT, ".env"))
load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing")

with psycopg.connect(DATABASE_URL) as conn:
    rows = conn.execute("""
      select
        t.transaction_date,
        c.name as company,
        t.owner_name,
        t.transaction_code,
        t.shares,
        t.price,
        t.total_value
      from transactions t
      join companies c on c.issuer_cik = t.issuer_cik
      order by abs(coalesce(t.total_value,0)) desc
      limit 10;
    """).fetchall()

for r in rows:
    print(r)