"""Clients for Anthropic, OpenAI-compatible chat endpoints and Jev on Cloudflare Workers AI.

Context: Each client turns one prompt into one CallResult. |
Input: Model id, prompts, credentials. |
Output: CallResult.
"""

from __future__ import annotations

from typing import Any

from idp.errors import ResponseFormatError
from idp.providers.base import CallResult, JsonTransport, Usage, parse_json_object

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai"
JEV_MODEL = "typesafe/jev"


class AnthropicClient:
    """Calls the Anthropic Messages API."""

    def __init__(self, transport: JsonTransport, api_key: str) -> None:
        self._transport = transport
        self._headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}

    def complete(
        self, model: str, system: str, user: str, max_tokens: int, thinking: dict[str, Any]
    ) -> CallResult:
        """Ask for a JSON object and return it parsed.

        Args:
            model: Model id.
            system: System prompt.
            user: User message.
            max_tokens: Output limit.
            thinking: Thinking setting; this benchmark answers without extended thinking.

        Raises:
            ProviderError: On HTTP failure.
            ResponseFormatError: If the answer holds no JSON object.
        """
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "thinking": thinking,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data, latency = self._transport.post(ANTHROPIC_URL, self._headers, body)
        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage = data.get("usage", {})
        return CallResult(
            parse_json_object(text),
            Usage(int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))),
            latency,
        )


class ChatCompletionsClient:
    """Calls an OpenAI-compatible chat completions endpoint (OpenAI or Workers AI)."""

    def __init__(self, transport: JsonTransport, base_url: str, api_key: str) -> None:
        self._transport = transport
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}

    @classmethod
    def for_openai(cls, transport: JsonTransport, api_key: str) -> ChatCompletionsClient:
        """Client for the OpenAI API."""
        return cls(transport, "https://api.openai.com/v1", api_key)

    @classmethod
    def for_workers_ai(
        cls, transport: JsonTransport, account_id: str, api_token: str
    ) -> ChatCompletionsClient:
        """Client for the OpenAI-compatible endpoint of Cloudflare Workers AI."""
        return cls(transport, CLOUDFLARE_API.format(account=account_id) + "/v1", api_token)

    def complete(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        *,
        token_field: str = "max_tokens",
        extra: dict[str, Any] | None = None,
    ) -> CallResult:
        """Ask for a JSON object and return it parsed.

        Args:
            model: Model id.
            system: System prompt.
            user: User message.
            max_tokens: Output limit.
            token_field: Name of the output limit field; newer OpenAI models expect
                "max_completion_tokens".
            extra: Provider-specific body fields such as reasoning effort.

        Raises:
            ProviderError: On HTTP failure.
            ResponseFormatError: If the answer holds no JSON object.
        """
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            token_field: max_tokens,
            "response_format": {"type": "json_object"},
            **(extra or {}),
        }
        data, latency = self._transport.post(self._url, self._headers, body)
        choices = data.get("choices") or []
        if not choices:
            raise ResponseFormatError(f"no choices in answer of {model}")
        text = choices[0].get("message", {}).get("content") or ""
        usage = data.get("usage") or {}
        return CallResult(
            parse_json_object(text),
            Usage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))),
            latency,
        )


class JevClient:
    """Calls TypeSafe Jev through the Cloudflare Workers AI REST API."""

    def __init__(self, transport: JsonTransport, account_id: str, api_token: str) -> None:
        self._transport = transport
        self._url = CLOUDFLARE_API.format(account=account_id) + "/run"
        self._headers = {"Authorization": f"Bearer {api_token}"}

    def evaluate(self, state: str, questions: dict[str, Any]) -> CallResult:
        """Answer typed questions about a document.

        Args:
            state: Document text.
            questions: Jev questions keyed by name.

        Returns:
            CallResult whose payload maps question names to answers.

        Raises:
            ProviderError: On HTTP failure.
            ResponseFormatError: If the answer lacks the answers object.
        """
        body = {"model": JEV_MODEL, "input": {"state": state, "questions": questions}}
        data, latency = self._transport.post(self._url, self._headers, body)
        result = data.get("result", data)
        if isinstance(result.get("result"), dict):
            result = result["result"]
        answers = result.get("answers")
        if not isinstance(answers, dict):
            raise ResponseFormatError("Jev answer has no 'answers' object")
        usage = result.get("usage") or {}
        return CallResult(
            answers,
            Usage(int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))),
            latency,
        )
