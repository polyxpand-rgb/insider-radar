from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

# apps/worker/scripts/enrich_tickers.py
# Run from repo root with .venv activated:
#   python .\apps\worker\scripts\enrich_tickers.py

WORKER_ROOT = Path(__file__).resolve().parents[1]          # .../apps/worker
ENV_PATH = WORKER_ROOT / ".env"
DATA_DIR = WORKER_ROOT / "data"
CACHE_PATH = DATA_DIR / "company_tickers.json"

TICKER_URL = "https://www.sec.gov/files/company_tickers.json"


def load_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    else:
        raise RuntimeError(f"Missing env file: {ENV_PATH}")


def fetch_ticker_map(force: bool = False) -> dict[str, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_PATH.exists() and not force:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    else:
        ua = os.getenv("SEC_USER_AGENT") or "InsiderRadar/0.1 (your-email@example.com)"
        r = requests.get(TICKER_URL, headers={"User-Agent": ua}, timeout=30)
        r.raise_for_status()
        raw = r.json()
        CACHE_PATH.write_text(json.dumps(raw), encoding="utf-8")

    # raw is like {"0": {"cik_str": 1045810, "ticker":"NVDA", ...}, ...}
    out: dict[str, str] = {}
    for _, v in raw.items():
        cik = str(int(v["cik_str"]))          # normalize to no-leading-zero string
        ticker = (v.get("ticker") or "").strip()
        if ticker:
            out[cik] = ticker
    return out


def main() -> None:
    load_env()
    db = os.getenv("DATABASE_URL")
    if not db:
        raise RuntimeError("DATABASE_URL is required")

    ticker_map = fetch_ticker_map(force=False)
    print(f"Loaded ticker map: {len(ticker_map)} rows")

    updated = 0
    with psycopg.connect(db) as conn:
        with conn.cursor() as cur:
            # Update only existing companies we already have
            # and only when ticker is missing.
            params = [(t, cik) for cik, t in ticker_map.items()]
            cur.executemany(
                """
                UPDATE companies
                SET ticker = %s
                WHERE issuer_cik = %s
                  AND (ticker IS NULL OR ticker = '')
                """,
                params,
            )
            updated = cur.rowcount or 0

    print(f"Updated tickers in companies: {updated}")
    print(f"Cache file: {CACHE_PATH}")


if __name__ == "__main__":
    main()