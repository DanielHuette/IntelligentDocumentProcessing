"""Turn raw model answers into typed decisions and extracted fields.

Context: Boundary between untrusted model output and the confidence gate. |
Input: JSON payloads. |
Output: Classification and Extraction.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from idp.domain import UNKNOWN_VENDOR, Classification, DocumentType, Extraction
from idp.errors import ResponseFormatError
from idp.vendors import VENDORS_BY_KEY

_NUMBER = re.compile(r"-?[\d.,]+")
VALID_TYPES = frozenset(t.value for t in DocumentType)


def parse_amount(value: Any) -> Decimal | None:
    """Read a number written as JSON number or as German or English text.

    Args:
        value: 1234.5, "1.234,50 €", "EUR 1,234.50" or None.

    Returns:
        Decimal rounded to cents, or None when no number is present.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    match = _NUMBER.search(str(value))
    if match is None:
        return None
    text = match.group()
    if "," in text and "." in text:
        text = (
            text.replace(".", "").replace(",", ".")
            if text.rfind(",") > text.rfind(".")
            else text.replace(",", "")
        )
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(number, 0.0), 1.0)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extraction_from_payload(payload: dict[str, Any]) -> Extraction:
    """Build an Extraction from a model answer; unknown keys are ignored."""
    notes = payload.get("notes") or []
    return Extraction(
        vendor_name=_text(payload.get("vendor_name")),
        invoice_number=_text(payload.get("invoice_number")),
        invoice_date=_text(payload.get("invoice_date")),
        net=parse_amount(payload.get("net")),
        tax_rate=parse_amount(payload.get("tax_rate")),
        tax=parse_amount(payload.get("tax")),
        gross=parse_amount(payload.get("gross")),
        summary=_text(payload.get("summary")) or "",
        notes=tuple(str(note) for note in notes) if isinstance(notes, list) else (str(notes),),
    )


def classification_from_payload(payload: dict[str, Any]) -> Classification:
    """Build a Classification from a single model's JSON answer.

    Raises:
        ResponseFormatError: If the document type is missing.
    """
    document_type = str(payload.get("document_type", "")).strip()
    if not document_type:
        raise ResponseFormatError("answer has no document_type")
    vendor_key = str(payload.get("vendor_key", UNKNOWN_VENDOR)).strip()
    if vendor_key not in VENDORS_BY_KEY:
        vendor_key = UNKNOWN_VENDOR
    return Classification(
        document_type=document_type if document_type in VALID_TYPES else "unrecognized",
        document_type_confidence=_probability(payload.get("document_type_confidence")),
        vendor_key=vendor_key,
        vendor_confidence=_probability(payload.get("vendor_confidence")),
        formally_complete_probability=_probability(payload.get("formally_complete_probability")),
    )


def classification_from_jev(answers: dict[str, Any]) -> Classification:
    """Build a Classification from Jev's typed answers.

    Raises:
        ResponseFormatError: If an expected answer is missing.
    """
    try:
        document_type = answers["document_type"]
        vendor = answers["vendor"]
        complete = answers["formally_complete"]
    except KeyError as error:
        raise ResponseFormatError(f"Jev answer misses {error}") from error
    return Classification(
        document_type=str(document_type.get("choice", "")),
        document_type_confidence=_probability(document_type.get("confidence")),
        vendor_key=str(vendor.get("choice", UNKNOWN_VENDOR)),
        vendor_confidence=_probability(vendor.get("confidence")),
        formally_complete_probability=_probability(complete.get("noul")),
    )
