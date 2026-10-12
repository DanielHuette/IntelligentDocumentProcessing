# Arbeitsbericht

[English version](REFACTORING_REPORT.md)

## Bauentscheidungen
**Context:** Neues Projekt, gebaut am 8. und 9. Oktober 2026. | **Input:** Projektauftrag und Entscheidungen während des Baus. | **Output:** Was gebaut wurde, warum, und wie es belegt ist.

| Befund | Änderung | Nachweis |
|---|---|---|
| Sprachmodelle rechnen Summen nach oder „korrigieren“ sie | Summen- und Steuersatzprüfung laufen im Programmcode; Modelle übernehmen nur gedruckte Werte | `src/idp/rules.py`, `tests/test_rules.py`; Llama 3.3 hat in der Messung 5 Rechnungen mit falscher Summe freigegeben |
| Dublettenprüfung im Ablauf kann sich überholen | Datenbank-Trigger schickt eine zweite Buchung derselben Lieferant-Rechnungsnummer zur Prüfung; eindeutiger Teilindex als letzte Sicherung | `sql/001_invoices.sql`, ausgeführt gegen PostgreSQL 16 und Supabase |
| Anweisungen, Fragen und Schwellen könnten zwischen Messung und n8n auseinanderlaufen | n8n-Ablauf wird aus dem Python-Paket erzeugt; die automatische Prüfung vergleicht die eingecheckte Datei | `src/idp/workflow.py`, `.github/workflows/ci.yml`, `tests/test_workflow.py` |
| JavaScript-Weiche in n8n muss der Python-Weiche entsprechen | Dieselben Fälle in Node.js und Python geprüft | `tests/test_workflow.py::test_javascript_gate_matches_python` |
| Erste Fassung von Jevs Vollständigkeitsfrage bewertete saubere Rechnungen mit 0,63–0,80 | Frage einmal an 15 Dokumenten des Testsatzes und den drei Vorführdokumenten umformuliert, danach eingefroren; gleiche Formulierung in der Anweisung der Einzelmodelle | `src/idp/prompts.py`; 18 von 18 an der Schwelle 0,85 getrennt |
| Claude Haiku 5.5 denkt standardmäßig nach und stieß an die Token-Grenze | Messung und Ablauf rufen Claude ohne erweitertes Nachdenken auf | `src/idp/systems.py`, `src/idp/workflow.py` |
| Jev auf Workers AI wird über AI-Gateway-Guthaben abgerechnet, nicht über den Workers-Tarif | In der Einrichtungsanleitung beschrieben | `Dokumentation/SETUP.de.md`, Schritt 2 |
| Kostenlose Docker-Spaces auf CPU basic wurden 2026 abgeschafft | Space läuft unter einem PRO-Konto; Anleitung nennt das | `Dokumentation/SETUP.de.md`, Schritt 4 |
| Eine öffentliche Vorführung einer sauberen Rechnung würde nach dem ersten Besucher zur Dublette | Das Telekom-Beispiel bekommt je Einreichung eine neue Rechnungsnummer | `src/idp/samples.py`, Durchlauf in lokalem n8n 2.42.5 |

## Abschlussprüfung
**Context:** Abschnitt 10 des Engineering-Standards. | **Input:** Saubere Kopie ohne `.venv` und `.env`. | **Output:** Bestanden oder nicht je Prüfung.

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| Installation aus der Sperrdatei in frischer Umgebung | bestanden | `uv sync --locked` |
| `ruff check`, `ruff format --check` | bestanden | 28 Dateien |
| `mypy --strict` | bestanden | 21 Quelldateien |
| `pytest` | bestanden | 70 Tests |
| README-Befehle | bestanden | `idp corpus` erzeugt `data/corpus.jsonl` bytegleich; `idp benchmark --limit`, `idp report`, `idp workflow`, `idp samples` laufen |
| n8n-Ablauf von Anfang bis Ende | bestanden | lokales n8n 2.42.5 mit echtem Jev und Haiku: Telekom gebucht, AWS Prüfung (Summe), Global AI Prüfung (Betrug), leere Eingabe abgewiesen |
| Geheimnisse, absolute Pfade, Debug-Ausgaben, TODO | keine gefunden | Schlüsselwerte und Muster in allen Dateien gesucht |
