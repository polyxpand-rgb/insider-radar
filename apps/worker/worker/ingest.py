from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import psycopg
import psycopg.rows
import requests

from .config import DATABASE_URL
from .daily_index import fetch_form4_refs_for_date, iter_dates_back
from .form4_parser import parse_form4_xml  # your form4_parser.py MUST expose parse_form4_xml(...)
from .sec_client import fetch_form4_xml, make_session


def _connect():
    return psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)


def _to_text(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    s = str(v).strip()
    if not s:
        return None
    # accept "YYYY-MM-DD" or full timestamp
    s = s[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _tx_get(tx: Any, key: str) -> Any:
    """
    Supports both dict-like tx and dataclass/object tx.
    """
    if tx is None:
        return None
    if isinstance(tx, dict):
        return tx.get(key)
    return getattr(tx, key, None)


def upsert_company(cur, issuer_cik: str, name: str, ticker: Optional[str]) -> None:
    """
    Fixes the Postgres error:
      "could not determine data type of parameter $2"
    by avoiding `CASE WHEN %s IS NULL ...` (type-less param).
    """
    issuer_cik = str(issuer_cik).strip()
    name = str(name).strip()
    ticker = (ticker or "").strip() or None

    # Update all existing rows for this CIK (your web query uses DISTINCT ON)
    cur.execute(
        """
        update companies
           set name   = %s::text,
               ticker = coalesce(nullif(%s::text, ''), ticker)
         where issuer_cik = %s::text
        """,
        (name, ticker or "", issuer_cik),
    )

    # Insert a row if missing
    cur.execute(
        """
        insert into companies (issuer_cik, name, ticker)
        select %s::text, %s::text, nullif(%s::text,'')
        where not exists (select 1 from companies where issuer_cik = %s::text)
        """,
        (issuer_cik, name, ticker or "", issuer_cik),
    )


def insert_transaction(cur, issuer_cik: str, accession: str, owner_name: Optional[str], tx: Any) -> bool:
    """
    Idempotent insert using your existing UNIQUE constraint:
    (accession_number, transaction_date, transaction_code, shares, price, security_title)

    Returns True if inserted, False if skipped.
    """
    issuer_cik = str(issuer_cik).strip()
    accession = str(accession).strip()

    owner_name = (owner_name or "").strip() or "UNKNOWN"

    transaction_date = _to_date(_tx_get(tx, "transaction_date"))
    transaction_code = _to_text(_tx_get(tx, "transaction_code"))
    shares = _to_decimal(_tx_get(tx, "shares"))
    price = _to_decimal(_tx_get(tx, "price"))
    total_value = _to_decimal(_tx_get(tx, "total_value"))
    security_title = _to_text(_tx_get(tx, "security_title"))
    is_direct = _tx_get(tx, "is_direct")

    # Normalize is_direct to bool/None
    if isinstance(is_direct, str):
        is_direct = is_direct.strip().lower()
        if is_direct in ("1", "true", "t", "yes", "y"):
            is_direct = True
        elif is_direct in ("0", "false", "f", "no", "n"):
            is_direct = False
        else:
            is_direct = None

    # If total_value missing but shares & price exist, compute it
    if total_value is None and shares is not None and price is not None:
        total_value = shares * price

    # Required fields for uniqueness + sanity
    if transaction_date is None or not transaction_code or security_title is None:
        return False

    cur.execute(
        """
        insert into transactions (
          issuer_cik,
          accession_number,
          owner_name,
          transaction_date,
          transaction_code,
          shares,
          price,
          total_value,
          is_direct,
          security_title
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (accession_number, transaction_date, transaction_code, shares, price, security_title)
        do nothing
        """,
        (
            issuer_cik,
            accession,
            owner_name,
            transaction_date,
            transaction_code,
            shares,
            price,
            total_value,
            is_direct,
            security_title,
        ),
    )
    return cur.rowcount == 1


def ingest_day(d: date, max_filings: int = 200) -> dict:
    """
    Ingest all Form 4 filings for one day from the SEC daily index.
    """
    session = make_session()

    try:
        refs = fetch_form4_refs_for_date(session, user_agent=session.headers["User-Agent"], d=d)
    except requests.HTTPError as e:
        # You already handle the 403 in daily_index, but keep this as a safety net.
        print(f"[daily-index] {e}")
        refs = []

    refs = refs[:max_filings]

    stats = {
        "date": str(d),
        "refs_found": len(refs),
        "filings_ok": 0,
        "filings_failed": 0,
        "transactions_inserted": 0,
        "transactions_skipped": 0,
    }

    with _connect() as conn:
        with conn.cursor() as cur:
            for ref in refs:
                try:
                    # robust XML extraction; pass cik+accession for index.json fallback
                    xml = fetch_form4_xml(session, ref.url, cik=ref.cik, accession=ref.accession_number)
                    parsed = parse_form4_xml(xml)

                    issuer_cik = getattr(parsed, "issuer_cik", None) or ref.cik
                    issuer_name = getattr(parsed, "issuer_name", None) or ref.company_name
                    ticker = getattr(parsed, "ticker", None)
                    owner_name = getattr(parsed, "owner_name", None)

                    upsert_company(cur, issuer_cik, issuer_name, ticker)

                    inserted = 0
                    skipped = 0

                    txs = getattr(parsed, "transactions", None) or []
                    for tx in txs:
                        did = insert_transaction(cur, issuer_cik, ref.accession_number, owner_name, tx)
                        if did:
                            inserted += 1
                        else:
                            skipped += 1

                    conn.commit()

                    stats["filings_ok"] += 1
                    stats["transactions_inserted"] += inserted
                    stats["transactions_skipped"] += skipped

                except Exception as e:
                    conn.rollback()
                    stats["filings_failed"] += 1
                    print(f"[WARN] {ref.accession_number} failed: {e}")

    return stats


def backfill(days: int = 10, max_filings_per_day: int = 200) -> None:
    dates = iter_dates_back(days)
    for d in dates:
        s = ingest_day(d, max_filings=max_filings_per_day)
        print("[OK]", s)