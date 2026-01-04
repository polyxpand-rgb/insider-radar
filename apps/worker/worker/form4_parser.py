from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple
import xml.etree.ElementTree as ET


# -----------------------------
# Data models returned by parser
# -----------------------------

@dataclass(frozen=True)
class ParsedTxn:
    transaction_date: Optional[date]
    transaction_code: Optional[str]
    shares: Optional[Decimal]
    price: Optional[Decimal]
    total_value: Optional[Decimal]
    security_title: Optional[str]
    is_direct: Optional[bool]


@dataclass(frozen=True)
class ParsedFiling:
    issuer_cik: Optional[str]
    issuer_name: Optional[str]
    ticker: Optional[str]
    owner_name: Optional[str]
    transactions: List[ParsedTxn]


# -----------------------------
# Helpers (namespace-safe)
# -----------------------------

def _strip(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s or None


def _to_date(s: Optional[str]) -> Optional[date]:
    s = _strip(s)
    if not s:
        return None
    # SEC usually uses YYYY-MM-DD
    s = s[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _to_decimal(s: Optional[str]) -> Optional[Decimal]:
    s = _strip(s)
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _tag_endswith(el: ET.Element, suffix: str) -> bool:
    # Handles namespaced tags like "{ns}issuerCik"
    return el.tag.lower().endswith(suffix.lower())


def _find_first_text(root: ET.Element, *tag_suffix_path: str) -> Optional[str]:
    """
    Find nested tags by matching the end of tag names (namespace-safe).
    Example: _find_first_text(root, "issuer", "issuerCik")
    """
    cur = root
    for suf in tag_suffix_path:
        nxt = None
        for ch in cur:
            if _tag_endswith(ch, suf):
                nxt = ch
                break
        if nxt is None:
            return None
        cur = nxt
    return _strip(cur.text)


def _find_all_by_suffix(root: ET.Element, suffix: str) -> List[ET.Element]:
    out: List[ET.Element] = []
    for el in root.iter():
        if _tag_endswith(el, suffix):
            out.append(el)
    return out


def _find_child_by_suffix(parent: ET.Element, suffix: str) -> Optional[ET.Element]:
    for ch in list(parent):
        if _tag_endswith(ch, suffix):
            return ch
    return None


def _find_child_text(parent: ET.Element, suffix: str) -> Optional[str]:
    ch = _find_child_by_suffix(parent, suffix)
    return _strip(ch.text) if ch is not None else None


def _value_of(node: Optional[ET.Element]) -> Optional[str]:
    """
    Many Form 4 fields are like: <transactionDate><value>2025-12-29</value></transactionDate>
    This returns the inner <value> text if present, otherwise node.text.
    """
    if node is None:
        return None
    v = _find_child_by_suffix(node, "value")
    if v is not None and v.text:
        return _strip(v.text)
    return _strip(node.text)


def _extract_owner_name(root: ET.Element) -> Optional[str]:
    # Try the common location: reportingOwner/reportingOwnerId/rptOwnerName/value
    for ro in _find_all_by_suffix(root, "reportingOwner"):
        roi = _find_child_by_suffix(ro, "reportingOwnerId")
        if roi is None:
            continue
        name_node = _find_child_by_suffix(roi, "rptOwnerName")
        if name_node is None:
            continue
        return _value_of(name_node)
    return None


def _parse_direct_flag(tx_root: ET.Element) -> Optional[bool]:
    # directOrIndirectOwnership/value is "D" or "I"
    doi = _find_child_by_suffix(tx_root, "directOrIndirectOwnership")
    if doi is None:
        return None
    v = _value_of(doi)
    if not v:
        return None
    v = v.strip().upper()
    if v == "D":
        return True
    if v == "I":
        return False
    return None


def _parse_one_tx(tx_root: ET.Element) -> ParsedTxn:
    # securityTitle/value
    sec_title = None
    st = _find_child_by_suffix(tx_root, "securityTitle")
    if st is not None:
        sec_title = _value_of(st)

    # transactionDate/value
    tx_date = None
    td = _find_child_by_suffix(tx_root, "transactionDate")
    if td is not None:
        tx_date = _to_date(_value_of(td))

    # transactionCoding/transactionCode/value
    tx_code = None
    coding = _find_child_by_suffix(tx_root, "transactionCoding")
    if coding is not None:
        code_node = _find_child_by_suffix(coding, "transactionCode")
        tx_code = _value_of(code_node) if code_node is not None else None
        tx_code = _strip(tx_code)

    # transactionAmounts/(transactionShares/value, transactionPricePerShare/value)
    shares = None
    price = None
    amounts = _find_child_by_suffix(tx_root, "transactionAmounts")
    if amounts is not None:
        sh_node = _find_child_by_suffix(amounts, "transactionShares")
        if sh_node is not None:
            shares = _to_decimal(_value_of(sh_node))

        pr_node = _find_child_by_suffix(amounts, "transactionPricePerShare")
        if pr_node is not None:
            price = _to_decimal(_value_of(pr_node))

    total_value = None
    if shares is not None and price is not None:
        total_value = shares * price

    is_direct = _parse_direct_flag(tx_root)

    return ParsedTxn(
        transaction_date=tx_date,
        transaction_code=tx_code,
        shares=shares,
        price=price,
        total_value=total_value,
        security_title=sec_title,
        is_direct=is_direct,
    )


def _extract_transactions(root: ET.Element) -> List[ParsedTxn]:
    """
    Pull transactions from:
    - nonDerivativeTable/nonDerivativeTransaction
    - derivativeTable/derivativeTransaction
    """
    out: List[ParsedTxn] = []

    # Non-derivative
    nd_table = None
    for el in root.iter():
        if _tag_endswith(el, "nonDerivativeTable"):
            nd_table = el
            break
    if nd_table is not None:
        for tx in list(nd_table):
            if _tag_endswith(tx, "nonDerivativeTransaction"):
                out.append(_parse_one_tx(tx))

    # Derivative
    d_table = None
    for el in root.iter():
        if _tag_endswith(el, "derivativeTable"):
            d_table = el
            break
    if d_table is not None:
        for tx in list(d_table):
            if _tag_endswith(tx, "derivativeTransaction"):
                out.append(_parse_one_tx(tx))

    return out


# -----------------------------
# Public API used by ingest.py
# -----------------------------

def parse_form4_xml(xml_text: str) -> ParsedFiling:
    """
    Parse Form 4 XML (<ownershipDocument>) into a ParsedFiling.
    This function name MUST exist because ingest.py imports it.
    """
    # Some SEC XML begins with BOM or whitespace
    xml_text = xml_text.lstrip("\ufeff").strip()

    root = ET.fromstring(xml_text)

    issuer_cik = _find_first_text(root, "issuer", "issuerCik")
    issuer_name = _find_first_text(root, "issuer", "issuerName")
    ticker = _find_first_text(root, "issuer", "issuerTradingSymbol")

    owner_name = _extract_owner_name(root)

    txs = _extract_transactions(root)

    return ParsedFiling(
        issuer_cik=_strip(issuer_cik),
        issuer_name=_strip(issuer_name),
        ticker=_strip(ticker),
        owner_name=_strip(owner_name),
        transactions=txs,
    )