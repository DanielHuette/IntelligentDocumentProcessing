# Einrichtung: Cloud-Betrieb

[English version](SETUP.md)

Supabase (kostenloser Tarif) speichert die Rechnungen und die Daten von n8n, ein Hugging-Face-Space
betreibt n8n (Docker-Spaces auf CPU basic brauchen seit Mitte 2026 ein PRO-Konto), Cloudflare
Workers AI stellt Jev bereit, Anthropic stellt Claude Haiku 5.5 bereit. Dauer: etwa 30 Minuten.

## 1. Supabase: Datenbank
**Context:** Dauerhafte Ablage für Rechnungen, Prüf-Warteschlange und n8n selbst. | **Input:** `sql/001_invoices.sql`. | **Output:** Projekt-Adresse, geheimer Schlüssel, Verbindungsdaten.

| Schritt | Handlung | Ergebnis |
|---|---|---|
| 1 | Bei supabase.com registrieren, Projekt anlegen (Region Frankfurt, Datenbank-Passwort notieren). | Leere Postgres-Datenbank |
| 2 | SQL Editor → New query → `sql/001_invoices.sql` einfügen → Run. | Tabellen `vendors` (15 Lieferanten) und `invoices`, Schema `n8n`, Dubletten-Prüfung, Zeilenschutz |
| 3 | Project Settings → API Keys → Secret keys → neuen Schlüssel anlegen. | Schlüssel `sb_secret_…` für n8n |
| 4 | Connect → Session pooler. Host, Benutzer und Port kopieren. | Host wie `aws-0-eu-central-1.pooler.supabase.com`, Benutzer `postgres.<project-ref>`, Port 5432 |

Der Session Pooler ist nötig, weil Hugging-Face-Spaces den direkten Datenbank-Host nur über IPv6
erreichen würden, und das unterstützen sie nicht.

## 2. Cloudflare: Jev
**Context:** Jev läuft als `typesafe/jev` auf Workers AI. | **Input:** Cloudflare-Konto. | **Output:** Konto-Nummer, API-Token, Guthaben.

| Schritt | Handlung | Ergebnis |
|---|---|---|
| 1 | My Profile → API Tokens → Create Token → Custom token, Recht Account · Workers AI · Edit. | API-Token |
| 2 | AI → AI Gateway → Credits → Top-up credits (mindestens 10 USD, Kredit- oder Debitkarte direkt eingetragen, nicht über Google Pay). | Guthaben für Fremdmodelle wie Jev |
| 3 | Konto-Nummer aus der Adresse im Dashboard kopieren (`dash.cloudflare.com/<konto-nummer>/…`). | Konto-Nummer |

Jev kostet 0,042 USD pro Million Eingabe-Token; ein Dokument hat etwa 2.100 Token.

## 3. Anthropic: Claude Haiku 5.5
| Schritt | Handlung | Ergebnis |
|---|---|---|
| 1 | platform.claude.com → API Keys → Create Key. | Schlüssel `sk-ant-…` |
| 2 | Billing → monatliche Ausgabegrenze setzen. | Ein öffentliches Formular kann keine Kosten auftürmen |

## 4. Hugging Face: n8n
**Context:** n8n ohne eigenen Server. | **Input:** `deploy/huggingface-space/`. | **Output:** Öffentliche Formular-Adresse.

| Schritt | Handlung | Ergebnis |
|---|---|---|
| 1 | huggingface.co → New Space → SDK Docker → Blank → CPU basic → Public (braucht PRO). | Leerer Space |
| 2 | Files → `Dockerfile` und `README.md` aus `deploy/huggingface-space/` hochladen. | Space baut n8n |
| 3 | Settings → Variables and secrets → Einträge aus der Tabelle anlegen, dann Restart. | n8n startet mit Supabase |
| 4 | Space-Adresse sofort öffnen und das n8n-Eigentümerkonto anlegen. | Niemand sonst kann die Instanz übernehmen |

| Name | Art | Wert |
|---|---|---|
| `N8N_ENCRYPTION_KEY` | Secret | 32+ zufällige Zeichen; Kopie aufbewahren, damit sind die Zugangsdaten verschlüsselt |
| `DB_POSTGRESDB_HOST` | Secret | Host des Session Poolers |
| `DB_POSTGRESDB_USER` | Secret | `postgres.<project-ref>` |
| `DB_POSTGRESDB_PASSWORD` | Secret | Datenbank-Passwort aus Schritt 1.1 |
| `CLOUDFLARE_ACCOUNT_ID` | Secret | Konto-Nummer aus Schritt 2.3 |
| `N8N_HOST` | Variable | `<konto>-<space>.hf.space` |
| `WEBHOOK_URL` | Variable | `https://<benutzer>-<space>.hf.space/` |
| `N8N_EDITOR_BASE_URL` | Variable | `https://<benutzer>-<space>.hf.space/` |

## 5. n8n: Ablauf
| Schritt | Handlung | Ergebnis |
|---|---|---|
| 1 | Credentials → Header Auth `Cloudflare Workers AI`: Name `Authorization`, Wert `Bearer <token>`. | Zugang zu Jev |
| 2 | Credentials → Header Auth `Anthropic`: Name `x-api-key`, Wert `<schlüssel>`. | Zugang zu Haiku |
| 3 | Credentials → Supabase API `Supabase`: Host `https://<project-ref>.supabase.co`, geheimer Schlüssel. | Zugang zur Datenbank |
| 4 | Workflows → Import from file → `n8n/invoice_pipeline.workflow.json`. In den Schritten `Jev entscheidet`, `Haiku liest aus`, `Zweig A: buchen` und `Zweig B: zur Prüfung` die Zugangsdaten auswählen. | Ablauf vollständig |
| 5 | Publish. `https://<benutzer>-<space>.hf.space/form/rechnungseingang` öffnen. | Öffentliches Formular |

Erwartete Ergebnisse der drei eingebauten Dokumente:

| Dokument | Weg | Angezeigter Grund |
|---|---|---|
| Telekom | Gebucht | keiner |
| AWS | Prüfung | Netto plus Steuer ergibt nicht Brutto |
| Global AI Shapers | Prüfung | keine Rechnung aus den Stammdaten, verdächtige Kontoänderung |

## 6. Vorführung wach halten
GitHub-Repository → Settings → Secrets and variables → Actions → Variables → `DEMO_FORM_URL` =
Formular-Adresse. Der Ablauf `keepalive.yml` lädt das Formular dann einmal täglich, damit Space
und Supabase-Projekt nicht einschlafen.
