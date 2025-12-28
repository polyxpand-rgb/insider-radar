from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import xml.etree.ElementTree as ET

@dataclass(frozen=True)
class ParsedForm4:
    issuer_cik: str
    issuer_name: str
    owner_name: str
    owner_cik: Optional[str]
    transactions: List[dict]

def _strip_ns(root: ET.Element) -> None:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

def _text(node: Optional[ET.Element]) -> str:
    return (node.text or "").strip() if node is not None else ""

def parse_form4_xml(xml_text: str) -> ParsedForm4:
    root = ET.fromstring(xml_text)
    _strip_ns(root)

    issuer_cik = _text(root.find(".//issuer/issuerCik"))
    issuer_name = _text(root.find(".//issuer/issuerName"))

    owner_name = _text(root.find(".//reportingOwner/reportingOwnerId/rptOwnerName"))
    owner_cik = _text(root.find(".//reportingOwner/reportingOwnerId/rptOwnerCik")) or None

    txs: List[dict] = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        security_title = _text(tx.find(".//securityTitle/value"))
        tx_date = _text(tx.find(".//transactionDate/value"))
        code = _text(tx.find(".//transactionCoding/transactionCode"))
        ad = _text(tx.find(".//transactionAmounts/transactionAcquiredDisposedCode/value"))  # A/D
        shares_s = _text(tx.find(".//transactionAmounts/transactionShares/value"))
        price_s = _text(tx.find(".//transactionAmounts/transactionPricePerShare/value"))
        doi = _text(tx.find(".//ownershipNature/directOrIndirectOwnership/value"))  # D/I

        try:
            shares = float(shares_s) if shares_s else None
        except Exception:
            shares = None
        try:
            price = float(price_s) if price_s else None
        except Exception:
            price = None

        total_value = None
        if shares is not None and price is not None:
            total_value = shares * price
            if ad.upper() == "D":
                total_value = -abs(total_value)

        txs.append(
            {
                "transaction_date": tx_date or None,
                "transaction_code": code or None,
                "acq_disp": ad or None,
                "shares": shares,
                "price": price,
                "total_value": total_value,
                "is_direct": (doi.upper() == "D") if doi else None,
                "security_title": security_title or None,
            }
        )

    return ParsedForm4(
        issuer_cik=issuer_cik,
        issuer_name=issuer_name,
        owner_name=owner_name,
        owner_cik=owner_cik,
        transactions=txs,
    )