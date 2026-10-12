# Setup: cloud deployment

[Deutsche Fassung](SETUP.de.md)

Supabase (free tier) stores the invoices and n8n's own data, a Hugging Face Space runs n8n (Docker
Spaces on CPU basic need a PRO account since mid-2026), Cloudflare Workers AI serves Jev, Anthropic
serves Claude Haiku 5.5. Allow about 30 minutes.

## 1. Supabase: database
**Context:** Persistent storage for invoices, the review queue and n8n itself. | **Input:** `sql/001_invoices.sql`. | **Output:** Project URL, secret key, connection details.

| Step | Action | Result |
|---|---|---|
| 1 | Sign up at supabase.com, create a project (region Frankfurt, note the database password). | Empty Postgres database |
| 2 | SQL Editor → New query → paste `sql/001_invoices.sql` → Run. | Tables `vendors` (15 suppliers) and `invoices`, schema `n8n`, duplicate trigger, row level security |
| 3 | Project Settings → API Keys → Secret keys → create one. | `sb_secret_…` key for n8n |
| 4 | Connect → Session pooler. Copy host, user and port. | Host like `aws-0-eu-central-1.pooler.supabase.com`, user `postgres.<project-ref>`, port 5432 |

The session pooler is required because Hugging Face Spaces have no IPv6 route to the direct
database host.

## 2. Cloudflare: Jev
**Context:** Jev runs as `typesafe/jev` on Workers AI. | **Input:** Cloudflare account. | **Output:** Account ID, API token, credits.

| Step | Action | Result |
|---|---|---|
| 1 | My Profile → API Tokens → Create Token → Custom token, permission Account · Workers AI · Edit. | API token |
| 2 | AI → AI Gateway → Credits → Top-up credits (minimum 10 USD, needs a credit or debit card entered directly). | Balance for third-party models such as Jev |
| 3 | Copy the account ID from the dashboard URL (`dash.cloudflare.com/<account-id>/…`). | Account ID |

Jev costs 0.042 USD per million input tokens; one document is about 2,100 tokens.

## 3. Anthropic: Claude Haiku 5.5
| Step | Action | Result |
|---|---|---|
| 1 | platform.claude.com → API Keys → Create Key. | `sk-ant-…` key |
| 2 | Billing → set a monthly spend limit. | A public form cannot run up costs |

## 4. Hugging Face: n8n
**Context:** n8n without a server of your own. | **Input:** `deploy/huggingface-space/`. | **Output:** Public form URL.

| Step | Action | Result |
|---|---|---|
| 1 | huggingface.co → New Space → SDK Docker → Blank → CPU basic → Public (needs PRO). | Empty Space |
| 2 | Files → upload `Dockerfile` and `README.md` from `deploy/huggingface-space/`. | Space builds n8n |
| 3 | Settings → Variables and secrets → add the entries below, then Restart. | n8n starts against Supabase |
| 4 | Open the Space URL at once and create the n8n owner account. | Nobody else can claim the instance |

| Name | Kind | Value |
|---|---|---|
| `N8N_ENCRYPTION_KEY` | Secret | 32+ random characters; keep a copy, credentials are encrypted with it |
| `DB_POSTGRESDB_HOST` | Secret | Session pooler host |
| `DB_POSTGRESDB_USER` | Secret | `postgres.<project-ref>` |
| `DB_POSTGRESDB_PASSWORD` | Secret | Database password from step 1.1 |
| `CLOUDFLARE_ACCOUNT_ID` | Secret | Account ID from step 2.3 |
| `N8N_HOST` | Variable | `<user>-<space>.hf.space` |
| `WEBHOOK_URL` | Variable | `https://<user>-<space>.hf.space/` |
| `N8N_EDITOR_BASE_URL` | Variable | `https://<user>-<space>.hf.space/` |

## 5. n8n: workflow
| Step | Action | Result |
|---|---|---|
| 1 | Credentials → Header Auth `Cloudflare Workers AI`: name `Authorization`, value `Bearer <token>`. | Jev access |
| 2 | Credentials → Header Auth `Anthropic`: name `x-api-key`, value `<key>`. | Haiku access |
| 3 | Credentials → Supabase API `Supabase`: host `https://<project-ref>.supabase.co`, secret key. | Database access |
| 4 | Workflows → Import from file → `n8n/invoice_pipeline.workflow.json`. Select the credentials in the nodes `Jev entscheidet`, `Haiku liest aus`, `Zweig A: buchen`, `Zweig B: zur Prüfung`. | Workflow complete |
| 5 | Publish. Open `https://<user>-<space>.hf.space/form/rechnungseingang`. | Public form |

Expected results for the three built-in documents:

| Document | Route | Reason shown |
|---|---|---|
| Telekom | Booked | none |
| AWS | Review | net + tax does not equal gross |
| Global AI Shapers | Review | not an invoice from master data, suspicious bank change |

## 6. Keep the demo awake
GitHub repository → Settings → Secrets and variables → Actions → Variables → `DEMO_FORM_URL` =
form URL. The workflow `keepalive.yml` then loads the form once a day, which keeps the Space and
the Supabase project from going to sleep.
