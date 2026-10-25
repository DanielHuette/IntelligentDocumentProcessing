"""Lay out drafts in the formats that reach a real inbox.

Context: Third stage of corpus generation. |
Input: Draft and target format. |
Output: Document text.
"""

from __future__ import annotations

import random
from decimal import Decimal
from xml.sax.saxutils import escape

from idp.corpus.content import Draft, money, percent
from idp.domain import DocumentFormat, DocumentType

WIDTH = 78
OCR_SWAPS = {
    "l": "1",
    "O": "0",
    "o": "ö",
    "rn": "m",
    "ü": "u",
    "ä": "a",
    "ß": "B",
    "e": "c",
    "i": "í",
    "S": "5",
}
XRECHNUNG_TYPES = frozenset({DocumentType.INVOICE, DocumentType.CREDIT_NOTE})


def _labels(draft: Draft) -> dict[str, str]:
    de = draft.language == "de"
    return {
        "pos": "Pos." if de else "Item",
        "desc": "Bezeichnung" if de else "Description",
        "qty": "Menge" if de else "Qty",
        "price": "Einzelpreis" if de else "Unit price",
        "total": "Gesamt" if de else "Total",
        "net": "Nettobetrag" if de else "Net amount",
        "tax": "Umsatzsteuer" if de else "VAT",
        "gross": "Rechnungsbetrag" if de else "Invoice total",
        "vat_id": "USt-IdNr." if de else "VAT ID",
        "bank": "Bankverbindung" if de else "Bank details",
    }


def _party_block(draft: Draft) -> list[str]:
    sender, recipient = draft.sender, draft.recipient
    return [
        f"{sender.name} · {sender.street} · {sender.city}",
        "",
        recipient.name,
        recipient.street,
        recipient.city,
        "",
    ]


def _item_lines(draft: Draft) -> list[str]:
    labels = _labels(draft)
    if not draft.items:
        return []
    if not draft.show_prices:
        rows = [f"{labels['pos']:<5}{labels['desc']:<52}{labels['qty']:>10}"]
        rows += [
            f"{i:<5}{item.description[:50]:<52}{item.quantity:>6} {item.unit}"
            for i, item in enumerate(draft.items, 1)
        ]
        return [*rows, ""]
    rows = [
        f"{labels['pos']:<5}{labels['desc']:<38}{labels['qty']:>6}"
        f"{labels['price']:>14}{labels['total']:>15}"
    ]
    for i, item in enumerate(draft.items, 1):
        rows.append(
            f"{i:<5}{item.description[:36]:<38}{item.quantity:>6}"
            f"{money(item.unit_price, draft.language):>14}"
            f"{money(item.net, draft.language):>15}"
        )
    return [*rows, ""]


def _total_lines(draft: Draft) -> list[str]:
    labels = _labels(draft)
    lang = draft.language
    if draft.amounts is None:
        if draft.amount_label and draft.items:
            total = sum((item.net for item in draft.items), Decimal("0.00"))
            return [f"{draft.amount_label}: {money(total, lang)}", ""]
        return []
    a = draft.amounts
    gross_label = draft.amount_label or labels["gross"]
    return [
        f"{labels['net']:<40}{money(a.net, lang):>20}",
        f"{labels['tax'] + ' ' + percent(a.tax_rate, lang):<40}{money(a.tax, lang):>20}",
        f"{gross_label:<40}{money(a.gross, lang):>20}",
        "",
    ]


def _footer(draft: Draft) -> list[str]:
    labels = _labels(draft)
    lines = ["-" * WIDTH, f"{draft.sender.name} · {draft.sender.street} · {draft.sender.city}"]
    if draft.show_vat_id and draft.sender.vat_id:
        lines.append(f"{labels['vat_id']} {draft.sender.vat_id}")
    if draft.show_bank and draft.sender.iban:
        lines.append(f"{labels['bank']}: IBAN {draft.sender.iban}")
    return lines


def render_plain(draft: Draft) -> str:
    """Lay out a draft as a printed letter."""
    lines = _party_block(draft)
    if draft.title:
        lines += [draft.title.upper(), ""]
    lines += [f"{label}: {value}" for label, value in draft.fields]
    lines.append("")
    lines += _item_lines(draft)
    lines += _total_lines(draft)
    lines += [*draft.paragraphs, ""]
    lines += [*draft.notes, ""] if draft.notes else []
    lines += _footer(draft)
    return "\n".join(lines).strip() + "\n"


def render_email(draft: Draft, rng: random.Random) -> str:
    """Wrap a draft into an e-mail, inline for letters and as-is for plain mail."""
    de = draft.language == "de"
    local = rng.choice(("buchhaltung", "rechnung", "info", "service")) if de else "billing"
    sender_mail = f"{local}@{draft.sender.email_domain or 'mail.de'}"
    recipient_mail = f"kreditoren@{draft.recipient.email_domain or 'mail.de'}"
    header = [
        f"{'Von' if de else 'From'}: {draft.sender.name} <{sender_mail}>",
        f"{'An' if de else 'To'}: {recipient_mail}",
        f"{'Betreff' if de else 'Subject'}: {draft.subject}",
        f"{'Datum' if de else 'Date'}: {draft.fields[0][1] if draft.fields else '15.09.2026'}",
        "",
    ]
    if draft.document_type == DocumentType.EMAIL:
        body = [*draft.paragraphs, draft.sender.name]
    else:
        intro = (
            "Sehr geehrte Damen und Herren,\n\nnachfolgend erhalten Sie unser Dokument "
            "im Textformat:"
            if de
            else "Dear Sir or Madam,\n\nplease find our document below:"
        )
        body = [intro, "", render_plain(draft)]
    return "\n".join(header + body).strip() + "\n"


def render_ocr(draft: Draft, rng: random.Random) -> str:
    """Simulate text recognition of a scan: letter errors, broken lines, stray marks.

    Digits stay untouched so that printed amounts keep their meaning.
    """
    noisy_lines = []
    for clean in render_plain(draft).splitlines():
        if any(ch.isdigit() for ch in clean) and rng.random() < 0.7:
            noisy_lines.append(clean)
            continue
        noisy = clean
        for source, target in OCR_SWAPS.items():
            if source in noisy and rng.random() < 0.25:
                noisy = noisy.replace(source, target, 1)
        if rng.random() < 0.08:
            noisy = noisy.replace(" ", "", 2)
        noisy_lines.append(noisy)
    merged: list[str] = []
    for line in noisy_lines:
        if merged and line and rng.random() < 0.1:
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return "\n".join(["~ Seite 1 von 1 ~  |", *merged, "|  .  ,"]) + "\n"


def render_table(draft: Draft) -> str:
    """Lay out a draft as a semicolon export from an accounting system."""
    lang = draft.language
    rows = [
        "Feld;Wert",
        f"Dokument;{draft.title or draft.subject}",
        f"Absender;{draft.sender.name}",
        f"Anschrift;{draft.sender.street}, {draft.sender.city}",
        f"Empfänger;{draft.recipient.name}",
    ]
    rows += [f"{label};{value}" for label, value in draft.fields]
    if draft.show_vat_id and draft.sender.vat_id:
        rows.append(f"USt-IdNr.;{draft.sender.vat_id}")
    if draft.show_bank and draft.sender.iban:
        rows.append(f"IBAN;{draft.sender.iban}")
    if draft.items:
        rows += ["", "Pos;Bezeichnung;Menge;Einheit;Einzelpreis;Netto"]
        rows += [
            f"{i};{item.description};{item.quantity};{item.unit};"
            f"{money(item.unit_price, lang)};{money(item.net, lang)}"
            for i, item in enumerate(draft.items, 1)
        ]
    if draft.amounts is not None:
        a = draft.amounts
        rows += [
            "",
            f"Netto;{money(a.net, lang)}",
            f"Steuersatz;{percent(a.tax_rate, lang)}",
            f"Steuer;{money(a.tax, lang)}",
            f"{draft.amount_label or 'Brutto'};{money(a.gross, lang)}",
        ]
    rows += ["", *(f"Text;{p}" for p in [*draft.paragraphs, *draft.notes])]
    return "\n".join(rows) + "\n"


def render_xrechnung(draft: Draft) -> str:
    """Lay out an invoice or credit note as an XRechnung in UBL syntax."""
    a = draft.amounts
    if a is None or draft.document_type not in XRECHNUNG_TYPES:
        return render_plain(draft)
    credit = draft.document_type == DocumentType.CREDIT_NOTE
    root = "CreditNote" if credit else "Invoice"
    number = next((v for k, v in draft.fields if "nummer" in k.lower()), "")
    printed_date = next((v for k, v in draft.fields if "datum" in k.lower()), "")
    issue = "-".join(reversed(printed_date.split("."))) if printed_date else ""
    seller_tax = (
        f"<cac:PartyTaxScheme><cbc:CompanyID>{draft.sender.vat_id}</cbc:CompanyID>"
        "<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>"
        if draft.show_vat_id and draft.sender.vat_id
        else ""
    )
    lines = "".join(
        f"<cac:{root}Line><cbc:ID>{i}</cbc:ID>"
        f'<cbc:{"Credited" if credit else "Invoiced"}Quantity unitCode="C62">{item.quantity}'
        f"</cbc:{'Credited' if credit else 'Invoiced'}Quantity>"
        f'<cbc:LineExtensionAmount currencyID="EUR">{item.net}</cbc:LineExtensionAmount>'
        f"<cac:Item><cbc:Name>{escape(item.description)}</cbc:Name></cac:Item>"
        f'<cac:Price><cbc:PriceAmount currencyID="EUR">{item.unit_price}</cbc:PriceAmount>'
        f"</cac:Price></cac:{root}Line>"
        for i, item in enumerate(draft.items, 1)
    )
    number_tag = f"<cbc:ID>{escape(number)}</cbc:ID>" if number else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<ubl:{root} xmlns:ubl="urn:oasis:names:specification:ubl:schema:xsd:{root}-2" '
        'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
        'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">\n'
        "<cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:"
        "xrechnung_3.0</cbc:CustomizationID>\n"
        f"{number_tag}<cbc:IssueDate>{escape(issue)}</cbc:IssueDate>"
        "<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>\n"
        f"<cac:AccountingSupplierParty><cac:Party><cac:PartyName><cbc:Name>"
        f"{escape(draft.sender.name)}</cbc:Name></cac:PartyName><cac:PostalAddress>"
        f"<cbc:StreetName>{escape(draft.sender.street)}</cbc:StreetName><cbc:CityName>"
        f"{escape(draft.sender.city)}</cbc:CityName></cac:PostalAddress>{seller_tax}"
        "</cac:Party></cac:AccountingSupplierParty>\n"
        f"<cac:AccountingCustomerParty><cac:Party><cac:PartyName><cbc:Name>"
        f"{escape(draft.recipient.name)}</cbc:Name></cac:PartyName></cac:Party>"
        "</cac:AccountingCustomerParty>\n"
        f"<cac:PaymentMeans><cac:PayeeFinancialAccount><cbc:ID>"
        f"{draft.sender.iban.replace(' ', '')}</cbc:ID></cac:PayeeFinancialAccount>"
        "</cac:PaymentMeans>\n"
        f'<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">{a.tax}</cbc:TaxAmount>'
        f'<cac:TaxSubtotal><cbc:TaxableAmount currencyID="EUR">{a.net}</cbc:TaxableAmount>'
        f'<cbc:TaxAmount currencyID="EUR">{a.tax}</cbc:TaxAmount><cac:TaxCategory>'
        f"<cbc:ID>S</cbc:ID><cbc:Percent>{a.tax_rate * 100:.0f}</cbc:Percent></cac:TaxCategory>"
        "</cac:TaxSubtotal></cac:TaxTotal>\n"
        f'<cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount currencyID="EUR">{a.net}'
        f'</cbc:TaxExclusiveAmount><cbc:TaxInclusiveAmount currencyID="EUR">{a.gross}'
        f'</cbc:TaxInclusiveAmount><cbc:PayableAmount currencyID="EUR">{a.gross}'
        "</cbc:PayableAmount></cac:LegalMonetaryTotal>\n"
        f"{lines}\n</ubl:{root}>\n"
    )


def render(draft: Draft, document_format: DocumentFormat, rng: random.Random) -> str:
    """Render a draft in the requested format.

    Args:
        draft: Content to lay out.
        document_format: Target format; ENGLISH is a language and uses the letter layout.
        rng: Random source for e-mail addresses and recognition noise.

    Returns:
        Document text.
    """
    if draft.document_type == DocumentType.EMAIL:
        return render_email(draft, rng)
    match document_format:
        case DocumentFormat.EMAIL:
            return render_email(draft, rng)
        case DocumentFormat.OCR:
            return render_ocr(draft, rng)
        case DocumentFormat.TABLE:
            return render_table(draft)
        case DocumentFormat.XRECHNUNG:
            return render_xrechnung(draft)
        case DocumentFormat.PLAIN | DocumentFormat.ENGLISH:
            return render_plain(draft)
