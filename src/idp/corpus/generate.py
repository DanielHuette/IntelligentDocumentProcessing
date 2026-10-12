"""Assemble the benchmark corpus with planted defects and known answers.

Context: Entry point of corpus generation. |
Input: Size and seed. |
Output: Ordered labeled documents, JSONL on disk.
"""

from __future__ import annotations

import json
import os
import random
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from idp.corpus.content import ContentFactory, Draft, compute_amounts
from idp.corpus.render import XRECHNUNG_TYPES, render
from idp.domain import (
    UNKNOWN_VENDOR,
    Amounts,
    Defect,
    DocumentFormat,
    DocumentType,
    GroundTruth,
    LabeledDocument,
    Route,
    Vendor,
)
from idp.vendors import SCAM_PARTIES, UNKNOWN_PARTIES, VENDORS

TYPE_SHARES: dict[DocumentType, float] = {
    DocumentType.INVOICE: 0.36,
    DocumentType.CREDIT_NOTE: 0.06,
    DocumentType.PAYMENT_REMINDER: 0.06,
    DocumentType.DELIVERY_NOTE: 0.06,
    DocumentType.QUOTE: 0.06,
    DocumentType.PURCHASE_ORDER: 0.06,
    DocumentType.ORDER_CONFIRMATION: 0.06,
    DocumentType.CONTRACT: 0.048,
    DocumentType.TERMINATION: 0.04,
    DocumentType.RECEIPT: 0.06,
    DocumentType.BANK_STATEMENT: 0.04,
    DocumentType.EMAIL: 0.052,
    DocumentType.FRAUDULENT_INVOICE: 0.04,
}

DEFECT_SHARES: dict[Defect | None, float] = {
    None: 0.50,
    Defect.ARITHMETIC_ERROR: 0.09,
    Defect.MISSING_VAT_ID: 0.09,
    Defect.WRONG_TAX_RATE: 0.08,
    Defect.MISSING_INVOICE_NUMBER: 0.08,
    Defect.UNKNOWN_VENDOR: 0.09,
    Defect.DUPLICATE: 0.07,
}

FORMAT_WEIGHTS: dict[DocumentFormat, int] = {
    DocumentFormat.PLAIN: 30,
    DocumentFormat.EMAIL: 20,
    DocumentFormat.OCR: 15,
    DocumentFormat.TABLE: 10,
    DocumentFormat.ENGLISH: 15,
    DocumentFormat.XRECHNUNG: 10,
}

WRONG_RATE = Decimal("0.16")

SUPPLIER_DOCUMENTS: dict[DocumentType, Callable[[ContentFactory, Vendor, str], Draft]] = {
    DocumentType.CREDIT_NOTE: ContentFactory.credit_note,
    DocumentType.PAYMENT_REMINDER: ContentFactory.payment_reminder,
    DocumentType.DELIVERY_NOTE: ContentFactory.delivery_note,
    DocumentType.PURCHASE_ORDER: ContentFactory.purchase_order,
    DocumentType.ORDER_CONFIRMATION: ContentFactory.order_confirmation,
    DocumentType.CONTRACT: ContentFactory.contract,
    DocumentType.TERMINATION: ContentFactory.termination,
}


def _allocate[K](shares: dict[K, float], total: int) -> dict[K, int]:
    """Split a total into whole counts that follow the shares and add up exactly."""
    raw = {key: share * total for key, share in shares.items()}
    counts = {key: int(value) for key, value in raw.items()}
    remainder = total - sum(counts.values())
    by_fraction = sorted(raw, key=lambda key: raw[key] - counts[key], reverse=True)
    for key in by_fraction[:remainder]:
        counts[key] += 1
    return counts


class CorpusBuilder:
    """Builds one corpus deterministically from a seed."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self._factory = ContentFactory(self._rng)

    def _format_for(self, document_type: DocumentType) -> DocumentFormat:
        formats = list(FORMAT_WEIGHTS)
        weights = list(FORMAT_WEIGHTS.values())
        if document_type not in XRECHNUNG_TYPES:
            weights[formats.index(DocumentFormat.XRECHNUNG)] = 0
        return self._rng.choices(formats, weights)[0]

    def _invoice(self, defect: Defect | None, fmt: DocumentFormat) -> tuple[Draft, GroundTruth]:
        language = "en" if fmt == DocumentFormat.ENGLISH else "de"
        if defect == Defect.UNKNOWN_VENDOR:
            sender = self._rng.choice([p for p in UNKNOWN_PARTIES if p.vat_id])
            vendor_key, trade = UNKNOWN_VENDOR, "unknown"
        else:
            vendor = self._rng.choice(VENDORS)
            sender, vendor_key, trade = vendor.party, vendor.key, vendor.trade
        draft, number = self._factory.invoice(sender, trade, language)
        amounts = draft.amounts
        assert amounts is not None
        invoice_number: str | None = number
        if defect == Defect.ARITHMETIC_ERROR:
            offset = Decimal(self._rng.randint(1000, 9000)) / 100 * self._rng.choice((1, -1))
            amounts = replace(amounts, gross=amounts.gross + offset)
        elif defect == Defect.WRONG_TAX_RATE:
            amounts = compute_amounts(draft.items, WRONG_RATE)
        elif defect == Defect.MISSING_VAT_ID:
            draft.show_vat_id = False
        elif defect == Defect.MISSING_INVOICE_NUMBER:
            draft.fields = [f for f in draft.fields if f[1] != number]
            draft.subject = "Rechnung" if language == "de" else "Invoice"
            invoice_number = None
        draft.amounts = amounts
        complete = defect not in (Defect.MISSING_VAT_ID, Defect.MISSING_INVOICE_NUMBER)
        truth = GroundTruth(
            document_type=DocumentType.INVOICE,
            vendor_key=vendor_key,
            formally_complete=complete,
            invoice_number=invoice_number,
            amounts=amounts,
            route=Route.APPROVED if defect is None else Route.NEEDS_REVIEW,
            defects=(defect,) if defect else (),
        )
        return draft, truth

    def _other(self, document_type: DocumentType, fmt: DocumentFormat) -> tuple[Draft, str]:
        language = "en" if fmt == DocumentFormat.ENGLISH else "de"
        vendor = self._rng.choice(VENDORS)
        builder = SUPPLIER_DOCUMENTS.get(document_type)
        if builder is not None:
            return builder(self._factory, vendor, language), vendor.key
        return self._special(document_type, vendor, language)

    def _special(
        self, document_type: DocumentType, vendor: Vendor, language: str
    ) -> tuple[Draft, str]:
        """Documents whose partner may be unknown, a bank, a shop or a scammer."""
        factory, rng = self._factory, self._rng
        key = UNKNOWN_VENDOR
        match document_type:
            case DocumentType.QUOTE if rng.random() < 0.4:
                draft = factory.quote(rng.choice(UNKNOWN_PARTIES), "unknown", language)
            case DocumentType.QUOTE:
                draft, key = factory.quote(vendor.party, vendor.trade, language), vendor.key
            case DocumentType.RECEIPT:
                draft = factory.receipt(language)
            case DocumentType.BANK_STATEMENT:
                draft = factory.bank_statement(language)
            case DocumentType.EMAIL if rng.random() < 0.3:
                draft = factory.email(rng.choice(UNKNOWN_PARTIES), language)
            case DocumentType.EMAIL:
                draft, key = factory.email(vendor.party, language), vendor.key
            case DocumentType.FRAUDULENT_INVOICE:
                draft = factory.fraudulent_invoice(rng.choice(SCAM_PARTIES), language)
            case _:
                raise ValueError(f"{document_type} is built elsewhere")
        return draft, key

    def _duplicate_of(self, original: LabeledDocument) -> LabeledDocument:
        """Re-submit an approved invoice, often in another format."""
        truth = replace(original.truth, route=Route.NEEDS_REVIEW, defects=(Defect.DUPLICATE,))
        return LabeledDocument("", original.document_format, original.text, truth)

    def build(self, size: int) -> list[LabeledDocument]:
        """Create the corpus in processing order; duplicates follow their originals."""
        type_counts = _allocate(TYPE_SHARES, size)
        defect_counts = _allocate(DEFECT_SHARES, type_counts[DocumentType.INVOICE])
        duplicates = defect_counts.pop(Defect.DUPLICATE)
        documents: list[LabeledDocument] = []
        for defect, count in defect_counts.items():
            for _ in range(count):
                fmt = self._format_for(DocumentType.INVOICE)
                draft, truth = self._invoice(defect, fmt)
                documents.append(LabeledDocument("", fmt, render(draft, fmt, self._rng), truth))
        for document_type, count in type_counts.items():
            if document_type == DocumentType.INVOICE:
                continue
            for _ in range(count):
                fmt = self._format_for(document_type)
                draft, vendor_key = self._other(document_type, fmt)
                truth = GroundTruth(
                    document_type,
                    vendor_key,
                    False,
                    None,
                    draft.amounts if document_type == DocumentType.CREDIT_NOTE else None,
                    Route.NEEDS_REVIEW,
                )
                documents.append(LabeledDocument("", fmt, render(draft, fmt, self._rng), truth))
        self._rng.shuffle(documents)
        clean = [i for i, d in enumerate(documents) if d.truth.route == Route.APPROVED]
        for index in sorted(self._rng.sample(clean, duplicates), reverse=True):
            position = self._rng.randint(index + 1, len(documents))
            documents.insert(position, self._duplicate_of(documents[index]))
        return [replace(d, doc_id=f"doc-{i:04d}") for i, d in enumerate(documents, 1)]


def generate_corpus(size: int = 250, seed: int = 2026) -> list[LabeledDocument]:
    """Generate a labeled corpus.

    Args:
        size: Number of documents including duplicates.
        seed: Seed for full reproducibility.

    Returns:
        Documents in the order a mailbox would deliver them.

    Raises:
        ValueError: If size is too small to hold every document type.
    """
    if size < 50:
        raise ValueError("size must be at least 50 to cover every document type and defect")
    return CorpusBuilder(seed).build(size)


def _to_json(document: LabeledDocument) -> dict[str, object]:
    truth = document.truth
    amounts = truth.amounts
    return {
        "doc_id": document.doc_id,
        "format": document.document_format.value,
        "text": document.text,
        "truth": {
            "document_type": truth.document_type.value,
            "vendor_key": truth.vendor_key,
            "formally_complete": truth.formally_complete,
            "invoice_number": truth.invoice_number,
            "amounts": None
            if amounts is None
            else {
                "net": str(amounts.net),
                "tax_rate": str(amounts.tax_rate),
                "tax": str(amounts.tax),
                "gross": str(amounts.gross),
            },
            "route": truth.route.value,
            "defects": [d.value for d in truth.defects],
        },
    }


def _from_json(raw: dict[str, object]) -> LabeledDocument:
    truth = raw["truth"]
    assert isinstance(truth, dict)
    amounts = truth["amounts"]
    return LabeledDocument(
        doc_id=str(raw["doc_id"]),
        document_format=DocumentFormat(str(raw["format"])),
        text=str(raw["text"]),
        truth=GroundTruth(
            document_type=DocumentType(truth["document_type"]),
            vendor_key=truth["vendor_key"],
            formally_complete=bool(truth["formally_complete"]),
            invoice_number=truth["invoice_number"],
            amounts=None
            if amounts is None
            else Amounts(**{key: Decimal(value) for key, value in amounts.items()}),
            route=Route(truth["route"]),
            defects=tuple(Defect(d) for d in truth["defects"]),
        ),
    )


def write_corpus(documents: list[LabeledDocument], path: Path) -> None:
    """Write the corpus as JSON Lines, atomically.

    Args:
        documents: Corpus to store.
        path: Target file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        for document in documents:
            stream.write(json.dumps(_to_json(document), ensure_ascii=False) + "\n")
    Path(temp_name).replace(path)


def load_corpus(path: Path) -> Iterator[LabeledDocument]:
    """Stream a corpus from JSON Lines.

    Args:
        path: File written by write_corpus.

    Yields:
        Labeled documents in stored order.
    """
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield _from_json(json.loads(line))
