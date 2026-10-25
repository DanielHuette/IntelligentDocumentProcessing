"""Prompts and Jev questions, shared by the benchmark and the n8n workflow.

Context: One definition of every model instruction, so benchmark and production ask the same
thing. |
Input: Domain labels and vendor master data. |
Output: Prompt strings and the Jev question set.
"""

from __future__ import annotations

import json
from typing import Any

from idp.domain import DOCUMENT_TYPE_DESCRIPTIONS, UNKNOWN_VENDOR
from idp.vendors import VENDORS

FORMAL_COMPLETENESS = (
    "Is this a formally complete German invoice with supplier name and address, supplier VAT "
    "ID or tax number, invoice number, invoice date, line items, net amount, tax rate, tax "
    "amount and gross total all printed?"
)
UNKNOWN_VENDOR_CRITERION = (
    "The document does not come from, and is not addressed to, exactly one of the listed "
    "suppliers (new supplier, private shop, bank, or scam)."
)


def vendor_options() -> dict[str, str]:
    """Supplier choices with the details that identify each one."""
    options = {
        vendor.key: f"{vendor.party.name}, {vendor.party.street}, {vendor.party.city}, "
        f"VAT ID {vendor.party.vat_id}"
        for vendor in VENDORS
    }
    options[UNKNOWN_VENDOR] = UNKNOWN_VENDOR_CRITERION
    return options


def document_type_options() -> dict[str, str]:
    """Document type choices with their definitions."""
    return {doc_type.value: text for doc_type, text in DOCUMENT_TYPE_DESCRIPTIONS.items()}


def jev_questions() -> dict[str, dict[str, Any]]:
    """The three typed questions Jev answers for every document."""
    return {
        "document_type": {
            "type": "choice",
            "instructions": "Which kind of document is this?",
            "criteria": document_type_options(),
        },
        "vendor": {
            "type": "choice",
            "instructions": (
                "Which supplier from the master data issued this document or is its business "
                "counterparty? Kessler Maschinenbau GmbH is the buyer, never the answer."
            ),
            "criteria": vendor_options(),
        },
        "formally_complete": {"type": "noul", "instructions": FORMAL_COMPLETENESS},
    }


_EXTRACTION_FIELDS = """\
"vendor_name": supplier name as printed, or null,
"invoice_number": invoice number exactly as printed, or null if none is printed,
"invoice_date": date in ISO format YYYY-MM-DD, or null,
"net": net total as a number, or null,
"tax_rate": VAT rate in percent as a number (19 for 19 %), or null,
"tax": VAT amount as a number, or null,
"gross": gross total as a number, or null,
"summary": two short German sentences: what the document is about and what action it needs,
"notes": list of remarks that are not booking data (delivery notes, office hours, warnings)"""

_AMOUNT_RULE = (
    "Copy amounts exactly as printed, even when they do not add up. Never correct or recompute "
    "them. Use null for anything the document does not state."
)

EXTRACTION_SYSTEM_PROMPT = f"""\
You extract booking data from documents received by the accounts payable team of \
Kessler Maschinenbau GmbH. The documents may be letters, e-mails, scans with recognition \
errors, table exports or XRechnung XML, in German or English.

Return one JSON object and nothing else, with these keys:
{_EXTRACTION_FIELDS}

{_AMOUNT_RULE}"""


def full_system_prompt() -> str:
    """System prompt for a single model that classifies and extracts in one call."""
    types = json.dumps(document_type_options(), indent=1, ensure_ascii=False)
    vendors = json.dumps(vendor_options(), indent=1, ensure_ascii=False)
    return f"""\
You process documents received by the accounts payable team of Kessler Maschinenbau GmbH. \
The documents may be letters, e-mails, scans with recognition errors, table exports or \
XRechnung XML, in German or English.

Document types (key: definition):
{types}

Supplier master data (key: identifying details). Kessler Maschinenbau GmbH is the buyer and \
never the supplier:
{vendors}

Return one JSON object and nothing else, with these keys:
"document_type": one document type key,
"document_type_confidence": your probability between 0 and 1 that the type is right,
"vendor_key": one supplier key, or "{UNKNOWN_VENDOR}",
"vendor_confidence": your probability between 0 and 1 that the supplier is right,
"formally_complete_probability": probability between 0 and 1 that the answer to this \
question is yes: {FORMAL_COMPLETENESS},
{_EXTRACTION_FIELDS}

{_AMOUNT_RULE}"""


def user_message(document_text: str) -> str:
    """Wrap a document so the model cannot confuse it with instructions."""
    return f"<document>\n{document_text}\n</document>"
