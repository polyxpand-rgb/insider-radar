from __future__ import annotations

import json
import re
import time
from typing import Optional

import requests

from .config import SEC_USER_AGENT


SEC_ARCHIVES = "https://www.sec.gov/Archives"


def make_session() -> requests.Session:
    """
    Create a requests session that plays nicely with SEC.
    """
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": SEC_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    return s


def _rate_limit_sleep(min_interval_sec: float = 0.12) -> None:
    # Simple global sleep; good enough for now.
    time.sleep(min_interval_sec)


def fetch_filing_txt(session: requests.Session, url: str, timeout: int = 30) -> str:
    _rate_limit_sleep()
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def _extract_ownership_document_xml(filing_txt: str) -> Optional[str]:
    """
    Most Form 4 submissions contain an embedded XML with root <ownershipDocument>.
    We extract the first such block.
    """
    # Common case: XML is present plainly
    m = re.search(r"<ownershipDocument\b.*?</ownershipDocument>", filing_txt, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0)

    # Sometimes embedded inside <XML> ... </XML>
    m = re.search(r"<XML>\s*(<ownershipDocument\b.*?</ownershipDocument>)\s*</XML>", filing_txt, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)

    # Sometimes the doc starts at <?xml ...> and includes ownershipDocument
    m = re.search(r"(<\?xml\b.*?<ownershipDocument\b.*?</ownershipDocument>)", filing_txt, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _accession_nodash(accession: str) -> str:
    return accession.replace("-", "").strip()


def _index_json_url(cik: str, accession: str) -> str:
    # https://www.sec.gov/Archives/edgar/data/{cik}/{accessionNoDash}/index.json
    return f"{SEC_ARCHIVES}/edgar/data/{cik.strip()}/{_accession_nodash(accession)}/index.json"


def _try_fetch_xml_via_index_json(session: requests.Session, cik: str, accession: str) -> Optional[str]:
    """
    Fallback approach:
    fetch index.json from the accession folder and grab the first .xml file that looks like ownershipDocument.
    """
    url = _index_json_url(cik, accession)
    _rate_limit_sleep()
    r = session.get(url, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()

    try:
        payload = r.json()
    except json.JSONDecodeError:
        return None

    items = payload.get("directory", {}).get("item", [])
    # Prefer .xml files
    xml_names = [it.get("name") for it in items if isinstance(it, dict) and str(it.get("name", "")).lower().endswith(".xml")]
    if not xml_names:
        return None

    base = f"{SEC_ARCHIVES}/edgar/data/{cik.strip()}/{_accession_nodash(accession)}"
    for name in xml_names:
        if not name:
            continue
        xml_url = f"{base}/{name}"
        _rate_limit_sleep()
        rx = session.get(xml_url, timeout=30)
        if rx.status_code == 404:
            continue
        rx.raise_for_status()
        txt = rx.text
        if "<ownershipDocument" in txt:
            return txt

    return None


def fetch_form4_xml(session: requests.Session, filing_txt_url: str, cik: Optional[str] = None, accession: Optional[str] = None) -> str:
    """
    Fetch the filing .txt and extract the Form 4 XML (<ownershipDocument>).

    If not found in the .txt, optionally fallback to index.json (needs cik + accession).
    """
    filing_txt = fetch_filing_txt(session, filing_txt_url)

    xml = _extract_ownership_document_xml(filing_txt)
    if xml:
        return xml

    if cik and accession:
        xml2 = _try_fetch_xml_via_index_json(session, cik, accession)
        if xml2:
            return xml2

    raise ValueError("No Form 4 XML (<ownershipDocument>) found in filing txt")