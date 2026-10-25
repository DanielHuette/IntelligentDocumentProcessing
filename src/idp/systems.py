"""The document-processing setups that the benchmark compares.

Context: Declares models, prices and how each setup answers one document. |
Input: Settings. |
Output: Runnable systems.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from idp.config import Settings
from idp.domain import Classification, Extraction
from idp.parsing import (
    classification_from_jev,
    classification_from_payload,
    extraction_from_payload,
)
from idp.prompts import EXTRACTION_SYSTEM_PROMPT, full_system_prompt, jev_questions, user_message
from idp.providers.base import CallResult, JsonTransport, Usage
from idp.providers.clients import AnthropicClient, ChatCompletionsClient, JevClient

PRICES_CHECKED = "2026-10-08"
MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class Price:
    """US dollars per million tokens."""

    input: Decimal
    output: Decimal

    def cost(self, usage: Usage) -> Decimal:
        """Cost of one call in US dollars."""
        return (self.input * usage.input_tokens + self.output * usage.output_tokens) / MILLION


PRICES: dict[str, Price] = {
    "typesafe/jev": Price(Decimal("0.042"), Decimal("0")),
    "claude-haiku-5-5": Price(Decimal("0.10"), Decimal("0.50")),
    "claude-sonnet-5-5": Price(Decimal("2"), Decimal("10")),
    "gpt-5.6-luna": Price(Decimal("0.20"), Decimal("1.20")),
    "gpt-5.6-terra": Price(Decimal("2"), Decimal("12")),
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": Price(Decimal("0.293"), Decimal("2.253")),
    "@cf/mistralai/mistral-small-3.1-24b-instruct": Price(Decimal("0.351"), Decimal("0.555")),
    "@cf/deepseek-ai/deepseek-v4-pro-0813": Price(Decimal("1.32"), Decimal("3.96")),
}


@dataclass(frozen=True, slots=True)
class Answer:
    """What a system says about one document, with its cost and latency."""

    classification: Classification
    extraction: Extraction
    latency_ms: float
    cost_usd: Decimal
    calls: dict[str, float] = field(default_factory=dict)


Runner = Callable[[str], Answer]


@dataclass(frozen=True, slots=True)
class SystemSpec:
    """A named setup and the factory that builds its runner."""

    key: str
    label: str
    provider: str
    build: Callable[[Clients], Runner]


class Clients:
    """Lazily created provider clients sharing one HTTP connection pool."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.request_timeout_seconds)
        self._transport = JsonTransport(self._http, settings.max_attempts)

    def close(self) -> None:
        """Release network connections."""
        self._http.close()

    def anthropic(self) -> AnthropicClient:
        """Anthropic client; raises ConfigError without a key."""
        return AnthropicClient(self._transport, self._settings.require("anthropic_api_key"))

    def openai(self) -> ChatCompletionsClient:
        """OpenAI client; raises ConfigError without a key."""
        return ChatCompletionsClient.for_openai(
            self._transport, self._settings.require("openai_api_key")
        )

    def workers_ai(self) -> ChatCompletionsClient:
        """Workers AI chat client; raises ConfigError without account and token."""
        return ChatCompletionsClient.for_workers_ai(
            self._transport,
            self._settings.require("cloudflare_account_id"),
            self._settings.require("cloudflare_api_token"),
        )

    def jev(self) -> JevClient:
        """Jev client; raises ConfigError without account and token."""
        return JevClient(
            self._transport,
            self._settings.require("cloudflare_account_id"),
            self._settings.require("cloudflare_api_token"),
        )


def _single(model: str, call: Callable[[str, str, str], CallResult]) -> Runner:
    system = full_system_prompt()

    def run(text: str) -> Answer:
        result = call(model, system, user_message(text))
        return Answer(
            classification_from_payload(result.payload),
            extraction_from_payload(result.payload),
            result.latency_ms,
            PRICES[model].cost(result.usage),
            {model: result.latency_ms},
        )

    return run


NO_THINKING: dict[str, dict[str, Any]] = {
    "claude-haiku-5-5": {"type": "disabled"},
    "claude-sonnet-5-5": {"type": "between_tools"},
}


def _anthropic(model: str) -> Callable[[Clients], Runner]:
    def build(clients: Clients) -> Runner:
        client = clients.anthropic()
        thinking = NO_THINKING[model]
        return _single(model, lambda m, s, u: client.complete(m, s, u, 2000, thinking))

    return build


def _openai(model: str) -> Callable[[Clients], Runner]:
    def build(clients: Clients) -> Runner:
        client = clients.openai()
        extra: dict[str, Any] = {"reasoning_effort": "low"}
        return _single(
            model,
            lambda m, s, u: client.complete(
                m, s, u, 4000, token_field="max_completion_tokens", extra=extra
            ),
        )

    return build


def _workers_ai(model: str, max_tokens: int = 1200) -> Callable[[Clients], Runner]:
    def build(clients: Clients) -> Runner:
        client = clients.workers_ai()
        return _single(model, lambda m, s, u: client.complete(m, s, u, max_tokens))

    return build


def _hybrid(clients: Clients) -> Runner:
    """Jev decides while Haiku extracts; both run in parallel like in the n8n workflow."""
    jev, haiku = clients.jev(), clients.anthropic()
    questions = jev_questions()
    model = "claude-haiku-5-5"
    pool = ThreadPoolExecutor(max_workers=2)

    def run(text: str) -> Answer:
        jev_future = pool.submit(jev.evaluate, text, questions)
        haiku_future = pool.submit(
            haiku.complete,
            model,
            EXTRACTION_SYSTEM_PROMPT,
            user_message(text),
            1500,
            NO_THINKING[model],
        )
        decided, extracted = jev_future.result(), haiku_future.result()
        cost = PRICES["typesafe/jev"].cost(decided.usage) + PRICES[model].cost(extracted.usage)
        return Answer(
            classification_from_jev(decided.payload),
            extraction_from_payload(extracted.payload),
            max(decided.latency_ms, extracted.latency_ms),
            cost,
            {"typesafe/jev": decided.latency_ms, model: extracted.latency_ms},
        )

    return run


SYSTEMS: tuple[SystemSpec, ...] = (
    SystemSpec("hybrid", "Jev + Claude Haiku 5.5 (hybrid)", "TypeSafe + Anthropic", _hybrid),
    SystemSpec("haiku", "Claude Haiku 5.5", "Anthropic", _anthropic("claude-haiku-5-5")),
    SystemSpec("sonnet", "Claude Sonnet 5.5", "Anthropic", _anthropic("claude-sonnet-5-5")),
    SystemSpec("gpt_luna", "GPT-5.6 Luna", "OpenAI", _openai("gpt-5.6-luna")),
    SystemSpec("gpt_terra", "GPT-5.6 Terra", "OpenAI", _openai("gpt-5.6-terra")),
    SystemSpec(
        "llama",
        "Llama 3.3 70B",
        "Cloudflare",
        _workers_ai("@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
    ),
    SystemSpec(
        "mistral",
        "Mistral Small 3.1 24B",
        "Cloudflare",
        _workers_ai("@cf/mistralai/mistral-small-3.1-24b-instruct"),
    ),
    SystemSpec(
        "deepseek",
        "DeepSeek V4 Pro",
        "Cloudflare",
        _workers_ai("@cf/deepseek-ai/deepseek-v4-pro-0813", 4000),
    ),
)

SYSTEMS_BY_KEY: dict[str, SystemSpec] = {spec.key: spec for spec in SYSTEMS}
