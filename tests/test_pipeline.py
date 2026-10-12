"""Tests for systems, the measurement loop and the report."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import respx

from idp.benchmark import answer_from_record, load_records, run_system
from idp.config import Settings
from idp.domain import Classification, Extraction, LabeledDocument, Route
from idp.errors import ConfigError, ProviderError
from idp.providers.base import Usage
from idp.providers.clients import ANTHROPIC_URL
from idp.report import jev_latencies, markdown_table, score_system, write_report
from idp.systems import PRICES, SYSTEMS_BY_KEY, Answer, Clients, Price, SystemSpec


def _truthful(document: LabeledDocument) -> Answer:
    """Answer exactly like the ground truth, with full confidence."""
    truth = document.truth
    amounts = truth.amounts
    return Answer(
        Classification(
            truth.document_type.value,
            1.0,
            truth.vendor_key,
            1.0,
            1.0 if truth.formally_complete else 0.0,
        ),
        Extraction(
            None,
            truth.invoice_number,
            None,
            amounts.net if amounts else None,
            amounts.tax_rate * 100 if amounts else None,
            amounts.tax if amounts else None,
            amounts.gross if amounts else None,
            "ok",
        ),
        100.0,
        Decimal("0.001"),
        {"typesafe/jev": 50.0},
    )


def _oracle(corpus: list[LabeledDocument], fail: set[str] | None = None) -> SystemSpec:
    by_text: dict[str, LabeledDocument] = {}
    for document in corpus:
        by_text.setdefault(document.text, document)

    def build(_clients: Clients) -> object:
        def run(text: str) -> Answer:
            document = by_text[text]
            if fail and document.doc_id in fail:
                raise ProviderError("boom")
            return _truthful(document)

        return run

    return SystemSpec("hybrid", "Oracle", "test", build)  # type: ignore[arg-type]


def test_price_cost() -> None:
    assert Price(Decimal("1"), Decimal("2")).cost(Usage(1_000_000, 500_000)) == Decimal("2")
    assert all(price.input >= 0 for price in PRICES.values())


def test_clients_require_credentials() -> None:
    clients = Clients(Settings(_env_file=None))
    try:
        with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
            clients.anthropic()
    finally:
        clients.close()


@respx.mock
def test_hybrid_system_combines_jev_and_haiku(settings: Settings) -> None:
    respx.post("https://api.cloudflare.com/client/v4/accounts/account123/ai/run").respond(
        json={
            "result": {
                "result": {
                    "answers": {
                        "document_type": {"choice": "invoice", "confidence": 0.99},
                        "vendor": {"choice": "telekom", "confidence": 0.99},
                        "formally_complete": {"noul": 0.95},
                    },
                    "usage": {"input_tokens": 2000, "output_tokens": 300},
                }
            },
        }
    )
    respx.post(ANTHROPIC_URL).respond(
        json={
            "content": [
                {
                    "text": '{"invoice_number": "1", "net": 100, "tax_rate": 19, '
                    '"tax": 19, "gross": 119, "summary": "s"}'
                }
            ],
            "usage": {"input_tokens": 700, "output_tokens": 200},
        }
    )
    clients = Clients(settings)
    try:
        answer = SYSTEMS_BY_KEY["hybrid"].build(clients)("document")
    finally:
        clients.close()
    assert answer.classification.vendor_key == "telekom"
    assert answer.extraction.gross == Decimal("119.00")
    assert set(answer.calls) == {"typesafe/jev", "claude-haiku-5-5"}
    assert answer.cost_usd == Decimal("0.000084") + Decimal("0.00017")


def test_run_system_is_resumable(
    tmp_path: Path, corpus: list[LabeledDocument], settings: Settings
) -> None:
    subset = corpus[:20]
    clients = Clients(settings)
    try:
        path = run_system(
            _oracle(subset, {subset[0].doc_id}), subset, clients, tmp_path, concurrency=3
        )
        assert "error" in load_records(path)[subset[0].doc_id]
        run_system(_oracle(subset), subset, clients, tmp_path, concurrency=3)
    finally:
        clients.close()
    records = load_records(path)
    assert len(records) == 20
    assert all(answer_from_record(r) is not None for r in records.values())


def test_perfect_answers_score_perfectly(
    tmp_path: Path, corpus: list[LabeledDocument], settings: Settings
) -> None:
    spec = _oracle(corpus)
    clients = Clients(settings)
    try:
        run_system(spec, corpus, clients, tmp_path / "raw", concurrency=8)
    finally:
        clients.close()
    metrics = score_system(spec, corpus, tmp_path / "raw")
    assert metrics.route_accuracy == 100.0
    assert metrics.wrongly_approved == 0
    assert metrics.gross_accuracy == 100.0
    assert metrics.cost_per_1000_usd == pytest.approx(1.0)
    assert jev_latencies(tmp_path / "raw")["p50_ms"] == 50.0
    write_report([metrics], {}, tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["systems"][0]["route_accuracy"] == 100.0
    assert "Weiche richtig" in (tmp_path / "benchmark.de.md").read_text()


def test_failed_documents_go_to_review(tmp_path: Path, corpus: list[LabeledDocument]) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "hybrid.jsonl").write_text(
        "\n".join(json.dumps({"doc_id": d.doc_id, "error": "x"}) for d in corpus) + "\n"
    )
    metrics = score_system(_oracle(corpus), corpus, raw)
    expected = sum(d.truth.route == Route.NEEDS_REVIEW for d in corpus) / len(corpus)
    assert metrics.failures == len(corpus)
    assert metrics.route_accuracy == pytest.approx(round(100 * expected, 1))
    assert "| Oracle |" in markdown_table([metrics])
