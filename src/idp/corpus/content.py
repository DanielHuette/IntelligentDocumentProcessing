"""Business content for each document type, independent of layout.

Context: Second stage of corpus generation; turns a document type and a business partner into a
draft. |
Input: Random source, partner, language. |
Output: Draft records.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from idp.domain import Amounts, DocumentType, Party, Vendor
from idp.vendors import BANK_PARTY, BUYER, VENDORS

CENT = Decimal("0.01")
STANDARD_RATE = Decimal("0.19")
REDUCED_RATE = Decimal("0.07")


@dataclass(frozen=True, slots=True)
class CatalogItem:
    """A product or service a supplier sells."""

    german: str
    english: str
    low: int
    high: int
    unit: str = "Stk"
    rate: Decimal = STANDARD_RATE


@dataclass(frozen=True, slots=True)
class LineItem:
    """One priced position on a document."""

    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal

    @property
    def net(self) -> Decimal:
        """Position total before tax."""
        return (self.quantity * self.unit_price).quantize(CENT, ROUND_HALF_UP)


@dataclass(slots=True)
class Draft:
    """Everything a renderer needs to lay out one document."""

    document_type: DocumentType
    language: str
    sender: Party
    recipient: Party
    title: str
    fields: list[tuple[str, str]]
    items: list[LineItem] = field(default_factory=list)
    show_prices: bool = True
    amounts: Amounts | None = None
    amount_label: str | None = None
    paragraphs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    show_vat_id: bool = True
    show_bank: bool = True
    subject: str = ""


CATALOG: dict[str, tuple[CatalogItem, ...]] = {
    "telecom": (
        CatalogItem(
            "Mobilfunk Business M, Grundgebühr", "Mobile Business M, base fee", 30, 45, "Monat"
        ),
        CatalogItem(
            "Festnetz und Internet CompanyFlex",
            "Landline and internet CompanyFlex",
            55,
            90,
            "Monat",
        ),
        CatalogItem("Roaming-Verbindungen EU", "EU roaming connections", 4, 25, "pauschal"),
        CatalogItem("Zusätzliche SIM-Karte", "Additional SIM card", 5, 12, "Monat"),
    ),
    "cloud": (
        CatalogItem(
            "Amazon EC2, Rechenleistung eu-central-1",
            "Amazon EC2 compute eu-central-1",
            180,
            900,
            "pauschal",
        ),
        CatalogItem("Amazon S3, Speicher", "Amazon S3 storage", 20, 140, "pauschal"),
        CatalogItem(
            "Amazon RDS, Datenbankinstanz", "Amazon RDS database instance", 90, 420, "pauschal"
        ),
        CatalogItem("AWS Support Business", "AWS Business Support", 100, 160, "Monat"),
    ),
    "office": (
        CatalogItem("Kopierpapier A4, 80 g, Karton", "Copy paper A4 80 g, box", 22, 34, "Karton"),
        CatalogItem("Toner schwarz HL-L8360", "Black toner HL-L8360", 70, 120),
        CatalogItem("Ordner breit, blau", "Lever arch file, blue", 2, 4),
        CatalogItem("Bürostuhl ergonomisch", "Ergonomic office chair", 240, 480),
    ),
    "logistics": (
        CatalogItem(
            "Palettentransport Münster–Stuttgart",
            "Pallet freight Münster–Stuttgart",
            180,
            420,
            "Fahrt",
        ),
        CatalogItem("Lagermiete Stellplatz", "Warehouse slot rental", 18, 30, "Platz"),
        CatalogItem("Expresszuschlag", "Express surcharge", 35, 90, "pauschal"),
    ),
    "it_service": (
        CatalogItem(
            "Wartungsvertrag Server, Monatspauschale",
            "Server maintenance, monthly fee",
            290,
            650,
            "Monat",
        ),
        CatalogItem("Technikereinsatz vor Ort", "On-site technician", 85, 125, "Std"),
        CatalogItem("Firewall-Lizenz Verlängerung", "Firewall licence renewal", 380, 900),
    ),
    "energy": (
        CatalogItem(
            "Strom Gewerbe, Arbeitspreis",
            "Commercial electricity, energy charge",
            1400,
            5200,
            "pauschal",
        ),
        CatalogItem("Grundpreis Zählpunkt", "Meter point base charge", 15, 40, "Monat"),
    ),
    "vehicles": (
        CatalogItem("Inspektion Transporter", "Van inspection", 320, 780),
        CatalogItem("Winterreifen inkl. Montage", "Winter tyres incl. fitting", 520, 980, "Satz"),
        CatalogItem("Leasingrate Firmenwagen", "Company car lease instalment", 390, 690, "Monat"),
    ),
    "cleaning": (
        CatalogItem(
            "Unterhaltsreinigung Büroflächen", "Regular office cleaning", 900, 1900, "Monat"
        ),
        CatalogItem("Glasreinigung Fassade", "Facade window cleaning", 300, 750, "pauschal"),
    ),
    "tax_advice": (
        CatalogItem("Finanzbuchhaltung Monat", "Monthly bookkeeping", 450, 900, "Monat"),
        CatalogItem("Lohnabrechnung je Mitarbeiter", "Payroll per employee", 18, 30, "MA"),
        CatalogItem("Beratung Umsatzsteuer", "VAT consulting", 140, 220, "Std"),
    ),
    "software": (
        CatalogItem("ERP-Lizenz Professional", "ERP licence Professional", 59, 99, "Nutzer"),
        CatalogItem("Implementierung Schnittstelle", "Interface implementation", 110, 160, "Std"),
    ),
    "printing": (
        CatalogItem(
            "Produktkatalog 48 Seiten, 4/4-farbig", "Product catalogue 48 pages", 2, 5, "Stk"
        ),
        CatalogItem("Visitenkarten 350 g", "Business cards 350 g", 30, 60, "500 Stk"),
        CatalogItem("Messeplakat A0", "Trade fair poster A0", 25, 60),
    ),
    "rent": (
        CatalogItem(
            "Miete Lagerhalle Hammer Straße", "Warehouse rent Hammer Straße", 2800, 4600, "Monat"
        ),
        CatalogItem("Nebenkostenvorauszahlung", "Service charge prepayment", 350, 700, "Monat"),
    ),
    "tools": (
        CatalogItem("Akku-Bohrschrauber 18 V", "Cordless drill 18 V", 160, 320),
        CatalogItem("Messschieber digital", "Digital caliper", 45, 120),
        CatalogItem("HSS-Bohrer-Set 25-tlg.", "HSS drill set, 25 pieces", 40, 95, "Set"),
    ),
    "catering": (
        CatalogItem(
            "Mittagessen Kantine, Lieferung",
            "Canteen lunch delivery",
            7,
            12,
            "Portion",
            REDUCED_RATE,
        ),
        CatalogItem(
            "Brötchenplatte Besprechung",
            "Sandwich platter for meeting",
            35,
            70,
            "Platte",
            REDUCED_RATE,
        ),
    ),
    "paper": (
        CatalogItem("Wellpappe Kartonagen 600x400", "Corrugated boxes 600x400", 1, 3),
        CatalogItem("Stretchfolie 500 mm", "Stretch film 500 mm", 12, 25, "Rolle"),
        CatalogItem("Packpapier Rolle 75 m", "Wrapping paper roll 75 m", 18, 40, "Rolle"),
    ),
    "unknown": (
        CatalogItem("Beratungsleistung", "Consulting services", 120, 180, "Std"),
        CatalogItem(
            "Installation und Material", "Installation and material", 400, 2400, "pauschal"
        ),
        CatalogItem("KI-Strategie-Workshop", "AI strategy workshop", 1500, 4800, "Tag"),
    ),
}

GERMAN_MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


def money(value: Decimal, language: str) -> str:
    """Format an amount the way it is printed in the given language."""
    text = f"{value:,.2f}"
    if language == "de":
        return text.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    return "EUR " + text


def day(value: date, language: str) -> str:
    """Format a date as printed in the given language."""
    return value.strftime("%d.%m.%Y") if language == "de" else value.strftime("%d %b %Y")


def percent(rate: Decimal, language: str) -> str:
    """Format a tax rate fraction as percent."""
    whole = f"{rate * 100:.0f} %"
    return whole if language == "de" else whole.replace(" ", "")


def compute_amounts(items: list[LineItem], rate: Decimal) -> Amounts:
    """Compute correct totals for priced positions."""
    net = sum((item.net for item in items), Decimal("0.00"))
    tax = (net * rate).quantize(CENT, ROUND_HALF_UP)
    return Amounts(net=net, tax_rate=rate, tax=tax, gross=net + tax)


class ContentFactory:
    """Creates drafts for every document type from one seeded random source."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def random_date(self) -> date:
        """Pick a document date in the third quarter of 2026."""
        return date(2026, 7, 1) + timedelta(days=self._rng.randrange(92))

    def pick_items(self, trade: str, language: str, count: int | None = None) -> list[LineItem]:
        """Draw priced positions from a trade catalog."""
        catalog = CATALOG[trade]
        size = count or self._rng.randint(1, min(3, len(catalog)))
        chosen = self._rng.sample(catalog, size)
        items = []
        for entry in chosen:
            quantity = Decimal(self._rng.choice((1, 1, 1, 2, 3, 5, 10, 12, 20)))
            if entry.unit in ("Monat", "pauschal", "Fahrt"):
                quantity = Decimal(1)
            cents = self._rng.randint(entry.low * 100, entry.high * 100)
            items.append(
                LineItem(
                    description=entry.german if language == "de" else entry.english,
                    quantity=quantity,
                    unit=entry.unit,
                    unit_price=Decimal(cents) / 100,
                )
            )
        return items

    def rate_for(self, trade: str) -> Decimal:
        """Tax rate a trade charges."""
        return REDUCED_RATE if trade == "catering" else STANDARD_RATE

    def invoice_number(self, vendor_key: str) -> str:
        """Create a vendor-specific invoice number pattern."""
        n = self._rng.randint(10000, 99999)
        patterns = {
            "telekom": f"{self._rng.randint(100, 999)} {self._rng.randint(1000, 9999)} {n}",
            "aws": f"EUINDE26-{n}{self._rng.randint(10, 99)}",
        }
        return patterns.get(
            vendor_key, self._rng.choice((f"RE-2026-{n}", f"2026{n}", f"R{n}/26", f"INV-{n}"))
        )

    def invoice(self, sender: Party, trade: str, language: str) -> tuple[Draft, str]:
        """Draft a correct invoice; defects are applied by the generator."""
        number = self.invoice_number(_key_of(sender))
        issued = self.random_date()
        items = self.pick_items(trade, language)
        amounts = compute_amounts(items, self.rate_for(trade))
        de = language == "de"
        period = issued.replace(day=1) - timedelta(days=1)
        fields = [
            ("Rechnungsnummer" if de else "Invoice number", number),
            ("Rechnungsdatum" if de else "Invoice date", day(issued, language)),
            (
                "Leistungszeitraum" if de else "Service period",
                f"{GERMAN_MONTHS[period.month - 1]} 2026" if de else f"{period:%B} 2026",
            ),
            ("Kundennummer" if de else "Customer number", str(self._rng.randint(100000, 999999))),
        ]
        due = issued + timedelta(days=self._rng.choice((14, 30)))
        paragraphs = [
            (
                f"Bitte überweisen Sie den Rechnungsbetrag bis zum {day(due, language)}."
                if de
                else f"Please pay the invoice amount by {day(due, language)}."
            ),
        ]
        draft = Draft(
            DocumentType.INVOICE,
            language,
            sender,
            BUYER,
            "Rechnung" if de else "Invoice",
            fields,
            items,
            True,
            amounts,
            None,
            paragraphs,
            self.optional_notes(language),
            subject=f"Rechnung {number}" if de else f"Invoice {number}",
        )
        return draft, number

    def optional_notes(self, language: str) -> list[str]:
        """Unstructured remarks that a summary should separate from the facts."""
        de_notes = (
            "Hinweis: Unsere Bankverbindung hat sich nicht geändert.",
            "Bitte geben Sie bei Zahlung die Rechnungsnummer an.",
            "Lieferung erfolgte an Tor 3, Annahme durch Hr. Wolters.",
            "Betriebsferien vom 23.12. bis 02.01.",
            "Rückfragen gern an buchhaltung@ unter Angabe der Kundennummer.",
        )
        en_notes = (
            "Please quote the invoice number with your payment.",
            "Delivered to gate 3, received by Mr Wolters.",
            "Our office is closed from 23 Dec to 2 Jan.",
        )
        pool = de_notes if language == "de" else en_notes
        return self._rng.sample(pool, self._rng.randint(0, 2))

    def credit_note(self, vendor: Vendor, language: str) -> Draft:
        """Draft a credit note that refers to an earlier invoice."""
        items = self.pick_items(vendor.trade, language, 1)
        amounts = compute_amounts(items, self.rate_for(vendor.trade))
        de = language == "de"
        ref = self.invoice_number(vendor.key)
        number = f"GS-{self._rng.randint(1000, 9999)}"
        return Draft(
            DocumentType.CREDIT_NOTE,
            language,
            vendor.party,
            BUYER,
            "Gutschrift" if de else "Credit note",
            [
                ("Gutschriftsnummer" if de else "Credit note number", number),
                ("Datum" if de else "Date", day(self.random_date(), language)),
                ("Bezug Rechnung" if de else "Related invoice", ref),
            ],
            items,
            True,
            amounts,
            "Gutschriftsbetrag" if de else "Credit amount",
            [
                (
                    "Aufgrund Ihrer Reklamation schreiben wir Ihnen folgenden Betrag gut. "
                    "Die Verrechnung erfolgt mit der nächsten Rechnung."
                )
                if de
                else "Following your complaint we credit the amount below to your account."
            ],
            subject=f"Gutschrift {number}" if de else f"Credit note {number}",
        )

    def payment_reminder(self, vendor: Vendor, language: str) -> Draft:
        """Draft a dunning letter about an unpaid invoice."""
        de = language == "de"
        ref = self.invoice_number(vendor.key)
        open_amount = Decimal(self._rng.randint(8000, 480000)) / 100
        level = self._rng.choice(("Zahlungserinnerung", "1. Mahnung", "2. Mahnung"))
        title = level if de else self._rng.choice(("Payment reminder", "Final reminder"))
        text = (
            f"bei Durchsicht unserer Konten haben wir festgestellt, dass unsere Rechnung {ref} "
            f"über {money(open_amount, language)} noch offen ist. Bitte begleichen Sie den Betrag "
            "innerhalb von 7 Tagen. Sollten Sie die Zahlung bereits veranlasst haben, betrachten "
            "Sie dieses Schreiben als gegenstandslos."
            if de
            else f"our records show that invoice {ref} for {money(open_amount, language)} is still "
            "outstanding. Please settle the amount within 7 days."
        )
        fee = ["Mahngebühr: 5,00 €"] if de and level == "2. Mahnung" else []
        return Draft(
            DocumentType.PAYMENT_REMINDER,
            language,
            vendor.party,
            BUYER,
            title,
            [
                ("Datum" if de else "Date", day(self.random_date(), language)),
                ("Offene Rechnung" if de else "Open invoice", ref),
            ],
            paragraphs=[
                ("Sehr geehrte Damen und Herren," if de else "Dear Sir or Madam,"),
                text,
                *fee,
            ],
            subject=f"{title} zu Rechnung {ref}" if de else f"{title}: invoice {ref}",
        )

    def delivery_note(self, vendor: Vendor, language: str) -> Draft:
        """Draft a delivery note without prices."""
        de = language == "de"
        number = f"LS-{self._rng.randint(100000, 999999)}"
        return Draft(
            DocumentType.DELIVERY_NOTE,
            language,
            vendor.party,
            BUYER,
            "Lieferschein" if de else "Delivery note",
            [
                ("Lieferschein-Nr." if de else "Delivery note no.", number),
                ("Lieferdatum" if de else "Delivery date", day(self.random_date(), language)),
                ("Ihre Bestellung" if de else "Your order", f"B-{self._rng.randint(1000, 9999)}"),
            ],
            self.pick_items(vendor.trade, language),
            False,
            paragraphs=[
                "Ware vollständig und unbeschädigt erhalten: ______ (Unterschrift)"
                if de
                else "Goods received complete and undamaged: ______"
            ],
            show_bank=False,
            subject=f"Lieferschein {number}" if de else f"Delivery {number}",
        )

    def quote(self, sender: Party, trade: str, language: str) -> Draft:
        """Draft a quote with prices but no payment request."""
        de = language == "de"
        items = self.pick_items(trade, language)
        amounts = compute_amounts(items, self.rate_for(trade))
        number = f"AN-{self._rng.randint(10000, 99999)}"
        valid = self.random_date() + timedelta(days=30)
        return Draft(
            DocumentType.QUOTE,
            language,
            sender,
            BUYER,
            "Angebot" if de else "Quotation",
            [
                ("Angebotsnummer" if de else "Quote number", number),
                ("Gültig bis" if de else "Valid until", day(valid, language)),
            ],
            items,
            True,
            amounts,
            "Angebotssumme" if de else "Quoted total",
            [
                "Vielen Dank für Ihre Anfrage. Gern bieten wir Ihnen an:"
                if de
                else "Thank you for your enquiry. We are pleased to offer:"
            ],
            subject=f"Angebot {number}" if de else f"Quotation {number}",
        )

    def purchase_order(self, vendor: Vendor, language: str) -> Draft:
        """Draft a purchase order sent by the buyer."""
        de = language == "de"
        number = f"B-2026-{self._rng.randint(1000, 9999)}"
        items = self.pick_items(vendor.trade, language)
        return Draft(
            DocumentType.PURCHASE_ORDER,
            language,
            BUYER,
            vendor.party,
            "Bestellung" if de else "Purchase order",
            [
                ("Bestellnummer" if de else "Order number", number),
                ("Bestelldatum" if de else "Order date", day(self.random_date(), language)),
                ("Liefertermin" if de else "Delivery date", "KW 44" if de else "week 44"),
            ],
            items,
            True,
            compute_amounts(items, self.rate_for(vendor.trade)),
            "Bestellwert" if de else "Order value",
            [
                "Bitte bestätigen Sie den Auftrag schriftlich."
                if de
                else "Please confirm this order in writing."
            ],
            show_bank=False,
            subject=f"Bestellung {number}" if de else f"Order {number}",
        )

    def order_confirmation(self, vendor: Vendor, language: str) -> Draft:
        """Draft an order confirmation from the supplier."""
        de = language == "de"
        items = self.pick_items(vendor.trade, language)
        return Draft(
            DocumentType.ORDER_CONFIRMATION,
            language,
            vendor.party,
            BUYER,
            "Auftragsbestätigung" if de else "Order confirmation",
            [
                (
                    "Auftragsnummer" if de else "Order number",
                    f"AB-{self._rng.randint(10000, 99999)}",
                ),
                (
                    "Ihre Bestellung" if de else "Your order",
                    f"B-2026-{self._rng.randint(1000, 9999)}",
                ),
                (
                    "Voraussichtliche Lieferung" if de else "Expected delivery",
                    day(self.random_date(), language),
                ),
            ],
            items,
            True,
            compute_amounts(items, self.rate_for(vendor.trade)),
            "Auftragswert" if de else "Order value",
            [
                "Wir bedanken uns für Ihren Auftrag und bestätigen ihn wie folgt. Die Rechnung "
                "erhalten Sie nach Lieferung."
                if de
                else "Thank you for your order, which we confirm as follows. You will be invoiced "
                "after delivery."
            ],
            subject="Auftragsbestätigung" if de else "Order confirmation",
        )

    def contract(self, vendor: Vendor, language: str) -> Draft:
        """Draft a contract excerpt."""
        de = language == "de"
        fee = money(Decimal(self._rng.randint(20000, 300000)) / 100, language)
        clauses = [
            f"§ 1 Vertragsgegenstand: {vendor.party.name} erbringt für die Kessler Maschinenbau "
            "GmbH Leistungen gemäß Anlage 1."
            if de
            else f"1. Subject: {vendor.party.name} provides services to Kessler Maschinenbau GmbH "
            "as described in Annex 1.",
            f"§ 2 Vergütung: Die monatliche Pauschale beträgt {fee} zuzüglich gesetzlicher "
            "Umsatzsteuer. Die Abrechnung erfolgt monatlich."
            if de
            else f"2. Fees: The monthly flat fee is {fee} plus statutory VAT, invoiced monthly.",
            "§ 3 Laufzeit: Der Vertrag beginnt am 01.10.2026 und läuft 24 Monate. Er verlängert "
            "sich um jeweils 12 Monate, wenn er nicht drei Monate vor Ablauf gekündigt wird."
            if de
            else "3. Term: 24 months from 1 Oct 2026, renewing by 12 months unless "
            "terminated with three months' notice.",
            "§ 4 Haftung: Die Haftung ist auf Vorsatz und grobe Fahrlässigkeit beschränkt."
            if de
            else "4. Liability is limited to intent and gross negligence.",
        ]
        return Draft(
            DocumentType.CONTRACT,
            language,
            vendor.party,
            BUYER,
            self._rng.choice(("Rahmenvertrag", "Wartungsvertrag", "Dienstleistungsvertrag"))
            if de
            else "Service agreement",
            [
                ("Vertragsnummer" if de else "Contract number", f"V-{self._rng.randint(100, 999)}"),
                ("Stand" if de else "Version", day(self.random_date(), language)),
            ],
            paragraphs=[
                *clauses,
                "Ort, Datum, Unterschriften beider Parteien"
                if de
                else "Place, date, signatures of both parties",
            ],
            show_bank=False,
            subject="Vertrag zur Unterschrift" if de else "Agreement for signature",
        )

    def termination(self, vendor: Vendor, language: str) -> Draft:
        """Draft a termination notice in either direction."""
        de = language == "de"
        from_buyer = self._rng.random() < 0.5
        sender, recipient = (BUYER, vendor.party) if from_buyer else (vendor.party, BUYER)
        text = (
            f"hiermit kündigen wir den Vertrag Nr. V-{self._rng.randint(100, 999)} fristgerecht "
            "zum 31.12.2026. Bitte bestätigen Sie uns den Eingang dieser Kündigung schriftlich."
            if de
            else f"we hereby terminate contract no. V-{self._rng.randint(100, 999)} with effect "
            "from 31 Dec 2026. Please confirm receipt in writing."
        )
        return Draft(
            DocumentType.TERMINATION,
            language,
            sender,
            recipient,
            "Kündigung" if de else "Notice of termination",
            [("Datum" if de else "Date", day(self.random_date(), language))],
            paragraphs=[
                "Sehr geehrte Damen und Herren," if de else "Dear Sir or Madam,",
                text,
                "Mit freundlichen Grüßen" if de else "Kind regards",
            ],
            show_bank=False,
            subject="Kündigung" if de else "Termination",
        )

    def receipt(self, language: str) -> Draft:
        """Draft a small expense receipt from a business without master data entry."""
        de = language == "de"
        shops = (
            ("Taxi Zentrale Münster eG", "Fahrt Hbf – Industrieweg", REDUCED_RATE),
            ("Hotel am Prinzipalmarkt", "Übernachtung Einzelzimmer", REDUCED_RATE),
            ("Aral Tankstelle Weseler Straße", "Super E10, 48,2 l", STANDARD_RATE),
            ("Parkhaus Theater Münster", "Parkgebühr 3 Std.", STANDARD_RATE),
            ("Restaurant Pinkus", "Bewirtung Geschäftsessen", STANDARD_RATE),
        )
        shop, item, rate = self._rng.choice(shops)
        gross = Decimal(self._rng.randint(800, 18000)) / 100
        net = (gross / (1 + rate)).quantize(CENT, ROUND_HALF_UP)
        party = Party(shop, "Münster", "48143 Münster", None, "", "")
        return Draft(
            DocumentType.RECEIPT,
            language,
            party,
            BUYER,
            "Quittung" if de else "Receipt",
            [
                ("Beleg-Nr." if de else "Receipt no.", str(self._rng.randint(1000, 99999))),
                ("Datum" if de else "Date", day(self.random_date(), language)),
            ],
            [LineItem(item, Decimal(1), "", gross)],
            True,
            Amounts(net, rate, gross - net, gross),
            "Summe bar" if de else "Total paid",
            ["Betrag dankend erhalten." if de else "Paid with thanks."],
            show_vat_id=False,
            show_bank=False,
            subject="Beleg" if de else "Receipt",
        )

    def bank_statement(self, language: str) -> Draft:
        """Draft a statement whose movements mention several suppliers."""
        de = language == "de"
        lines = []
        for vendor in self._rng.sample(VENDORS, 4):
            amount = money(Decimal(self._rng.randint(5000, 400000)) / 100, language)
            lines.append(
                f"{day(self.random_date(), language)}  "
                f"{'Überweisung an' if de else 'Transfer to'} {vendor.party.name}  "
                f"-{amount}"
            )
        lines.append(
            f"{day(self.random_date(), language)}  "
            f"{'Gutschrift Kunde' if de else 'Customer payment'} Brandt Anlagenbau  "
            f"+{money(Decimal(self._rng.randint(100000, 900000)) / 100, language)}"
        )
        return Draft(
            DocumentType.BANK_STATEMENT,
            language,
            BANK_PARTY,
            BUYER,
            "Kontoauszug" if de else "Account statement",
            [
                ("Auszug" if de else "Statement", f"{self._rng.randint(1, 52)}/2026"),
                ("IBAN", BUYER.iban),
            ],
            paragraphs=lines,
            show_vat_id=False,
            show_bank=False,
            subject="Ihr elektronischer Kontoauszug" if de else "Your account statement",
        )

    def email(self, sender: Party, language: str) -> Draft:
        """Draft a plain business e-mail without a bookable document."""
        de = language == "de"
        topics_de = (
            "wir möchten den Liefertermin für Ihre Bestellung auf Donnerstag verschieben. "
            "Passt Ihnen das?",
            "anbei wie besprochen unser aktueller Produktkatalog als Link. Melden Sie sich gern "
            "bei Fragen.",
            "ich bin bis einschließlich Freitag nicht im Büro. In dringenden Fällen wenden Sie "
            "sich bitte an unsere Zentrale.",
            "können Sie uns bitte eine aktualisierte Ansprechpartnerliste für die Buchhaltung "
            "senden?",
            "zur Abstimmung des Jahresgesprächs schlage ich den 14. November um 10 Uhr vor.",
        )
        topics_en = (
            "could we move the delivery of your order to Thursday?",
            "I am out of the office until Friday. For urgent matters please call our main line.",
            "please send us an updated contact list for your accounts department.",
        )
        body = self._rng.choice(topics_de if de else topics_en)
        return Draft(
            DocumentType.EMAIL,
            language,
            sender,
            BUYER,
            "",
            [],
            paragraphs=[
                "Guten Tag," if de else "Hello,",
                body,
                "Viele Grüße" if de else "Best regards",
            ],
            show_vat_id=False,
            show_bank=False,
            subject=self._rng.choice(("Kurze Rückfrage", "Termin", "Abwesenheit", "Info"))
            if de
            else "Quick question",
        )

    def fraudulent_invoice(self, sender: Party, language: str) -> Draft:
        """Draft a directory-listing scam laid out like an invoice."""
        de = language == "de"
        gross = Decimal(self._rng.choice((890, 958, 1149, 1290, 1490))) + Decimal("0.00")
        number = f"{self._rng.randint(100000, 999999)}"
        return Draft(
            DocumentType.FRAUDULENT_INVOICE,
            language,
            sender,
            BUYER,
            "Rechnung / Eintragungsofferte" if de else "Invoice / Registration offer",
            [
                ("Vorgangsnummer" if de else "Reference", number),
                ("Fällig" if de else "Due", "sofort" if de else "immediately"),
            ],
            [
                LineItem(
                    "Eintragung Gewerbeverzeichnis, Laufzeit 3 Jahre"
                    if de
                    else "Business directory listing, 3 years",
                    Decimal(1),
                    "",
                    gross,
                )
            ],
            True,
            None,
            "Zu zahlen" if de else "Amount due",
            [
                "Bitte überweisen Sie den Betrag umgehend, um die Löschung Ihres Eintrags zu "
                "vermeiden."
                if de
                else "Pay immediately to avoid removal of your listing.",
                "Kleingedrucktes: Dies ist ein Angebot. Mit Zahlung kommt ein Vertrag über drei "
                "Jahre zustande. Keine Verbindung zu öffentlichen Registern."
                if de
                else "Small print: this is an offer. Payment creates a three-year contract.",
            ],
            show_vat_id=False,
            subject=f"Rechnung {number} – sofort fällig"
            if de
            else f"Invoice {number} - due immediately",
        )


def _key_of(party: Party) -> str:
    for vendor in VENDORS:
        if vendor.party == party:
            return vendor.key
    return "other"
