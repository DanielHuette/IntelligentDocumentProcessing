"""Build the n8n workflow from the same prompts, questions and rules as the benchmark.

Context: Generates n8n/invoice_pipeline.workflow.json so production and benchmark cannot drift apart. |
Input: Prompts, vendor master data, gate thresholds, showcase samples. |
Output: Workflow dictionary ready for import.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from idp.prompts import EXTRACTION_SYSTEM_PROMPT, jev_questions
from idp.rules import ALLOWED_TAX_RATES, CONFIDENCE_THRESHOLD, SUM_TOLERANCE, TAX_TOLERANCE
from idp.samples import CUSTOM_OPTION, FRESH_NUMBER_SAMPLES, SHOWCASE
from idp.vendors import VENDORS

WORKFLOW_NAME = "Intelligent Document Processing – Rechnungseingang"
FORM_PATH = "rechnungseingang"
MAX_CHARACTERS = 8000
HAIKU_MODEL = "claude-haiku-5-5"
_NAMESPACE = uuid.UUID("6f1c2a52-3d0e-4d55-9a62-2f3d8f0c7a11")

GATE_JS = f"""\
const THRESHOLD = {CONFIDENCE_THRESHOLD};
const ALLOWED_RATES_CENTS = {sorted(int(r * 100) for r in ALLOWED_TAX_RATES)};
const SUM_TOLERANCE_CENTS = {int(SUM_TOLERANCE * 100)};
const TAX_TOLERANCE_CENTS = {int(TAX_TOLERANCE * 100)};

function parseAmount(value) {{
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? Math.round(value * 100) / 100 : null;
  const match = String(value).match(/-?[\\d.,]+/);
  if (!match) return null;
  let text = match[0];
  if (text.includes(',') && text.includes('.')) {{
    text = text.lastIndexOf(',') > text.lastIndexOf('.')
      ? text.replace(/\\./g, '').replace(',', '.')
      : text.replace(/,/g, '');
  }} else if (text.includes(',')) {{
    text = text.replace(',', '.');
  }}
  const number = Number(text);
  return Number.isFinite(number) ? Math.round(number * 100) / 100 : null;
}}

function toCents(value) {{
  return Math.round(value * 100);
}}

function arithmeticProblems(extraction) {{
  const net = parseAmount(extraction.net);
  const rate = parseAmount(extraction.tax_rate);
  const tax = parseAmount(extraction.tax);
  const gross = parseAmount(extraction.gross);
  if (net === null || rate === null || tax === null || gross === null) {{
    return ['totals incomplete: net, tax rate, tax and gross are required'];
  }}
  const problems = [];
  const ratePercent = Math.round(rate > 1 ? rate : rate * 100);
  if (!ALLOWED_RATES_CENTS.includes(ratePercent)) {{
    problems.push(`tax rate ${{ratePercent}} % is not a German VAT rate`);
  }}
  if (Math.abs(toCents(net) + toCents(tax) - toCents(gross)) > SUM_TOLERANCE_CENTS) {{
    problems.push(`net ${{net}} + tax ${{tax}} != gross ${{gross}}`);
  }}
  if (Math.abs(Math.round(toCents(net) * ratePercent / 100) - toCents(tax)) > TAX_TOLERANCE_CENTS) {{
    problems.push(`tax ${{tax}} does not match ${{ratePercent}} % of net ${{net}}`);
  }}
  return problems;
}}

function gate(classification, extraction) {{
  if (classification.document_type !== 'invoice') {{
    return {{ route: 'needs_review', reasons: [`document type is ${{classification.document_type}}, not invoice`] }};
  }}
  const reasons = [];
  if (classification.document_type_confidence < THRESHOLD) {{
    reasons.push(`document type confidence ${{classification.document_type_confidence.toFixed(2)}}`);
  }}
  if (classification.vendor_key === 'unknown') {{
    reasons.push('vendor is not in master data');
  }} else if (classification.vendor_confidence < THRESHOLD) {{
    reasons.push(`vendor confidence ${{classification.vendor_confidence.toFixed(2)}}`);
  }}
  if (classification.formally_complete_probability < THRESHOLD) {{
    reasons.push(`mandatory invoice fields incomplete (probability ${{classification.formally_complete_probability.toFixed(2)}})`);
  }}
  if (!extraction.invoice_number) reasons.push('invoice number missing');
  reasons.push(...arithmeticProblems(extraction));
  return reasons.length ? {{ route: 'needs_review', reasons }} : {{ route: 'approved', reasons: [] }};
}}
"""

_PREPARE_JS = """\
const SAMPLES = __SAMPLES__;
const FRESH_NUMBERS = __FRESH__;
const CUSTOM_OPTION = __CUSTOM__;
const MAX_CHARACTERS = __MAX__;
const JEV_QUESTIONS = __QUESTIONS__;
const EXTRACTION_PROMPT = __PROMPT__;

const form = $input.first().json;
const choice = form.document_choice;
const custom = String(form.custom_text || '').trim();
let text = choice === CUSTOM_OPTION ? custom : (SAMPLES[choice] || '');
if (FRESH_NUMBERS[choice]) {
  const fresh = FRESH_NUMBERS[choice].slice(0, -5) + String(Date.now()).slice(-5);
  text = text.split(FRESH_NUMBERS[choice]).join(fresh);
}
let problem = null;
if (!text) problem = 'Bitte einen Rechnungstext einfügen oder ein Testdokument wählen.';
else if (text.length > MAX_CHARACTERS) problem = `Der Text ist länger als ${MAX_CHARACTERS} Zeichen.`;

return [{
  json: {
    valid: problem === null,
    problem,
    source: choice === CUSTOM_OPTION ? 'custom' : choice,
    documentText: text,
    startedAt: Date.now(),
    jevRequest: { model: 'typesafe/jev', input: { state: text, questions: JEV_QUESTIONS } },
    haikuRequest: {
      model: __MODEL__,
      max_tokens: 1500,
      thinking: { type: 'disabled' },
      system: EXTRACTION_PROMPT,
      messages: [{ role: 'user', content: `<document>\\n${text}\\n</document>` }],
    },
  },
}];
"""

_STAMP_JS = """\
const prepared = $('Anfragen vorbereiten').first().json;
return [{ json: { jevMs: Date.now() - prepared.startedAt, haikuStartedAt: Date.now() } }];
"""

_DECIDE_JS = """\
const VENDOR_NAMES = __VENDORS__;

function parseJsonObject(text) {
  const start = String(text || '').indexOf('{');
  const end = String(text || '').lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try { return JSON.parse(text.slice(start, end + 1)); } catch (error) { return null; }
}

function clamp(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(Math.max(number, 0), 1) : 0;
}

const prepared = $('Anfragen vorbereiten').first().json;
const timing = $('Jev-Zeit messen').first().json;
const jevBody = $('Jev entscheidet').first().json;
const haikuBody = $('Haiku liest aus').first().json;
const haikuMs = Date.now() - timing.haikuStartedAt;

const jevResult = (jevBody && jevBody.result) || {};
const answers = (jevResult.result && jevResult.result.answers) || jevResult.answers || null;
const haikuText = haikuBody && Array.isArray(haikuBody.content)
  ? haikuBody.content.map((block) => block.text || '').join('')
  : '';
const extraction = parseJsonObject(haikuText) || {};

let decision;
let classification = null;
if (!answers) {
  decision = { route: 'needs_review', reasons: ['Jev did not answer'] };
} else {
  classification = {
    document_type: String((answers.document_type || {}).choice || ''),
    document_type_confidence: clamp((answers.document_type || {}).confidence),
    vendor_key: String((answers.vendor || {}).choice || 'unknown'),
    vendor_confidence: clamp((answers.vendor || {}).confidence),
    formally_complete_probability: clamp((answers.formally_complete || {}).noul),
  };
  decision = gate(classification, extraction);
  if (!haikuText) decision = { route: 'needs_review', reasons: [...decision.reasons, 'Haiku did not answer'] };
}

const vendorKey = classification ? classification.vendor_key : 'unknown';
const isoDate = /^\\d{4}-\\d{2}-\\d{2}$/.test(String(extraction.invoice_date || ''))
  ? extraction.invoice_date : null;
const confidences = classification
  ? [classification.document_type_confidence, classification.vendor_confidence,
     classification.formally_complete_probability]
  : [0];

return [{
  json: {
    vendor: VENDOR_NAMES[vendorKey] || extraction.vendor_name || null,
    vendor_key: vendorKey,
    document_type: classification ? classification.document_type : 'unrecognized',
    invoice_number: extraction.invoice_number || null,
    invoice_date: isoDate,
    total_net: parseAmount(extraction.net),
    tax_rate: parseAmount(extraction.tax_rate),
    total_tax: parseAmount(extraction.tax),
    total_gross: parseAmount(extraction.gross),
    status: decision.route,
    human_review_required: decision.route !== 'approved',
    review_reasons: decision.reasons,
    jev_confidence: Math.round(Math.min(...confidences) * 1000) / 1000,
    jev_answers: classification,
    haiku_summary: extraction.summary || null,
    notes: Array.isArray(extraction.notes) ? extraction.notes.map(String) : [],
    latency_ms: { jev: timing.jevMs, haiku: haikuMs },
    source: prepared.source,
  },
}];
"""

_RESULT_JS = """\
const LABELS = {
  'totals incomplete: net, tax rate, tax and gross are required': 'Summen unvollständig: Netto, Steuersatz, Steuer und Brutto werden gebraucht',
  ' + tax ': ' + Steuer ',
  ' != gross ': ' ergibt nicht Brutto ',
  'tax rate ': 'Steuersatz ',
  'does not match': 'passt nicht zu',
  ' of net ': ' von Netto ',
  'net ': 'Netto ',
  'tax ': 'Steuer ',
  'document type is': 'Dokumentart ist',
  'not invoice': 'keine Rechnung',
  'vendor is not in master data': 'Lieferant steht nicht in den Stammdaten',
  'mandatory invoice fields incomplete': 'Pflichtangaben der Rechnung unvollständig',
  'invoice number missing': 'Rechnungsnummer fehlt',
  'is not a German VAT rate': 'ist kein deutscher Umsatzsteuersatz',
  'invoice already booked': 'Rechnung ist bereits gebucht',
  'Jev did not answer': 'Jev hat nicht geantwortet',
  'Haiku did not answer': 'Haiku hat nicht geantwortet',
  'confidence': 'Sicherheit',
  'probability': 'Wahrscheinlichkeit',
};
const DOCUMENT_TYPES = {
  invoice: 'Rechnung', credit_note: 'Gutschrift', payment_reminder: 'Mahnung',
  delivery_note: 'Lieferschein', quote: 'Angebot', purchase_order: 'Bestellung',
  order_confirmation: 'Auftragsbestätigung', contract: 'Vertrag', termination: 'Kündigung',
  receipt: 'Quittung', bank_statement: 'Kontoauszug', email: 'E-Mail ohne Beleg',
  fraudulent_invoice: 'Verdacht auf Scheinrechnung', unrecognized: 'nicht erkannt',
};
function german(reason) {
  const typed = Object.entries(DOCUMENT_TYPES)
    .reduce((text, [key, label]) => text.split(`is ${key},`).join(`is ${label},`), reason);
  return Object.entries(LABELS).reduce((text, [en, de]) => text.split(en).join(de), typed);
}
function escape(text) {
  return String(text ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function euro(value) {
  return value === null || value === undefined ? '–'
    : Number(value).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });
}

const decided = $('Prüfregeln anwenden').first().json;
const stored = $input.first().json;
const saved = Boolean(stored && stored.id);
const row = saved ? stored : decided;
const approved = row.status === 'approved';
const reasons = (row.review_reasons || []).map((r) => `<li>${escape(german(r))}</li>`).join('');
const notes = (row.notes || []).map((n) => `<li>${escape(n)}</li>`).join('');

const html = `
<h2>${approved ? 'Freigegeben und gebucht' : 'Zur Prüfung an die Buchhaltung'}</h2>
<p>${approved
  ? 'Alle Entscheidungen waren sicher genug und alle Prüfungen bestanden. Die Rechnung liegt als gebucht in der Datenbank.'
  : 'Mindestens eine Prüfung ist nicht bestanden. Die Rechnung wartet in der Prüf-Warteschlange auf einen Menschen.'}</p>
${reasons ? `<p><strong>Gründe:</strong></p><ul>${reasons}</ul>` : ''}
<table>
<tr><td>Lieferant</td><td>${escape(row.vendor || 'unbekannt')}</td></tr>
<tr><td>Dokumentart</td><td>${escape(DOCUMENT_TYPES[row.document_type] || row.document_type)}</td></tr>
<tr><td>Rechnungsnummer</td><td>${escape(row.invoice_number || '–')}</td></tr>
<tr><td>Netto / Steuer / Brutto</td><td>${euro(row.total_net)} / ${euro(row.total_tax)} / ${euro(row.total_gross)}</td></tr>
<tr><td>Sicherheit von Jev (schwächster Wert)</td><td>${Math.round((row.jev_confidence || 0) * 100)} %</td></tr>
<tr><td>Antwortzeit Jev / Haiku</td><td>${row.latency_ms ? row.latency_ms.jev : '–'} ms / ${row.latency_ms ? row.latency_ms.haiku : '–'} ms</td></tr>
</table>
<p><strong>Zusammenfassung von Claude Haiku 5.5:</strong> ${escape(row.haiku_summary || '–')}</p>
${notes ? `<p><strong>Aussortierte Notizen:</strong></p><ul>${notes}</ul>` : ''}
<p>${saved ? `Gespeichert in Supabase, Datensatz ${escape(row.id)}.` : 'Nicht gespeichert: Die Datenbank war nicht erreichbar.'}</p>
<p><a href="/form/__PATH__">Weiteres Dokument prüfen</a></p>`;

return [{ json: { html } }];
"""


def _node_id(name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, name))


def _node(
    name: str,
    node_type: str,
    version: float,
    position: tuple[int, int],
    parameters: dict[str, Any],
    **settings: Any,
) -> dict[str, Any]:
    return {
        "parameters": parameters,
        "id": _node_id(name),
        "name": name,
        "type": node_type,
        "typeVersion": version,
        "position": list(position),
        **settings,
    }


def _if(name: str, position: tuple[int, int], left: str) -> dict[str, Any]:
    return _node(
        name,
        "n8n-nodes-base.if",
        2.2,
        position,
        {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": _node_id(name + "-condition"),
                        "leftValue": left,
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
    )


def _code(name: str, position: tuple[int, int], js: str) -> dict[str, Any]:
    return _node(name, "n8n-nodes-base.code", 2, position, {"jsCode": js})


def _http(
    name: str,
    position: tuple[int, int],
    url: str,
    body: str,
    headers: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "method": "POST",
        "url": url,
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": bool(headers),
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": body,
        "options": {"timeout": 30000},
    }
    if headers:
        parameters["headerParameters"] = {"parameters": headers}
    return _node(
        name,
        "n8n-nodes-base.httpRequest",
        4.2,
        position,
        parameters,
        retryOnFail=True,
        maxTries=3,
        waitBetweenTries=1000,
        onError="continueRegularOutput",
    )


def _supabase(name: str, position: tuple[int, int]) -> dict[str, Any]:
    return _node(
        name,
        "n8n-nodes-base.supabase",
        1,
        position,
        {"tableId": "invoices", "dataToSend": "autoMapInputData"},
        onError="continueRegularOutput",
    )


def _completion(name: str, position: tuple[int, int], text: str) -> dict[str, Any]:
    return _node(
        name,
        "n8n-nodes-base.form",
        2.4,
        position,
        {"operation": "completion", "respondWith": "showText", "responseText": text},
    )


def _form_trigger() -> dict[str, Any]:
    options = [{"option": label} for label, _ in SHOWCASE.values()]
    options.append({"option": CUSTOM_OPTION})
    return _node(
        "Dokument einreichen",
        "n8n-nodes-base.formTrigger",
        2.4,
        (0, 300),
        {
            "formTitle": "Rechnungseingang prüfen",
            "formDescription": (
                "Wählen Sie ein Testdokument oder fügen Sie eigenen Rechnungstext ein. "
                "Jev entscheidet über Dokumentart, Lieferant und Vollständigkeit, Claude Haiku 5.5 "
                "liest die Beträge aus, feste Regeln rechnen nach. Nur sichere und fehlerfreie "
                "Rechnungen werden gebucht, alles andere geht zur Prüfung an einen Menschen."
            ),
            "formFields": {
                "values": [
                    {
                        "fieldName": "document_choice",
                        "fieldLabel": "Testdokument",
                        "fieldType": "dropdown",
                        "fieldOptions": {"values": options},
                        "requiredField": True,
                    },
                    {
                        "fieldName": "custom_text",
                        "fieldLabel": "Eigener Text",
                        "fieldType": "textarea",
                        "placeholder": "Nur ausfüllen, wenn oben „Eigener Text“ gewählt ist",
                    },
                ]
            },
            "options": {
                "path": FORM_PATH,
                "buttonLabel": "Dokument prüfen",
                "appendAttribution": False,
            },
        },
        webhookId=_node_id("form-webhook"),
    )


def _connect(*pairs: tuple[str, str, int]) -> dict[str, Any]:
    connections: dict[str, Any] = {}
    for source, target, output in pairs:
        outputs = connections.setdefault(source, {"main": []})["main"]
        while len(outputs) <= output:
            outputs.append([])
        outputs[output].append({"node": target, "type": "main", "index": 0})
    return connections


def prepare_js() -> str:
    """Code of the node that selects the document and builds both model requests."""
    samples = dict(SHOWCASE.values())
    replacements = {
        "__SAMPLES__": json.dumps(samples, ensure_ascii=False, indent=1),
        "__CUSTOM__": json.dumps(CUSTOM_OPTION, ensure_ascii=False),
        "__FRESH__": json.dumps(FRESH_NUMBER_SAMPLES, ensure_ascii=False),
        "__MAX__": str(MAX_CHARACTERS),
        "__QUESTIONS__": json.dumps(jev_questions(), ensure_ascii=False, indent=1),
        "__PROMPT__": json.dumps(EXTRACTION_SYSTEM_PROMPT, ensure_ascii=False),
        "__MODEL__": json.dumps(HAIKU_MODEL),
    }
    code = _PREPARE_JS
    for marker, value in replacements.items():
        code = code.replace(marker, value)
    return code


def decide_js() -> str:
    """Code of the node that applies the confidence gate."""
    names = {vendor.key: vendor.party.name for vendor in VENDORS}
    return (
        GATE_JS
        + "\n"
        + _DECIDE_JS.replace("__VENDORS__", json.dumps(names, ensure_ascii=False, indent=1))
    )


def build_workflow() -> dict[str, Any]:
    """Assemble the complete workflow.

    Returns:
        Workflow dictionary in the n8n import format, without credentials.
    """
    nodes = [
        _form_trigger(),
        _code("Anfragen vorbereiten", (220, 300), prepare_js()),
        _if("Text gültig?", (440, 300), "={{ $json.valid }}"),
        _completion(
            "Hinweis anzeigen", (660, 520), "={{ $('Anfragen vorbereiten').first().json.problem }}"
        ),
        _http(
            "Jev entscheidet",
            (660, 300),
            "=https://api.cloudflare.com/client/v4/accounts/{{ $env.CLOUDFLARE_ACCOUNT_ID }}/ai/run",
            "={{ JSON.stringify($('Anfragen vorbereiten').first().json.jevRequest) }}",
        ),
        _code("Jev-Zeit messen", (880, 300), _STAMP_JS),
        _http(
            "Haiku liest aus",
            (1100, 300),
            "https://api.anthropic.com/v1/messages",
            "={{ JSON.stringify($('Anfragen vorbereiten').first().json.haikuRequest) }}",
            [{"name": "anthropic-version", "value": "2023-06-01"}],
        ),
        _code("Prüfregeln anwenden", (1320, 300), decide_js()),
        _if("Freigabe?", (1540, 300), "={{ $json.status === 'approved' }}"),
        _supabase("Zweig A: buchen", (1760, 200)),
        _supabase("Zweig B: zur Prüfung", (1760, 420)),
        _code("Ergebnis aufbereiten", (1980, 300), _RESULT_JS.replace("__PATH__", FORM_PATH)),
        _completion("Ergebnis anzeigen", (2200, 300), "={{ $json.html }}"),
    ]
    connections = _connect(
        ("Dokument einreichen", "Anfragen vorbereiten", 0),
        ("Anfragen vorbereiten", "Text gültig?", 0),
        ("Text gültig?", "Jev entscheidet", 0),
        ("Text gültig?", "Hinweis anzeigen", 1),
        ("Jev entscheidet", "Jev-Zeit messen", 0),
        ("Jev-Zeit messen", "Haiku liest aus", 0),
        ("Haiku liest aus", "Prüfregeln anwenden", 0),
        ("Prüfregeln anwenden", "Freigabe?", 0),
        ("Freigabe?", "Zweig A: buchen", 0),
        ("Freigabe?", "Zweig B: zur Prüfung", 1),
        ("Zweig A: buchen", "Ergebnis aufbereiten", 0),
        ("Zweig B: zur Prüfung", "Ergebnis aufbereiten", 0),
        ("Ergebnis aufbereiten", "Ergebnis anzeigen", 0),
    )
    return {
        "name": WORKFLOW_NAME,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": False},
    }
