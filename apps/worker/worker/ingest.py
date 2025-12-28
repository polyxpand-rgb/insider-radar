from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

import psycopg

from .daily_index import IndexRow
from .form4_parser import parse_form4_xml
from .sec_client import SecClient

def accession_from_filename(filename: str) -> str:
    base = filename.split("/")[-1]
    return base.replace(".txt", "").replace(".hdr.sgml", "")

def accession_nodash(accession: str) -> str:
    return accession.replace("-", "")

def filing_index_json_url(cik: str, accession: str) -> str:
    cik_int = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash(accession)}/index.json"

def pick_xml_from_index(index_json: dict) -> Optional[str]:
    try:
        items = index_json["directory"]["item"]
    except Exception:
        return None
    # Prefer files that look like the primary Form 4 XML
    preferred = []
    for it in items:
        name = (it.get("name") or "").lower()
        if name.endswith(".xml"):
            preferred.append(it.get("name"))
    if not preferred:
        return None
    # Heuristic: prefer something with "form4" or "primary" if present
    for n in preferred:
        nl = n.lower()
        if "form4" in nl or "primary" in nl:
            return n
    return preferred[0]

def primary_xml_url(cik: str, accession: str, xml_name: str) -> str:
    cik_int = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash(accession)}/{xml_name}"

def upsert_company(conn, cik: str, name: str) -> None:
    conn.execute(
        """
        INSERT INTO companies (issuer_cik, name)
        VALUES (%s, %s)
        ON CONFLICT (issuer_cik) DO UPDATE SET name = EXCLUDED.name
        """,
        (cik, name),
    )

def upsert_insider(conn, owner_cik: Optional[str], name: str) -> None:
    conn.execute(
        """
        INSERT INTO insiders (owner_cik, name)
        VALUES (%s, %s)
        ON CONFLICT (owner_cik, name) DO NOTHING
        """,
        (owner_cik, name),
    )

def upsert_filing(conn, row: IndexRow, accession: str, sec_url: str, primary_doc: Optional[str]) -> None:
    filed_at = datetime(row.date_filed.year, row.date_filed.month, row.date_filed.day)
    conn.execute(
        """
        INSERT INTO form4_filings (accession_number, issuer_cik, filed_at, primary_doc, sec_url)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (accession_number) DO UPDATE
        SET issuer_cik = EXCLUDED.issuer_cik,
            filed_at = COALESCE(form4_filings.filed_at, EXCLUDED.filed_at),
            primary_doc = COALESCE(EXCLUDED.primary_doc, form4_filings.primary_doc),
            sec_url = COALESCE(EXCLUDED.sec_url, form4_filings.sec_url)
        """,
        (accession, row.cik, filed_at, primary_doc, sec_url),
    )

def insert_transaction(conn, accession: str, issuer_cik: str, owner_name: str, tx: dict) -> None:
    tx_date = tx.get("transaction_date") or ""
    conn.execute(
        """
        INSERT INTO transactions (
          accession_number, issuer_cik, owner_name,
          transaction_date, transaction_code,
          shares, price, total_value,
          is_direct, security_title
        )
        VALUES (
          %s, %s, %s,
          NULLIF(%s,'')::date, %s,
          %s, %s, %s,
          %s, %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            accession, issuer_cik, owner_name,
            tx_date,
            tx.get("transaction_code"),
            tx.get("shares"),
            tx.get("price"),
            tx.get("total_value"),
            tx.get("is_direct"),
            tx.get("security_title"),
        ),
    )

def ingest_index_row(conn, client: SecClient, row: IndexRow) -> Tuple[str, int]:
    accession = accession_from_filename(row.filename)
    filing_txt_url = f"https://www.sec.gov/Archives/{row.filename}"

    idx_url = filing_index_json_url(row.cik, accession)
    idx_json = client.get_json(idx_url)
    xml_name = pick_xml_from_index(idx_json)

    # Always upsert base company + filing row
    upsert_company(conn, row.cik, row.company_name)
    upsert_filing(conn, row, accession, filing_txt_url, xml_name)

    if not xml_name:
        return accession, 0

    xml_url = primary_xml_url(row.cik, accession, xml_name)
    xml_text = client.get_text(xml_url)
    parsed = parse_form4_xml(xml_text)

    upsert_insider(conn, parsed.owner_cik, parsed.owner_name)

    n = 0
    for tx in parsed.transactions:
        insert_transaction(conn, accession, row.cik, parsed.owner_name, tx)
        n += 1

    return accession, n