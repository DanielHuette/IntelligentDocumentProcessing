"""Supplier master data and parties used by the corpus.

Context: The buying company knows 15 suppliers; everything else counts as unknown. |
Input: None. |
Output: Vendor and party records.

All companies except Telekom Deutschland and Amazon Web Services are fictitious. Every VAT ID
and IBAN is invented for testing and does not belong to a real account.
"""

from __future__ import annotations

from idp.domain import Party, Vendor


def german_iban(bank_code: str, account: str) -> str:
    """Build a German IBAN with a valid ISO 13616 check number.

    Args:
        bank_code: Eight-digit German bank code.
        account: Account number, padded to ten digits.

    Returns:
        IBAN in groups of four characters.

    Raises:
        ValueError: If the bank code or account is not numeric or too long.
    """
    if not (bank_code.isdigit() and len(bank_code) == 8):
        raise ValueError(f"bank code must have 8 digits: {bank_code!r}")
    if not (account.isdigit() and len(account) <= 10):
        raise ValueError(f"account must have up to 10 digits: {account!r}")
    bban = bank_code + account.zfill(10)
    check = 98 - int(bban + "131400") % 97
    raw = f"DE{check:02d}{bban}"
    return " ".join(raw[i : i + 4] for i in range(0, len(raw), 4))


BUYER = Party(
    name="Kessler Maschinenbau GmbH",
    street="Industrieweg 5",
    city="48163 Münster",
    vat_id="DE318204957",
    iban=german_iban("40050150", "77120345"),
    email_domain="kessler-maschinenbau.de",
)


def _vendor(
    key: str,
    trade: str,
    *,
    name: str,
    street: str,
    city: str,
    vat_id: str,
    bank: tuple[str, str],
    domain: str,
) -> Vendor:
    return Vendor(
        key=key,
        trade=trade,
        party=Party(name, street, city, vat_id, german_iban(*bank), domain),
    )


VENDORS: tuple[Vendor, ...] = (
    _vendor(
        "telekom",
        "telecom",
        name="Telekom Deutschland GmbH",
        street="Landgrabenweg 151",
        city="53227 Bonn",
        vat_id="DE811904217",
        bank=("37010050", "248586505"),
        domain="telekom.de",
    ),
    _vendor(
        "aws",
        "cloud",
        name="Amazon Web Services EMEA SARL, Niederlassung Deutschland",
        street="Marcel-Breuer-Straße 12",
        city="80807 München",
        vat_id="DE317013094",
        bank=("70020270", "15840926"),
        domain="aws.amazon.com",
    ),
    _vendor(
        "brenner",
        "office",
        name="Brenner Bürobedarf GmbH",
        street="Hafenweg 12",
        city="48155 Münster",
        vat_id="DE291847366",
        bank=("40050150", "33904417"),
        domain="brenner-buero.de",
    ),
    _vendor(
        "westfalen_logistik",
        "logistics",
        name="Westfalen Logistik Kühn KG",
        street="Speicherstraße 40",
        city="44147 Dortmund",
        vat_id="DE276103958",
        bank=("44050199", "61839204"),
        domain="wl-kuehn.de",
    ),
    _vendor(
        "lindner_it",
        "it_service",
        name="Lindner IT-Service GmbH",
        street="Am Kanonengraben 3",
        city="48151 Münster",
        vat_id="DE305572814",
        bank=("40060265", "99210384"),
        domain="lindner-it.de",
    ),
    _vendor(
        "ems_energie",
        "energy",
        name="Ems-Energie Versorgung GmbH",
        street="Werkstraße 7",
        city="48268 Greven",
        vat_id="DE284019375",
        bank=("40351060", "72005531"),
        domain="ems-energie.de",
    ),
    _vendor(
        "autohaus_hesse",
        "vehicles",
        name="Autohaus Hesse GmbH & Co. KG",
        street="Industriestraße 88",
        city="48599 Gronau",
        vat_id="DE213958604",
        bank=("40154530", "31007729"),
        domain="autohaus-hesse.de",
    ),
    _vendor(
        "klar_reinigung",
        "cleaning",
        name="Klar Gebäudereinigung GmbH",
        street="Albersloher Weg 210",
        city="48167 Münster",
        vat_id="DE299384710",
        bank=("40050150", "48120936"),
        domain="klar-reinigung.de",
    ),
    _vendor(
        "kanzlei_moeller",
        "tax_advice",
        name="Steuerkanzlei Möller & Partner mbB",
        street="Ludgeristraße 55",
        city="48143 Münster",
        vat_id="DE267731049",
        bank=("40060000", "20583317"),
        domain="kanzlei-moeller.de",
    ),
    _vendor(
        "cloudwerk",
        "software",
        name="Cloudwerk Software GmbH",
        street="Torstraße 140",
        city="10119 Berlin",
        vat_id="DE322190486",
        bank=("10070000", "84422190"),
        domain="cloudwerk.io",
    ),
    _vendor(
        "druckerei_hansen",
        "printing",
        name="Druckerei Hansen e.K.",
        street="Nordstraße 9",
        city="49477 Ibbenbüren",
        vat_id="DE258830172",
        bank=("40351060", "16620048"),
        domain="druck-hansen.de",
    ),
    _vendor(
        "vogt_immobilien",
        "rent",
        name="Vogt Immobilien & Gewerbevermietung GmbH",
        street="Hammer Straße 300",
        city="48153 Münster",
        vat_id="DE281164093",
        bank=("40050150", "55100872"),
        domain="vogt-immobilien.de",
    ),
    _vendor(
        "stahlmann",
        "tools",
        name="Stahlmann Werkzeughandel GmbH",
        street="Ruhrallee 17",
        city="45138 Essen",
        vat_id="DE249906618",
        bank=("36050105", "27394410"),
        domain="stahlmann-werkzeug.de",
    ),
    _vendor(
        "feldkueche",
        "catering",
        name="Feldküche Catering GmbH",
        street="Hansaring 61",
        city="48155 Münster",
        vat_id="DE313347722",
        bank=("40050150", "90011843"),
        domain="feldkueche-catering.de",
    ),
    _vendor(
        "nordpapier",
        "paper",
        name="Nordpapier Großhandel GmbH",
        street="Überseering 8",
        city="22297 Hamburg",
        vat_id="DE266058831",
        bank=("20050550", "12398870"),
        domain="nordpapier.de",
    ),
)

VENDORS_BY_KEY: dict[str, Vendor] = {vendor.key: vendor for vendor in VENDORS}

UNKNOWN_PARTIES: tuple[Party, ...] = (
    Party(
        "Global AI Shapers Corp.",
        "1209 Orange Street",
        "Wilmington, DE 19801, USA",
        None,
        "US62 0210 0021 0000 4471 2290",
        "globalaishapers.ai",
    ),
    Party(
        "Kaminski Haustechnik GmbH",
        "Weseler Straße 412",
        "48163 Münster",
        "DE297750413",
        german_iban("40050150", "61207718"),
        "kaminski-haustechnik.de",
    ),
    Party(
        "Bergmann Elektro OHG",
        "Zechenstraße 21",
        "45772 Marl",
        "DE245519806",
        german_iban("42650150", "30098115"),
        "bergmann-elektro.de",
    ),
    Party(
        "Nexora Digital Ltd",
        "71 Shelton Street",
        "London WC2H 9JQ, United Kingdom",
        None,
        "GB29 NWBK 6016 1331 9268 19",
        "nexora-digital.co.uk",
    ),
    Party(
        "Saxonia Fenster GmbH",
        "Pirnaer Landstraße 90",
        "01237 Dresden",
        "DE287712340",
        german_iban("85050300", "41188920"),
        "saxonia-fenster.de",
    ),
    Party(
        "Rheinfeld Consulting UG",
        "Mittelstraße 4",
        "50672 Köln",
        "DE331804726",
        german_iban("37050198", "19920355"),
        "rheinfeld-consulting.de",
    ),
)

SCAM_PARTIES: tuple[Party, ...] = (
    Party(
        "Zentrales Gewerbe-Register DE",
        "Postfach 1104",
        "1010 Wien, Österreich",
        None,
        "AT48 3200 0000 1234 5864",
        "gewerbe-register-zentral.com",
    ),
    Party(
        "Deutsches Firmenverzeichnis Online",
        "Calle Mayor 8",
        "29601 Marbella, Spanien",
        None,
        "ES91 2100 0418 4502 0005 1332",
        "firmenverzeichnis-de.net",
    ),
    Party(
        "Euro Patent & Marken Service",
        "Rue du Marché 17",
        "1204 Genf, Schweiz",
        None,
        "CH93 0076 2011 6238 5295 7",
        "euro-marken-service.org",
    ),
    Party(
        "Domain Registry Services Europe",
        "Strada Mare 22",
        "Bukarest, Rumänien",
        None,
        "RO49 AAAA 1B31 0075 9384 0000",
        "domain-registry-eu.info",
    ),
)

BANK_PARTY = Party(
    "Sparkasse Münsterland Ost",
    "Weseler Straße 230",
    "48151 Münster",
    None,
    BUYER.iban,
    "sparkasse-mslo.de",
)
