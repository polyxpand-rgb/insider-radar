from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from .sec_client import SecClient

@dataclass(frozen=True)
class IndexRow:
    cik: str
    company_name: str
    form_type: str
    date_filed: date
    filename: str

def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1

def daily_master_index_url(d: date) -> str:
    y = d.year
    q = _quarter(d)
    ymd = d.strftime("%Y%m%d")
    return f"https://www.sec.gov/Archives/edgar/daily-index/{y}/QTR{q}/master.{ymd}.idx"

def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    # YYYY-MM-DD
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            y, m, d = s.split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return None
    # YYYYMMDD
    if len(s) == 8 and s.isdigit():
        try:
            return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        except Exception:
            return None
    return None

def parse_master_idx(text: str) -> List[IndexRow]:
    out: List[IndexRow] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # skip non-data lines
        if line.startswith("Description:") or line.startswith("Last Data Received:"):
            continue
        if line.startswith("CIK|") or set(line) == {"-"}:
            continue
        if "|" not in line:
            continue

        parts = line.split("|")

        # remove trailing empty parts (if line ends with |)
        while parts and parts[-1].strip() == "":
            parts.pop()

        if len(parts) < 5:
            continue

        # robust parse from right
        filename = parts[-1].strip()
        filed_str = parts[-2].strip()
        form_type = parts[-3].strip()
        cik = parts[0].strip()
        company = "|".join(parts[1:-3]).strip()

        if form_type not in ("4", "4/A"):
            continue
        if not cik.isdigit():
            continue

        filed_date = _parse_date(filed_str)
        if not filed_date:
            continue

        out.append(IndexRow(cik=cik, company_name=company, form_type=form_type, date_filed=filed_date, filename=filename))

    return out

def fetch_form4_rows(client: SecClient, d: date) -> List[IndexRow]:
    url = daily_master_index_url(d)
    text = client.get_text(url)
    return parse_master_idx(text)