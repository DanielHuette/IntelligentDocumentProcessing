"""Score stored answers against the ground truth.

Context: Final benchmark stage; applies the same confidence gate to every system. |
Input: Corpus and stored answers. |
Output: Metrics per system, JSON and Markdown.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from idp.benchmark import answer_from_record, load_records
from idp.domain import DocumentType, LabeledDocument, Route
from idp.rules import duplicate_key, gate
from idp.systems import PRICES_CHECKED, SystemSpec

AMOUNT_TYPES = frozenset({DocumentType.INVOICE, DocumentType.CREDIT_NOTE})


@dataclass(frozen=True, slots=True)
class Metrics:
    """Quality, speed and cost of one system on the corpus."""

    system: str
    label: str
    provider: str
    documents: int
    failures: int
    document_type_accuracy: float
    vendor_accuracy: float
    completeness_accuracy: float
    gross_accuracy: float
    route_accuracy: float
    wrongly_approved: int
    needless_reviews: int
    latency_p50_ms: float
    latency_p95_ms: float
    cost_per_1000_usd: float


def _share(hits: int, total: int) -> float:
    return round(100 * hits / total, 1) if total else 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return round(ordered[index], 0)


def score_system(spec: SystemSpec, corpus: list[LabeledDocument], raw_dir: Path) -> Metrics:
    """Score one system; failed documents count as wrong and go to review.

    Args:
        spec: System to score.
        corpus: Documents in processing order.
        raw_dir: Directory with stored answers.

    Returns:
        Metrics for the system.
    """
    records = load_records(raw_dir / f"{spec.key}.jsonl")
    booked: set[str] = set()
    hits = {"type": 0, "vendor": 0, "complete": 0, "gross": 0, "route": 0}
    amount_docs = failures = wrongly_approved = needless = 0
    latencies: list[float] = []
    cost = Decimal(0)
    for document in corpus:
        truth = document.truth
        expects_amount = truth.document_type in AMOUNT_TYPES and truth.amounts is not None
        amount_docs += expects_amount
        record = records.get(document.doc_id)
        answer = answer_from_record(record) if record else None
        if answer is None:
            failures += 1
            hits["route"] += truth.route == Route.NEEDS_REVIEW
            continue
        c, e = answer.classification, answer.extraction
        latencies.append(answer.latency_ms)
        cost += answer.cost_usd
        hits["type"] += c.document_type == truth.document_type
        hits["vendor"] += c.vendor_key == truth.vendor_key
        hits["complete"] += (c.formally_complete_probability >= 0.5) == truth.formally_complete
        if expects_amount and truth.amounts is not None:
            hits["gross"] += e.gross is not None and abs(e.gross) == truth.amounts.gross
        decision = gate(c, e, booked)
        if decision.route == Route.APPROVED:
            key = duplicate_key(c.vendor_key, e.invoice_number)
            if key:
                booked.add(key)
        hits["route"] += decision.route == truth.route
        wrongly_approved += decision.route == Route.APPROVED != truth.route
        needless += decision.route == Route.NEEDS_REVIEW != truth.route
    answered = len(corpus) - failures
    return Metrics(
        system=spec.key,
        label=spec.label,
        provider=spec.provider,
        documents=len(corpus),
        failures=failures,
        document_type_accuracy=_share(hits["type"], len(corpus)),
        vendor_accuracy=_share(hits["vendor"], len(corpus)),
        completeness_accuracy=_share(hits["complete"], len(corpus)),
        gross_accuracy=_share(hits["gross"], amount_docs),
        route_accuracy=_share(hits["route"], len(corpus)),
        wrongly_approved=wrongly_approved,
        needless_reviews=needless,
        latency_p50_ms=round(statistics.median(latencies), 0) if latencies else 0.0,
        latency_p95_ms=_percentile(latencies, 0.95),
        cost_per_1000_usd=round(float(cost) / answered * 1000, 3) if answered else 0.0,
    )


def jev_latencies(raw_dir: Path) -> dict[str, float]:
    """Median and 95th percentile of the Jev call alone inside the hybrid system."""
    values = [
        r["calls"]["typesafe/jev"]
        for r in load_records(raw_dir / "hybrid.jsonl").values()
        if "calls" in r and "typesafe/jev" in r["calls"]
    ]
    if not values:
        return {}
    return {
        "p50_ms": round(statistics.median(values), 0),
        "p95_ms": _percentile(values, 0.95),
        "count": len(values),
    }


def markdown_table(metrics: list[Metrics], language: str = "en") -> str:
    """Render the comparison table in English or German."""
    headers = {
        "en": (
            "System",
            "Routing correct",
            "Wrongly approved",
            "Needless reviews",
            "Doc type",
            "Vendor",
            "Completeness",
            "Gross amount",
            "Median latency",
            "95th pct latency",
            "Cost per 1,000 docs",
            "Failures",
        ),
        "de": (
            "System",
            "Weiche richtig",
            "Fälschlich freigegeben",
            "Unnötig zur Prüfung",
            "Dokumentart",
            "Lieferant",
            "Formprüfung",
            "Bruttobetrag",
            "Antwortzeit Median",
            "Antwortzeit 95 %",
            "Kosten je 1.000 Dokumente",
            "Ausfälle",
        ),
    }[language]
    german = language == "de"

    def num(value: float, digits: int) -> str:
        text = f"{value:,.{digits}f}"
        return text.replace(",", "X").replace(".", ",").replace("X", ".") if german else text

    def money(value: float) -> str:
        return f"{num(value, 2)} $" if german else f"${num(value, 2)}"

    rows = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for m in sorted(metrics, key=lambda m: (-m.route_accuracy, m.wrongly_approved)):
        rows.append(
            f"| {m.label} | {num(m.route_accuracy, 1)} % | {m.wrongly_approved} "
            f"| {m.needless_reviews} | {num(m.document_type_accuracy, 1)} % "
            f"| {num(m.vendor_accuracy, 1)} % | {num(m.completeness_accuracy, 1)} % "
            f"| {num(m.gross_accuracy, 1)} % | {num(m.latency_p50_ms, 0)} ms "
            f"| {num(m.latency_p95_ms, 0)} ms | {money(m.cost_per_1000_usd)} | {m.failures} |"
        )
    return "\n".join(rows) + "\n"


def write_report(metrics: list[Metrics], jev: dict[str, float], out_dir: Path) -> None:
    """Write summary.json and Markdown tables in both languages."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "prices_checked": PRICES_CHECKED,
        "jev_call_latency": jev,
        "systems": [asdict(m) for m in metrics],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "benchmark.md").write_text(markdown_table(metrics, "en"), encoding="utf-8")
    (out_dir / "benchmark.de.md").write_text(markdown_table(metrics, "de"), encoding="utf-8")
