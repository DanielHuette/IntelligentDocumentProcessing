"""Tests for the arithmetic checks and the confidence gate."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from idp.domain import Classification, Extraction, Route
from idp.rules import arithmetic_problems, duplicate_key, gate, normalize_tax_rate


@pytest.mark.parametrize(("raw", "expected"), [("19", "0.19"), ("0.07", "0.07"), ("7", "0.07")])
def test_normalize_tax_rate_accepts_percent_and_fraction(raw: str, expected: str) -> None:
    assert normalize_tax_rate(Decimal(raw)) == Decimal(expected)


def test_consistent_totals_have_no_problems(clean_extraction: Extraction) -> None:
    assert arithmetic_problems(clean_extraction) == []


def test_sum_mismatch_is_reported(clean_extraction: Extraction) -> None:
    broken = replace(clean_extraction, gross=Decimal("190.06"))
    assert any("!= gross" in p for p in arithmetic_problems(broken))


def test_foreign_tax_rate_is_reported(clean_extraction: Extraction) -> None:
    wrong = replace(
        clean_extraction, tax_rate=Decimal("16"), tax=Decimal("24.34"), gross=Decimal("176.49")
    )
    problems = arithmetic_problems(wrong)
    assert any("not a German VAT rate" in p for p in problems)


def test_missing_totals_are_reported(clean_extraction: Extraction) -> None:
    assert arithmetic_problems(replace(clean_extraction, tax=None)) == [
        "totals incomplete: net, tax rate, tax and gross are required"
    ]


def test_duplicate_key_ignores_spaces_and_case() -> None:
    assert duplicate_key("aws", "euinde26 44") == duplicate_key(
        "aws", "EUINDE26-44".replace("-", "")
    )
    assert duplicate_key("aws", None) is None


def test_gate_approves_clean_confident_invoice(
    confident_invoice: Classification, clean_extraction: Extraction
) -> None:
    result = gate(confident_invoice, clean_extraction, set())
    assert result.route == Route.APPROVED
    assert result.reasons == ()


def test_gate_sends_other_documents_to_review(clean_extraction: Extraction) -> None:
    quote = Classification("quote", 0.99, "telekom", 0.99, 0.1)
    result = gate(quote, clean_extraction, set())
    assert result.route == Route.NEEDS_REVIEW
    assert result.reasons == ("document type is quote, not invoice",)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"document_type_confidence": 0.6}, "document type confidence"),
        ({"vendor_key": "unknown"}, "vendor is not in master data"),
        ({"vendor_confidence": 0.5}, "vendor confidence"),
        ({"formally_complete_probability": 0.3}, "mandatory invoice fields incomplete"),
    ],
)
def test_gate_requires_every_confidence(
    confident_invoice: Classification,
    clean_extraction: Extraction,
    change: dict[str, object],
    reason: str,
) -> None:
    result = gate(replace(confident_invoice, **change), clean_extraction, set())
    assert result.route == Route.NEEDS_REVIEW
    assert any(reason in r for r in result.reasons)


def test_gate_catches_missing_number_and_duplicates(
    confident_invoice: Classification, clean_extraction: Extraction
) -> None:
    assert (
        "invoice number missing"
        in gate(confident_invoice, replace(clean_extraction, invoice_number=None), set()).reasons
    )
    booked = {duplicate_key("telekom", "412 7781 30519") or ""}
    assert "invoice already booked" in gate(confident_invoice, clean_extraction, booked).reasons
