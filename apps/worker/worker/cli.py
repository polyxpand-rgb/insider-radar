from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from .ingest import backfill, ingest_day
from .ticker_enrich import enrich_missing_tickers


def _print(obj) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(obj)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worker.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # backfill
    p_backfill = sub.add_parser("backfill", help="Backfill Form 4 filings for the last N days")
    p_backfill.add_argument("--days", type=int, default=2)
    p_backfill.add_argument("--max-filings-per-day", type=int, default=200)

    # ingest-day
    p_day = sub.add_parser("ingest-day", help="Ingest a single YYYY-MM-DD day")
    p_day.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_day.add_argument("--max-filings", type=int, default=200)

    # enrich-tickers
    p_enrich = sub.add_parser("enrich-tickers", help="Fill missing company tickers using SEC CIK↔Ticker map")
    p_enrich.add_argument("--limit", type=int, default=5000, help="Max distinct issuer_cik to consider")
    p_enrich.add_argument("--overwrite", action="store_true", help="Overwrite existing tickers (default: only fill blanks)")
    p_enrich.add_argument("--dry-run", action="store_true", help="Show what would change without updating DB")
    p_enrich.add_argument("--cache-hours", type=int, default=24, help="Reuse downloaded SEC file for N hours")

    args = parser.parse_args(argv)

    if args.cmd == "backfill":
        res = backfill(days=args.days, max_filings_per_day=args.max_filings_per_day)
        _print(res)
        return 0

    if args.cmd == "ingest-day":
        res = ingest_day(day=args.date, max_filings=args.max_filings)
        _print(res)
        return 0

    if args.cmd == "enrich-tickers":
        r = enrich_missing_tickers(
            limit=args.limit,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            cache_hours=args.cache_hours,
        )
        print(f"[enrich-tickers] checked={r.checked} updated={r.updated} unmapped={r.unmapped}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())