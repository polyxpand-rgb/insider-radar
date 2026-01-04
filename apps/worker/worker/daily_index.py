from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import requests


@dataclass(frozen=True)
class FilingRef:
    cik: str
    company_name: str
    form_type: str
    date_filed: str
    file_name: str  # "edgar/data/.../0001234567-25-000001.txt"
    accession_number: str  # "0001234567-25-000001"
    url: str  # full URL to the .txt in Archives


def _quarter_for(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _master_idx_url(d: date) -> str:
    q = _quarter_for(d)
    return f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/master.{d:%Y%m%d}.idx"


def iter_dates_back(days: int, end: date | None = None) -> List[date]:
    end = end or date.today()
    return [end - timedelta(days=i) for i in range(days)]


def fetch_form4_refs_for_date(
    session: requests.Session,
    user_agent: str,
    d: date,
) -> List[FilingRef]:
    url = _master_idx_url(d)

    # Use session headers; but keep UA override explicit
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/plain,*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }

    r = session.get(url, headers=headers, timeout=30)

    # The file may not exist yet for "today" — SEC sometimes returns 403 instead of 404
    if r.status_code == 404:
        return []
    if r.status_code == 403:
        print(f"[daily-index] 403 for {url} (skipping)")
        return []

    r.raise_for_status()
    text = r.text
    lines = text.splitlines()

    # Find header line then parse after it
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("CIK|Company Name|Form Type|Date Filed|File Name"):
            start = i + 1
            break
    if start is None:
        return []

    out: List[FilingRef] = []
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != 5:
            continue

        cik, cname, form, date_filed, file_name = [p.strip() for p in parts]
        form_u = form.upper()

        # include 4 and 4/A
        if not (form_u == "4" or form_u == "4/A" or form_u.startswith("4 ")):
            continue

        # file_name example: edgar/data/1162870/0001193125-25-310142.txt
        accession = file_name.split("/")[-1].replace(".txt", "")
        full_url = "https://www.sec.gov/Archives/" + file_name

        out.append(
            FilingRef(
                cik=cik,
                company_name=cname,
                form_type=form,
                date_filed=date_filed,
                file_name=file_name,
                accession_number=accession,
                url=full_url,
            )
        )

    return out