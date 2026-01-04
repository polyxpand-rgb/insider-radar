"""
Ticker enrichment for companies table.

Goal:
- Fill missing companies.ticker using the SEC's official CIK↔Ticker file.
- Idempotent: safe to run repeatedly.
- Cached download (so we don't hammer SEC).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests


SEC_DEFAULT_TICKER_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if (v is not None and v.strip() != "") else default


def _sec_user_agent() -> str:
    # IMPORTANT: SEC expects a real UA with contact info.
    # You already use this for daily-index; reuse same env var.
    return _env("SEC_USER_AGENT", "InsiderRadar/0.1 (contact: you@example.com)") or ""


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _sec_user_agent(),
            "Accept": "application/json,text/plain,*/*",
        }
    )
    return s


def _cache_path() -> Path:
    # apps/worker/.cache/company_tickers_exchange.json
    here = Path(__file__).resolve()
    worker_root = here.parents[1]  # .../apps/worker
    p = worker_root / ".cache"
    p.mkdir(parents=True, exist_ok=True)
    return p / "company_tickers_exchange.json"


def _is_cache_fresh(path: Path, max_age_hours: int) -> bool:
    if not path.exists():
        return False
    age_sec = time.time() - path.stat().st_mtime
    return age_sec < max_age_hours * 3600


def _download_ticker_file(url: str, dest: Path, max_age_hours: int = 24) -> Path:
    if _is_cache_fresh(dest, max_age_hours):
        return dest

    session = _make_session()
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"SEC ticker download failed: HTTP {r.status_code} from {url}")

    dest.write_bytes(r.content)
    return dest


def _exchange_priority(exchange: Optional[str]) -> int:
    # Prefer big exchanges first if SEC file has multiple tickers per CIK.
    ex = (exchange or "").strip().lower()
    if ex == "nyse":
        return 0
    if ex == "nasdaq":
        return 1
    if ex in {"nyse american", "amex", "nyse mkt"}:
        return 2
    if ex == "otc":
        return 3
    if ex == "":
        return 9
    return 5


def load_cik_to_ticker_map(
    url: Optional[str] = None,
    cache_hours: int = 24,
) -> Dict[int, Tuple[str, Optional[str], Optional[str]]]:
    """
    Returns:
      { cik_int: (ticker, company_name, exchange) }

    Reads SEC JSON:
      {"fields":["cik","name","ticker","exchange"],"data":[[1045810,"NVIDIA CORP","NVDA","Nasdaq"], ...]}
    """
    src_url = url or _env("SEC_TICKER_URL", SEC_DEFAULT_TICKER_URL) or SEC_DEFAULT_TICKER_URL
    path = _download_ticker_file(src_url, _cache_path(), max_age_hours=cache_hours)

    obj = json.loads(path.read_text(encoding="utf-8"))

    fields = obj.get("fields", [])
    data = obj.get("data", [])
    if not isinstance(fields, list) or not isinstance(data, list):
        raise RuntimeError("Unexpected SEC ticker JSON format (fields/data).")

    # Find positions (defensive)
    try:
        i_cik = fields.index("cik")
        i_name = fields.index("name")
        i_ticker = fields.index("ticker")
        i_ex = fields.index("exchange")
    except ValueError:
        raise RuntimeError(f"Unexpected SEC ticker JSON fields: {fields}")

    candidates: Dict[int, List[Tuple[str, str, Optional[str]]]] = {}
    for row in data:
        if not isinstance(row, list) or len(row) <= max(i_cik, i_name, i_ticker, i_ex):
            continue

        cik = row[i_cik]
        name = row[i_name]
        ticker = row[i_ticker]
        exch = row[i_ex]

        if cik is None or ticker is None:
            continue

        try:
            cik_int = int(cik)
        except Exception:
            continue

        t = str(ticker).strip()
        if not t:
            continue

        n = str(name).strip() if name is not None else ""
        e = str(exch).strip() if exch is not None else ""

        candidates.setdefault(cik_int, []).append((t, n, e))

    # Pick best per CIK by exchange priority (then stable by ticker)
    out: Dict[int, Tuple[str, Optional[str], Optional[str]]] = {}
    for cik_int, rows in candidates.items():
        rows.sort(key=lambda x: (_exchange_priority(x[2]), x[0]))
        best_t, best_n, best_e = rows[0]
        out[cik_int] = (best_t, best_n or None, best_e or None)

    return out


def _get_db_url() -> str:
    db_url = _env("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set.")
    return db_url


def _connect():
    """
    Supports psycopg2 (preferred) and psycopg (v3).
    """
    db_url = _get_db_url()
    try:
        import psycopg2  # type: ignore

        return psycopg2.connect(db_url)
    except Exception:
        import psycopg  # type: ignore

        return psycopg.connect(db_url)


@dataclass
class EnrichResult:
    checked: int
    updated: int
    unmapped: int


def enrich_missing_tickers(
    *,
    limit: int = 5000,
    overwrite: bool = False,
    dry_run: bool = False,
    cache_hours: int = 24,
) -> EnrichResult:
    """
    Fills companies.ticker where missing/blank (or overwrites if overwrite=True).

    - limit: max distinct issuer_cik to consider in one run
    - overwrite: if True, replace existing tickers too (default False)
    - dry_run: print what would happen without updating
    """
    cik_map = load_cik_to_ticker_map(cache_hours=cache_hours)

    conn = _connect()
    try:
        conn.autocommit = False
        cur = conn.cursor()

        if overwrite:
            sel_sql = """
                select issuer_cik, max(name) as name
                from companies
                group by issuer_cik
                order by issuer_cik
                limit %s;
            """
            cur.execute(sel_sql, (limit,))
        else:
            sel_sql = """
                select issuer_cik, max(name) as name
                from companies
                where ticker is null or btrim(ticker) = ''
                group by issuer_cik
                order by issuer_cik
                limit %s;
            """
            cur.execute(sel_sql, (limit,))

        rows = cur.fetchall()

        update_params: List[Tuple[str, str, Optional[str]]] = []
        unmapped = 0

        for issuer_cik, _name in rows:
            if issuer_cik is None:
                continue
            cik_raw = str(issuer_cik).strip()
            if not cik_raw:
                continue
            try:
                cik_int = int(cik_raw.lstrip("0") or "0")
            except Exception:
                unmapped += 1
                continue

            mapped = cik_map.get(cik_int)
            if not mapped:
                unmapped += 1
                continue

            ticker, sec_name, _ex = mapped
            update_params.append((ticker, cik_raw, sec_name))

        if dry_run:
            print(f"[dry-run] Would check {len(rows)} issuer_cik; would update {len(update_params)}; unmapped {unmapped}")
            for (tkr, cik_raw, sec_name) in update_params[:25]:
                print(f"  issuer_cik={cik_raw} -> ticker={tkr} name={sec_name or ''}")
            conn.rollback()
            return EnrichResult(checked=len(rows), updated=0, unmapped=unmapped)

        if overwrite:
            upd_sql = """
                update companies
                set
                  ticker = %s,
                  name = case
                    when name is null or btrim(name) = '' then coalesce(%s, name)
                    else name
                  end
                where issuer_cik = %s;
            """
            # order params accordingly
            exec_params = [(tkr, sec_name, cik_raw) for (tkr, cik_raw, sec_name) in update_params]
        else:
            upd_sql = """
                update companies
                set
                  ticker = %s,
                  name = case
                    when name is null or btrim(name) = '' then coalesce(%s, name)
                    else name
                  end
                where issuer_cik = %s
                  and (ticker is null or btrim(ticker) = '');
            """
            exec_params = [(tkr, sec_name, cik_raw) for (tkr, cik_raw, sec_name) in update_params]

        # Batch update
        updated = 0
        for (tkr, sec_name, cik_raw) in exec_params:
            cur.execute(upd_sql, (tkr, sec_name, cik_raw))
            updated += cur.rowcount

        conn.commit()
        return EnrichResult(checked=len(rows), updated=updated, unmapped=unmapped)

    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass