"""Deterministic checks and the confidence gate.

Context: Decides between automatic approval and human review; the n8n Code node runs the same
rules. |
Input: Classification, extraction, already booked invoice keys. |
Output: GateResult with reasons.
"""

from __future__ import annotations

from collections.abc import Collection
from decimal import Decimal

from idp.domain import UNKNOWN_VENDOR, Classification, DocumentType, Extraction, GateResult, Route

CONFIDENCE_THRESHOLD = 0.85
ALLOWED_TAX_RATES: frozenset[Decimal] = frozenset({Decimal("0.19"), Decimal("0.07")})
SUM_TOLERANCE = Decimal("0.01")
TAX_TOLERANCE = Decimal("0.02")


def normalize_tax_rate(rate: Decimal) -> Decimal:
    """Return the rate as a fraction, accepting both 19 and 0.19.

    Args:
        rate: Tax rate as percent or fraction.

    Returns:
        Rate as fraction with two decimals.
    """
    fraction = rate / 100 if rate > 1 else rate
    return fraction.quantize(Decimal("0.01"))


def arithmetic_problems(extraction: Extraction) -> list[str]:
    """Check that the printed totals are complete and add up.

    Args:
        extraction: Fields read from the document.

    Returns:
        Human-readable problems; empty when the totals are consistent.
    """
    net, rate, tax, gross = extraction.net, extraction.tax_rate, extraction.tax, extraction.gross
    if net is None or rate is None or tax is None or gross is None:
        return ["totals incomplete: net, tax rate, tax and gross are required"]
    problems: list[str] = []
    fraction = normalize_tax_rate(rate)
    if fraction not in ALLOWED_TAX_RATES:
        problems.append(f"tax rate {fraction * 100:.0f} % is not a German VAT rate")
    if abs(net + tax - gross) > SUM_TOLERANCE:
        problems.append(f"net {net} + tax {tax} != gross {gross}")
    if abs(net * fraction - tax) > TAX_TOLERANCE:
        problems.append(f"tax {tax} does not match {fraction * 100:.0f} % of net {net}")
    return problems


def duplicate_key(vendor_key: str, invoice_number: str | None) -> str | None:
    """Build the key that identifies an invoice across submissions.

    Args:
        vendor_key: Supplier key from master data.
        invoice_number: Invoice number as printed.

    Returns:
        Normalized key, or None when there is no invoice number.
    """
    if not invoice_number:
        return None
    return f"{vendor_key}|{''.join(invoice_number.split()).upper()}"


def gate(
    classification: Classification,
    extraction: Extraction,
    booked_keys: Collection[str],
    threshold: float = CONFIDENCE_THRESHOLD,
) -> GateResult:
    """Approve only when every decision is confident and every check passes.

    Args:
        classification: Typed decisions with confidences.
        extraction: Fields read from the document.
        booked_keys: Duplicate keys of invoices that are already stored.
        threshold: Minimum confidence for each decision.

    Returns:
        APPROVED without reasons, or NEEDS_REVIEW with every reason that applies.
    """
    if classification.document_type != DocumentType.INVOICE:
        return GateResult(
            Route.NEEDS_REVIEW, (f"document type is {classification.document_type}, not invoice",)
        )
    reasons: list[str] = []
    if classification.document_type_confidence < threshold:
        reasons.append(f"document type confidence {classification.document_type_confidence:.2f}")
    if classification.vendor_key == UNKNOWN_VENDOR:
        reasons.append("vendor is not in master data")
    elif classification.vendor_confidence < threshold:
        reasons.append(f"vendor confidence {classification.vendor_confidence:.2f}")
    if classification.formally_complete_probability < threshold:
        reasons.append(
            "mandatory invoice fields incomplete "
            f"(probability {classification.formally_complete_probability:.2f})"
        )
    if not extraction.invoice_number:
        reasons.append("invoice number missing")
    reasons.extend(arithmetic_problems(extraction))
    key = duplicate_key(classification.vendor_key, extraction.invoice_number)
    if key is not None and key in booked_keys:
        reasons.append("invoice already booked")
    if reasons:
        return GateResult(Route.NEEDS_REVIEW, tuple(reasons))
    return GateResult(Route.APPROVED)
