"""HTTP transport with retries, timing and JSON extraction.

Context: Shared by every provider client. |
Input: URL, headers, JSON body. |
Output: Parsed response and latency of the successful attempt.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from idp.errors import ProviderError, ResponseFormatError, TransientProviderError

logger = logging.getLogger(__name__)

TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504, 529})


@dataclass(frozen=True, slots=True)
class Usage:
    """Tokens billed for one call."""

    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class CallResult:
    """Parsed answer of one model call."""

    payload: dict[str, Any]
    usage: Usage
    latency_ms: float


class JsonTransport:
    """Posts JSON and retries transient failures with exponential backoff."""

    def __init__(self, client: httpx.Client, max_attempts: int) -> None:
        self._client = client
        self._post = retry(
            retry=retry_if_exception_type(TransientProviderError),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(multiplier=2, max=40),
            reraise=True,
        )(self._post_once)

    def post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> tuple[Any, float]:
        """Send a request and return the decoded body and its latency in milliseconds.

        Raises:
            TransientProviderError: After the last retry of a temporary failure.
            ProviderError: For permanent HTTP errors.
            ResponseFormatError: If the body is not JSON.
        """
        return self._post(url, headers, body)

    def _post_once(
        self, url: str, headers: dict[str, str], body: dict[str, Any]
    ) -> tuple[Any, float]:
        started = time.perf_counter()
        try:
            response = self._client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as error:
            raise TransientProviderError(f"timeout calling {url}") from error
        except httpx.TransportError as error:
            raise TransientProviderError(f"network error calling {url}: {error}") from error
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code in TRANSIENT_STATUS:
            logger.warning("transient status %s from %s", response.status_code, url)
            raise TransientProviderError(f"status {response.status_code} from {url}")
        if response.is_error:
            raise ProviderError(f"status {response.status_code} from {url}: {response.text[:300]}")
        try:
            return response.json(), latency_ms
        except json.JSONDecodeError as error:
            raise ResponseFormatError(f"non-JSON body from {url}") from error


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output, tolerating code fences and prose.

    Args:
        text: Raw model output.

    Returns:
        The decoded object.

    Raises:
        ResponseFormatError: If no JSON object can be decoded.
    """
    start = text.find("{")
    if start < 0:
        raise ResponseFormatError(f"no JSON object in model output: {text[:120]!r}")
    decoder = json.JSONDecoder()
    while start >= 0:
        try:
            value, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise ResponseFormatError(f"invalid JSON object in model output: {text[:120]!r}")
