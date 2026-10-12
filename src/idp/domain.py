"""Domain types shared by the corpus generator, the decision rules and the benchmark.

Context: Single source of truth for labels. | Input: None. | Output: Enums and immutable records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class DocumentType(StrEnum):
    """Kinds of documents that land in an accounts-payable inbox."""

    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    PAYMENT_REMINDER = "payment_reminder"
    DELIVERY_NOTE = "delivery_note"
    QUOTE = "quote"
    PURCHASE_ORDER = "purchase_order"
    ORDER_CONFIRMATION = "order_confirmation"
    CONTRACT = "contract"
    TERMINATION = "termination"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    EMAIL = "email"
    FRAUDULENT_INVOICE = "fraudulent_invoice"


DOCUMENT_TYPE_DESCRIPTIONS: dict[DocumentType, str] = {
    DocumentType.INVOICE: (
        "A supplier invoice that requests payment for delivered goods or services."
    ),
    DocumentType.CREDIT_NOTE: (
        "A credit note (Gutschrift) that reduces or refunds an earlier invoice."
    ),
    DocumentType.PAYMENT_REMINDER: (
        "A payment reminder or dunning letter (Mahnung) about an unpaid invoice."
    ),
    DocumentType.DELIVERY_NOTE: (
        "A delivery note (Lieferschein) listing shipped goods, without prices to pay."
    ),
    DocumentType.QUOTE: "A quote or offer (Angebot) with prices for possible future business.",
    DocumentType.PURCHASE_ORDER: "A purchase order (Bestellung) sent by the buyer to a supplier.",
    DocumentType.ORDER_CONFIRMATION: (
        "An order confirmation (Auftragsbestätigung) from the supplier."
    ),
    DocumentType.CONTRACT: "A contract, framework agreement or excerpt of terms and conditions.",
    DocumentType.TERMINATION: "A termination or cancellation notice (Kündigung) for a contract.",
    DocumentType.RECEIPT: (
        "A small cash or card receipt (Quittung, Kassenbon), e.g. for travel expenses."
    ),
    DocumentType.BANK_STATEMENT: (
        "A bank account statement (Kontoauszug) listing account movements."
    ),
    DocumentType.EMAIL: "An ordinary business e-mail without a document that needs booking.",
    DocumentType.FRAUDULENT_INVOICE: (
        "Looks like an invoice but is an unsolicited offer or scam, e.g. a directory listing "
        "'offer' in invoice layout or urgent payment to an unknown foreign account."
    ),
}


class DocumentFormat(StrEnum):
    """How a document reaches the inbox."""

    PLAIN = "plain"
    EMAIL = "email"
    OCR = "ocr"
    TABLE = "table"
    ENGLISH = "english"
    XRECHNUNG = "xrechnung"


class Defect(StrEnum):
    """Deliberate faults planted in invoices."""

    ARITHMETIC_ERROR = "arithmetic_error"
    MISSING_VAT_ID = "missing_vat_id"
    WRONG_TAX_RATE = "wrong_tax_rate"
    MISSING_INVOICE_NUMBER = "missing_invoice_number"
    UNKNOWN_VENDOR = "unknown_vendor"
    DUPLICATE = "duplicate"


class Route(StrEnum):
    """Outcome of the confidence gate."""

    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"


UNKNOWN_VENDOR = "unknown"


@dataclass(frozen=True, slots=True)
class Party:
    """A company with the data that appears on business documents."""

    name: str
    street: str
    city: str
    vat_id: str | None
    iban: str
    email_domain: str


@dataclass(frozen=True, slots=True)
class Vendor:
    """A supplier from the master data of the buying company."""

    key: str
    party: Party
    trade: str


@dataclass(frozen=True, slots=True)
class Amounts:
    """Totals exactly as printed on a document."""

    net: Decimal
    tax_rate: Decimal
    tax: Decimal
    gross: Decimal


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """The correct answers for one generated document."""

    document_type: DocumentType
    vendor_key: str
    formally_complete: bool
    invoice_number: str | None
    amounts: Amounts | None
    route: Route
    defects: tuple[Defect, ...] = ()


@dataclass(frozen=True, slots=True)
class LabeledDocument:
    """A generated document together with its ground truth."""

    doc_id: str
    document_format: DocumentFormat
    text: str
    truth: GroundTruth


@dataclass(frozen=True, slots=True)
class Extraction:
    """Fields a language model reads from a document."""

    vendor_name: str | None
    invoice_number: str | None
    invoice_date: str | None
    net: Decimal | None
    tax_rate: Decimal | None
    tax: Decimal | None
    gross: Decimal | None
    summary: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Classification:
    """Typed decisions about a document, each with the model's confidence."""

    document_type: str
    document_type_confidence: float
    vendor_key: str
    vendor_confidence: float
    formally_complete_probability: float


@dataclass(frozen=True, slots=True)
class GateResult:
    """Route chosen by the confidence gate and the reasons for review."""

    route: Route
    reasons: tuple[str, ...] = field(default_factory=tuple)
