"""Shared fixtures for the test suite."""

from __future__ import annotations

from decimal import Decimal

import pytest

from idp.config import Settings
from idp.corpus import generate_corpus
from idp.domain import Classification, Extraction, LabeledDocument


@pytest.fixture
def settings() -> Settings:
    """Settings with dummy credentials that never leave the test process."""
    return Settings(
        _env_file=None,
        anthropic_api_key="test-anthropic",
        openai_api_key="test-openai",
        cloudflare_account_id="account123",
        cloudflare_api_token="test-cloudflare",
        max_attempts=2,
    )


@pytest.fixture
def confident_invoice() -> Classification:
    """Jev-style decisions for a clean invoice from a known supplier."""
    return Classification("invoice", 0.99, "telekom", 0.98, 0.95)


@pytest.fixture
def clean_extraction() -> Extraction:
    """Totals that add up at 19 %."""
    return Extraction(
        vendor_name="Telekom Deutschland GmbH",
        invoice_number="412 7781 30519",
        invoice_date="2026-10-02",
        net=Decimal("152.15"),
        tax_rate=Decimal("19"),
        tax=Decimal("28.91"),
        gross=Decimal("181.06"),
        summary="Mobilfunkrechnung.",
    )


@pytest.fixture(scope="session")
def corpus() -> list[LabeledDocument]:
    """The default corpus, generated once per test session."""
    return generate_corpus(250, 2026)
