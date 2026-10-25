"""Tests for the Jev relay in the project page worker.

Context: n8n on Hugging Face reaches Jev through web/_worker.js. | Input: Requests built in
Node.js with a stubbed fetch and ASSETS binding. | Output: Assertions on routing and forwarding.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1] / "web" / "_worker.js"
ACCOUNT = "0123456789abcdef0123456789abcdef"

SCRIPT = """
const worker = (await import(process.argv[1])).default;
const calls = [];
globalThis.fetch = async (url, init) => {
  calls.push({ url, auth: init.headers.Authorization, body: new TextDecoder().decode(init.body) });
  return new Response('{"ok":true}', { status: 200 });
};
const env = { ASSETS: { fetch: async () => new Response("page", { status: 200 }) } };
const base = "https://intelligentdocumentprocessing.speedofthespirit.dev";
const path = "/client/v4/accounts/" + process.argv[2] + "/ai/run";
const relayed = await worker.fetch(new Request(base + path, {
  method: "POST", headers: { Authorization: "Bearer t" }, body: '{"q":1}' }), env);
const getRelay = await worker.fetch(new Request(base + path), env);
const page = await worker.fetch(new Request(base + "/"), env);
const other = await worker.fetch(new Request(base + "/client/v4/accounts/x/ai/run",
  { method: "POST", body: "{}" }), env);
const big = await worker.fetch(new Request(base + path,
  { method: "POST", body: "x".repeat(70000) }), env);
console.log(JSON.stringify({
  relayed: relayed.status, getRelay: getRelay.status, page: await page.text(),
  other: await other.text(), big: big.status, calls,
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_relay_forwards_only_workers_ai_calls() -> None:
    """Relay path goes upstream with the caller's token; everything else stays local."""
    output = subprocess.run(
        ["node", "--input-type=module", "-e", SCRIPT, WORKER.as_uri(), ACCOUNT],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(output.stdout)
    assert result["relayed"] == 200
    assert result["calls"] == [
        {
            "url": f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run",
            "auth": "Bearer t",
            "body": '{"q":1}',
        }
    ]
    assert result["getRelay"] == 405
    assert result["page"] == "page"
    assert result["other"] == "page"
    assert result["big"] == 413


HEADER_SCRIPT = """
const worker = (await import(process.argv[1])).default;
const env = { ASSETS: { fetch: async () => new Response("asset", {
  status: 200, headers: { "Content-Type": "text/html" } }) } };
const base = "https://intelligentdocumentprocessing.speedofthespirit.dev";
const result = {};
for (const path of ["/", "/fonts/archivo.woff2", "/app.js", "/bilder/vorschau.jpg"]) {
  const response = await worker.fetch(new Request(base + path), env);
  result[path] = { body: await response.text(), headers: Object.fromEntries(response.headers) };
}
console.log(JSON.stringify(result));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_page_responses_carry_security_and_cache_headers() -> None:
    """Advanced-mode Pages ignore _headers, so the worker attaches them to every asset."""
    output = subprocess.run(
        ["node", "--input-type=module", "-e", HEADER_SCRIPT, WORKER.as_uri()],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(output.stdout)
    page = result["/"]["headers"]
    assert result["/"]["body"] == "asset"
    assert page["content-type"] == "text/html"
    assert (
        "script-src 'self' https://static.cloudflareinsights.com" in page["content-security-policy"]
    )
    assert "connect-src 'self' https://cloudflareinsights.com" in page["content-security-policy"]
    assert page["x-content-type-options"] == "nosniff"
    assert page["cache-control"] == "public, max-age=0, must-revalidate"
    assert result["/app.js"]["headers"]["cache-control"] == "public, max-age=0, must-revalidate"
    assert "immutable" in result["/fonts/archivo.woff2"]["headers"]["cache-control"]
    assert result["/bilder/vorschau.jpg"]["headers"]["cache-control"] == "public, max-age=86400"


def test_measurement_copy_on_page_matches_results() -> None:
    """The Benchmarks tab draws from web/messung.json, which must equal results/summary.json."""
    project = Path(__file__).resolve().parents[1]
    page_copy = json.loads((project / "web" / "messung.json").read_text(encoding="utf-8"))
    source = json.loads((project / "results" / "summary.json").read_text(encoding="utf-8"))
    assert page_copy == source
