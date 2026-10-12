"""Tests for turning model answers into typed records."""

from __future__ import annotations

from decimal import Decimal

import pytest

from idp.errors import ResponseFormatError
from idp.parsing import (
    classification_from_jev,
    classification_from_payload,
    extraction_from_payload,
    parse_amount,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1234.5, Decimal("1234.50")),
        ("1.234,56 €", Decimal("1234.56")),
        ("EUR 1,234.56", Decimal("1234.56")),
        ("181,06", Decimal("181.06")),
        ("-12.40", Decimal("-12.40")),
        (None, None),
        ("n/a", None),
        (True, None),
    ],
)
def test_parse_amount(raw: object, expected: Decimal | None) -> None:
    assert parse_amount(raw) == expected


def test_extraction_keeps_printed_values() -> None:
    extraction = extraction_from_payload(
        {
            "invoice_number": " INV-1 ",
            "net": "100,00",
            "tax_rate": 19,
            "tax": 19,
            "gross": "119",
            "summary": "Kurz.",
            "notes": ["Tor 3"],
        }
    )
    assert extraction.invoice_number == "INV-1"
    assert extraction.gross == Decimal("119.00")
    assert extraction.notes == ("Tor 3",)


def test_classification_normalizes_unknown_values() -> None:
    result = classification_from_payload(
        {
            "document_type": "memo",
            "document_type_confidence": 7,
            "vendor_key": "acme",
            "vendor_confidence": "x",
            "formally_complete_probability": -1,
        }
    )
    assert result.document_type == "unrecognized"
    assert result.document_type_confidence == 1.0
    assert result.vendor_key == "unknown"
    assert result.vendor_confidence == 0.0
    assert result.formally_complete_probability == 0.0


def test_classification_requires_document_type() -> None:
    with pytest.raises(ResponseFormatError):
        classification_from_payload({})


def test_classification_from_jev() -> None:
    result = classification_from_jev(
        {
            "document_type": {"choice": "invoice", "confidence": 0.99},
            "vendor": {"choice": "aws", "confidence": 0.97},
            "formally_complete": {"noul": 0.92},
        }
    )
    assert (result.document_type, result.vendor_key) == ("invoice", "aws")
    assert result.formally_complete_probability == pytest.approx(0.92)


def test_classification_from_jev_requires_all_answers() -> None:
    with pytest.raises(ResponseFormatError):
        classification_from_jev({"document_type": {"choice": "invoice"}})
