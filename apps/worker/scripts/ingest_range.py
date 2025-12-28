import os
import sys
import argparse
from datetime import date, timedelta

WORKER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKER_ROOT)

import psycopg
from dotenv import load_dotenv

from worker.sec_client import SecClient
from worker.daily_index import fetch_form4_rows
from worker.ingest import ingest_index_row

ENV_PATH = os.path.abspath(os.path.join(WORKER_ROOT, ".env"))
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()

def parse_ymd(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))

def daterange(d1: date, d2: date):
    d = d1
    while d <= d2:
        yield d
        d += timedelta(days=1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="dto", required=True, help="YYYY-MM-DD")
    ap.add_argument("--limit", type=int, default=25, help="max filings per day (safety)")
    args = ap.parse_args()

    if not DATABASE_URL:
        raise RuntimeError(f"DATABASE_URL missing (check {ENV_PATH})")
    if not SEC_USER_AGENT:
        raise RuntimeError(f"SEC_USER_AGENT missing (check {ENV_PATH})")

    client = SecClient(SEC_USER_AGENT)

    total_filings = 0
    total_txs = 0

    with psycopg.connect(DATABASE_URL) as conn:
        for d in daterange(parse_ymd(args.dfrom), parse_ymd(args.dto)):
            rows = fetch_form4_rows(client, d)
            if not rows:
                print(f"{d}: no rows (weekend/holiday or none).")
                continue

            rows = rows[: args.limit]
            print(f"{d}: {len(rows)} Form 4 rows")

            for r in rows:
                try:
                    accession, n = ingest_index_row(conn, client, r)
                    conn.commit()
                    total_filings += 1
                    total_txs += n
                    print(f"  + {accession}: {n} tx")
                except Exception as e:
                    conn.rollback()
                    print(f"  ! error on {r.filename}: {e}")

    print(f"Done. filings={total_filings} transactions={total_txs}")

if __name__ == "__main__":
    main()