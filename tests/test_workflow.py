"""Tests for the generated n8n workflow and its gate logic."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from idp.cli import main
from idp.domain import Classification, Extraction
from idp.parsing import extraction_from_payload
from idp.rules import gate
from idp.workflow import GATE_JS, build_workflow, decide_js, prepare_js


def test_workflow_connections_reference_existing_nodes() -> None:
    workflow = build_workflow()
    names = [node["name"] for node in workflow["nodes"]]
    assert len(names) == len(set(names))
    for source, outputs in workflow["connections"].items():
        assert source in names
        for output in outputs["main"]:
            assert all(link["node"] in names for link in output)


def test_workflow_contains_no_credentials() -> None:
    text = json.dumps(build_workflow())
    assert "credentials" not in text
    assert "sk-ant" not in text


def test_generated_code_embeds_shared_definitions() -> None:
    assert "formally_complete" in prepare_js()
    assert "Telekom Deutschland GmbH" in decide_js()
    assert "__" not in prepare_js().replace("__proto__", "")


GATE_CASES = [
    (
        Classification("invoice", 0.99, "telekom", 0.99, 0.95),
        {"invoice_number": "1", "net": 100, "tax_rate": 19, "tax": 19, "gross": 119},
    ),
    (
        Classification("invoice", 0.99, "telekom", 0.99, 0.95),
        {"invoice_number": "1", "net": "100,00", "tax_rate": "19 %", "tax": 19, "gross": 128},
    ),
    (
        Classification("invoice", 0.99, "aws", 0.99, 0.95),
        {"invoice_number": "1", "net": 100, "tax_rate": 16, "tax": 16, "gross": 116},
    ),
    (
        Classification("invoice", 0.70, "unknown", 0.2, 0.3),
        {"invoice_number": None, "net": None, "tax_rate": None, "tax": None, "gross": None},
    ),
    (Classification("quote", 0.99, "aws", 0.99, 0.1), {}),
]


def _python_gate(classification: Classification, raw: dict[str, object]) -> dict[str, object]:
    extraction: Extraction = extraction_from_payload({**raw, "summary": ""})
    result = gate(classification, extraction, set())
    return {"route": result.route.value, "reasons": list(result.reasons)}


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
@pytest.mark.parametrize(("classification", "raw"), GATE_CASES)
def test_javascript_gate_matches_python(
    classification: Classification, raw: dict[str, object]
) -> None:
    script = (
        GATE_JS + f"\nconsole.log(JSON.stringify(gate({json.dumps(asdict(classification))}, "
        f"{json.dumps(raw)})));"
    )
    output = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    javascript = json.loads(output.stdout)
    python = _python_gate(classification, raw)
    assert javascript["route"] == python["route"]
    assert len(javascript["reasons"]) == len(python["reasons"])


def test_cli_writes_corpus_samples_and_workflow(tmp_path: Path) -> None:
    assert main(["corpus", "--size", "60", "--out", str(tmp_path / "c.jsonl")]) == 0
    assert main(["samples", "--out", str(tmp_path / "s")]) == 0
    assert main(["workflow", "--out", str(tmp_path / "w.json")]) == 0
    assert len((tmp_path / "c.jsonl").read_text().splitlines()) == 60
    assert len(list((tmp_path / "s").glob("*.txt"))) == 3
    assert json.loads((tmp_path / "w.json").read_text())["nodes"]


def test_cli_rejects_unknown_systems(tmp_path: Path) -> None:
    main(["corpus", "--size", "60", "--out", str(tmp_path / "c.jsonl")])
    assert main(["report", "--corpus", str(tmp_path / "c.jsonl"), "--systems", "nope"]) == 1
