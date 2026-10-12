# Work report

[Deutsche Fassung](REFACTORING_REPORT.de.md)

## Build decisions
**Context:** New project, built from scratch on 8–9 October 2026. | **Input:** Project brief and decisions taken during the build. | **Output:** What was built, why, and how it is proven.

| Finding | Change | Evidence |
|---|---|---|
| Language models recompute or "correct" totals | Arithmetic and tax-rate checks run in plain code; models only copy printed values | `src/idp/rules.py`, `tests/test_rules.py`; Llama 3.3 approved 5 invoices with wrong sums in the benchmark |
| Duplicate detection inside the workflow can race | Database trigger moves a second booking of the same supplier + invoice number to review; partial unique index as last line | `sql/001_invoices.sql`, run against PostgreSQL 16 and Supabase |
| Prompts, questions and thresholds could drift between benchmark and n8n | n8n workflow is generated from the Python package; CI diffs the committed file | `src/idp/workflow.py`, `.github/workflows/ci.yml`, `tests/test_workflow.py` |
| JavaScript gate in n8n must match the Python gate | Same cases evaluated in Node.js and Python | `tests/test_workflow.py::test_javascript_gate_matches_python` |
| First wording of Jev's completeness question scored clean invoices at 0.63–0.80 | Question reworded once on 15 corpus documents plus three demo documents, then frozen; same wording in the single-model prompt | `src/idp/prompts.py`; 18/18 separated at the 0.85 threshold |
| Claude Haiku 5.5 thinks by default and hit the token limit | Benchmark and workflow call Claude without extended thinking | `src/idp/systems.py`, `src/idp/workflow.py` |
| Jev on Workers AI is billed from AI Gateway credits, not the Workers plan | Documented in setup guide | `Dokumentation/SETUP.md` step 2 |
| Free Docker Spaces on CPU basic were withdrawn in 2026 | Space runs under a PRO account; setup guide states it | `Dokumentation/SETUP.md` step 4 |
| A public demo of a clean invoice would turn into a duplicate after the first visitor | The Telekom sample gets a fresh invoice number per submission | `src/idp/samples.py`, end-to-end run in a local n8n 2.42.5 |

## Final check
**Context:** Section 10 of the engineering standard. | **Input:** Clean copy without `.venv` and `.env`. | **Output:** Pass or fail per check.

| Check | Result | Evidence |
|---|---|---|
| Install from lock file in a fresh environment | pass | `uv sync --locked` |
| `ruff check`, `ruff format --check` | pass | 28 files |
| `mypy --strict` | pass | 21 source files |
| `pytest` | pass | 70 tests |
| README commands | pass | `idp corpus` reproduces `data/corpus.jsonl` byte for byte; `idp benchmark --limit`, `idp report`, `idp workflow`, `idp samples` run |
| n8n workflow end to end | pass | local n8n 2.42.5 with real Jev and Haiku: Telekom booked, AWS review (sum), Global AI review (scam), empty input rejected |
| Secrets, absolute paths, debug output, TODO | none found | key values and patterns searched in all tracked files |
