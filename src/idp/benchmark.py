"""Run every system over the corpus and store one answer per document.

Context: Resumable measurement loop; finished documents are skipped on restart. |
Input: Corpus, systems, settings. |
Output: JSON Lines per system under results/raw/.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from idp.domain import Classification, Extraction, LabeledDocument
from idp.errors import ProviderError
from idp.systems import Answer, Clients, SystemSpec

logger = logging.getLogger(__name__)


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def answer_record(doc_id: str, answer: Answer) -> dict[str, Any]:
    """Serializable form of one answer."""
    return {
        "doc_id": doc_id,
        "classification": asdict(answer.classification),
        "extraction": asdict(answer.extraction),
        "latency_ms": round(answer.latency_ms, 1),
        "cost_usd": str(answer.cost_usd),
        "calls": {k: round(v, 1) for k, v in answer.calls.items()},
    }


def error_record(doc_id: str, error: Exception) -> dict[str, Any]:
    """Serializable form of a failed document."""
    return {"doc_id": doc_id, "error": f"{type(error).__name__}: {error}"[:500]}


def answer_from_record(record: dict[str, Any]) -> Answer | None:
    """Rebuild an Answer from a stored record; None for failed documents."""
    if "error" in record:
        return None
    raw = record["extraction"]

    def amount(key: str) -> Decimal | None:
        return None if raw.get(key) is None else Decimal(raw[key])

    extraction = Extraction(
        vendor_name=raw.get("vendor_name"),
        invoice_number=raw.get("invoice_number"),
        invoice_date=raw.get("invoice_date"),
        net=amount("net"),
        tax_rate=amount("tax_rate"),
        tax=amount("tax"),
        gross=amount("gross"),
        summary=raw.get("summary", ""),
        notes=tuple(raw.get("notes", ())),
    )
    return Answer(
        Classification(**record["classification"]),
        extraction,
        float(record["latency_ms"]),
        Decimal(record["cost_usd"]),
        record.get("calls", {}),
    )


def load_records(path: Path) -> dict[str, dict[str, Any]]:
    """Read stored records keyed by document id; later lines win."""
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                record = json.loads(line)
                records[record["doc_id"]] = record
    return records


def run_system(
    spec: SystemSpec,
    documents: Iterable[LabeledDocument],
    clients: Clients,
    out_dir: Path,
    *,
    concurrency: int,
    retry_failed: bool = True,
) -> Path:
    """Answer every document that has no stored answer yet.

    Args:
        spec: System to run.
        documents: Corpus in processing order.
        clients: Shared provider clients.
        out_dir: Directory for results/raw files.
        concurrency: Parallel requests for this system.
        retry_failed: Re-run documents whose stored record is an error.

    Returns:
        Path of the JSON Lines file with all answers.
    """
    path = out_dir / f"{spec.key}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    stored = load_records(path)
    pending = [
        d
        for d in documents
        if d.doc_id not in stored or (retry_failed and "error" in stored[d.doc_id])
    ]
    if not pending:
        logger.info("%s: all documents already answered", spec.key)
        return path
    runner = spec.build(clients)
    lock = threading.Lock()
    logger.info("%s: %d documents to answer", spec.key, len(pending))
    with path.open("a", encoding="utf-8") as stream, ThreadPoolExecutor(concurrency) as pool:
        futures = {pool.submit(runner, d.text): d.doc_id for d in pending}
        for done, future in enumerate(as_completed(futures), 1):
            doc_id = futures[future]
            try:
                record = answer_record(doc_id, future.result())
            except ProviderError as error:
                logger.warning("%s %s failed: %s", spec.key, doc_id, error)
                record = error_record(doc_id, error)
            with lock:
                stream.write(json.dumps(record, default=_json_default, ensure_ascii=False) + "\n")
                stream.flush()
            if done % 25 == 0:
                logger.info("%s: %d/%d", spec.key, done, len(pending))
    return path
