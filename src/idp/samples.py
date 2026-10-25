"""Three showcase documents for the public demo form.

Context: Embedded in the n8n form and written to samples/. |
Input: None. |
Output: Document texts keyed by form option.

The documents are fictitious test data. Company names are used for realism only; numbers,
tax IDs and bank details are invented.
"""

from __future__ import annotations

TELEKOM_INVOICE_NUMBER = "412 7781 30519"

TELEKOM = """\
Telekom Deutschland GmbH · Landgrabenweg 151 · 53227 Bonn

Kessler Maschinenbau GmbH
Industrieweg 5
48163 Münster

RECHNUNG (fiktives Testdokument)

Rechnungsnummer: 412 7781 30519
Rechnungsdatum: 02.10.2026
Leistungszeitraum: 01.09.2026 – 30.09.2026
Kundennummer: 5520 1984

Pos. Bezeichnung                          Menge    Einzelpreis      Gesamt
1    Business Mobil M, Grundgebühr            3        39,95 €     119,85 €
2    Zusätzliche SIM-Karte                    2         9,95 €      19,90 €
3    Roaming-Verbindungen EU                  1        12,40 €      12,40 €

Nettobetrag                                                       152,15 €
Umsatzsteuer 19 %                                                  28,91 €
Rechnungsbetrag                                                   181,06 €

Der Rechnungsbetrag wird am 16.10.2026 von Ihrem Konto abgebucht.
Hinweis: Ihr Tarif enthält ab November 5 GB zusätzliches Datenvolumen.

--------------------------------------------------------------------------
Telekom Deutschland GmbH · Landgrabenweg 151 · 53227 Bonn
USt-IdNr. DE811904217
Bankverbindung: IBAN DE31 3701 0050 0248 5865 05
"""

GLOBAL_AI = """\
Global AI Shapers Corp. · 1209 Orange Street · Wilmington, DE 19801, USA

Kessler Maschinenbau GmbH
Industrieweg 5
48163 Münster
Germany

INVOICE (fictitious test document)

Invoice number: GAS-2026-0917
Invoice date: 01 Oct 2026

Item Description                              Qty    Unit price          Total
1    AI strategy workshop (on site)              2   EUR 2,400.00   EUR 4,800.00
2    Prompt library licence, 12 months           1   EUR 1,200.00   EUR 1,200.00

Net amount                                        EUR 6,000.00
Tax                                                  EUR 0.00
Invoice total                                     EUR 6,000.00

Payment due within 5 days by wire transfer.
IMPORTANT: Our bank details have changed. Please use the new account below.

--------------------------------------------------------------------------
Global AI Shapers Corp. · Wilmington, Delaware
Bank details: IBAN US62 0210 0021 0000 4471 2290
"""

AWS = """\
Amazon Web Services EMEA SARL, Niederlassung Deutschland · Marcel-Breuer-Straße 12 · 80807 München

Kessler Maschinenbau GmbH
Industrieweg 5
48163 Münster

RECHNUNG (fiktives Testdokument)

Rechnungsnummer: EUINDE26-4471902
Rechnungsdatum: 03.10.2026
Leistungszeitraum: September 2026
Kontonummer: 7741 2290 1846

Pos. Bezeichnung                          Menge    Einzelpreis      Gesamt
1    Amazon EC2, Rechenleistung eu-central-1  1       612,40 €     612,40 €
2    Amazon S3, Speicher                      1        48,15 €      48,15 €
3    AWS Support Business                     1       100,00 €     100,00 €

Nettobetrag                                                       760,55 €
Umsatzsteuer 19 %                                                 144,50 €
Rechnungsbetrag                                                   914,05 €

Der Betrag wird Ihrer hinterlegten Kreditkarte belastet.

--------------------------------------------------------------------------
Amazon Web Services EMEA SARL, Niederlassung Deutschland · Marcel-Breuer-Straße 12 · 80807 München
USt-IdNr. DE317013094
Bankverbindung: IBAN DE32 7002 0270 0015 8409 26
"""

SHOWCASE: dict[str, tuple[str, str]] = {
    "telekom": ("Telekom – sauberer Durchlauf", TELEKOM),
    "global_ai": ("Global AI Shapers – unbekannter Absender", GLOBAL_AI),
    "aws": ("AWS – Rechenfehler", AWS),
}
CUSTOM_OPTION = "Eigener Text"
FRESH_NUMBER_SAMPLES: dict[str, str] = {SHOWCASE["telekom"][0]: TELEKOM_INVOICE_NUMBER}
"""Samples that get a new invoice number per submission, so the clean run stays bookable."""
