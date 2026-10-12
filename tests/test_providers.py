"""Tests for the provider clients with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from idp.errors import ProviderError, ResponseFormatError, TransientProviderError
from idp.providers.base import JsonTransport, parse_json_object
from idp.providers.clients import ANTHROPIC_URL, AnthropicClient, ChatCompletionsClient, JevClient


@pytest.fixture
def transport() -> JsonTransport:
    """Transport with a single retry and no real waiting."""
    transport = JsonTransport(httpx.Client(timeout=5), max_attempts=2)
    transport._post.retry.wait = lambda _state: 0  # type: ignore[attr-defined]
    return transport


@pytest.mark.parametrize(
    "text",
    ['{"a": 1}', '```json\n{"a": 1}\n```', 'Here you go: {"a": 1} done', '{bad} {"a": 1}'],
)
def test_parse_json_object_tolerates_wrapping(text: str) -> None:
    assert parse_json_object(text) == {"a": 1}


@pytest.mark.parametrize("text", ["no json", '{"a": 1', "[1, 2]"])
def test_parse_json_object_rejects_garbage(text: str) -> None:
    with pytest.raises(ResponseFormatError):
        parse_json_object(text)


@respx.mock
def test_anthropic_client_parses_text_and_usage(transport: JsonTransport) -> None:
    route = respx.post(ANTHROPIC_URL).respond(
        json={
            "content": [{"type": "text", "text": '{"gross": 1}'}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )
    result = AnthropicClient(transport, "key").complete("m", "s", "u", 100, {"type": "disabled"})
    assert result.payload == {"gross": 1}
    assert (result.usage.input_tokens, result.usage.output_tokens) == (10, 5)
    assert route.calls.last.request.headers["x-api-key"] == "key"


@respx.mock
def test_chat_client_uses_token_field(transport: JsonTransport) -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").respond(
        json={
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
    )
    client = ChatCompletionsClient.for_openai(transport, "key")
    result = client.complete("m", "s", "u", 50, token_field="max_completion_tokens")
    assert result.payload == {"ok": True}
    assert b'"max_completion_tokens":50' in route.calls.last.request.content


@respx.mock
def test_chat_client_requires_choices(transport: JsonTransport) -> None:
    respx.post("https://api.openai.com/v1/chat/completions").respond(json={"choices": []})
    with pytest.raises(ResponseFormatError):
        ChatCompletionsClient.for_openai(transport, "key").complete("m", "s", "u", 5)


@respx.mock
def test_jev_client_reads_nested_result(transport: JsonTransport) -> None:
    respx.post("https://api.cloudflare.com/client/v4/accounts/acc/ai/run").respond(
        json={
            "result": {
                "state": "Completed",
                "result": {
                    "answers": {"x": {"type": "noul", "noul": 0.9}},
                    "usage": {"input_tokens": 7, "output_tokens": 1},
                },
            },
            "success": True,
        }
    )
    result = JevClient(transport, "acc", "token").evaluate("text", {"x": {"type": "noul"}})
    assert result.payload == {"x": {"type": "noul", "noul": 0.9}}
    assert result.usage.input_tokens == 7


@respx.mock
def test_jev_client_requires_answers(transport: JsonTransport) -> None:
    respx.post("https://api.cloudflare.com/client/v4/accounts/acc/ai/run").respond(
        json={"result": {}}
    )
    with pytest.raises(ResponseFormatError):
        JevClient(transport, "acc", "token").evaluate("text", {})


@respx.mock
def test_transient_errors_are_retried(transport: JsonTransport) -> None:
    route = respx.post(ANTHROPIC_URL).mock(
        side_effect=[
            httpx.Response(529),
            httpx.Response(200, json={"content": [{"text": "{}"}], "usage": {}}),
        ]
    )
    AnthropicClient(transport, "key").complete("m", "s", "u", 10, {})
    assert route.call_count == 2


@respx.mock
def test_transient_errors_give_up_after_last_attempt(transport: JsonTransport) -> None:
    respx.post(ANTHROPIC_URL).respond(status_code=429)
    with pytest.raises(TransientProviderError):
        AnthropicClient(transport, "key").complete("m", "s", "u", 10, {})


@respx.mock
def test_permanent_errors_are_not_retried(transport: JsonTransport) -> None:
    route = respx.post(ANTHROPIC_URL).respond(status_code=400, text="bad request")
    with pytest.raises(ProviderError, match="400"):
        AnthropicClient(transport, "key").complete("m", "s", "u", 10, {})
    assert route.call_count == 1


@respx.mock
def test_timeouts_are_transient(transport: JsonTransport) -> None:
    respx.post(ANTHROPIC_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(TransientProviderError, match="timeout"):
        AnthropicClient(transport, "key").complete("m", "s", "u", 10, {})
