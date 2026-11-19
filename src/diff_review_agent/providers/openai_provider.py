"""OpenAI-compatible provider using stdlib urllib (no third-party packages)."""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from diff_review_agent.providers.base import BaseProvider, LLMMessage, LLMResponse

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(BaseProvider):
    """OpenAI-compatible chat-completion provider.

    Reads credentials from environment variables:
      OPENAI_API_KEY   — required for LLM mode
      OPENAI_MODEL     — optional, defaults to gpt-4o-mini
      OPENAI_BASE_URL  — optional, defaults to https://api.openai.com/v1
    """

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self._api_key: Optional[str] = api_key or None
        self._model: str = os.environ.get("OPENAI_MODEL", "").strip() or _DEFAULT_MODEL
        base = os.environ.get("OPENAI_BASE_URL", "").strip() or _DEFAULT_BASE_URL
        self._base_url: str = base.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(
        self,
        messages: List[LLMMessage],
        max_tokens: int = 1000,
        timeout: int = 30,
    ) -> LLMResponse:
        if not self.is_configured():
            return LLMResponse(error="Provider not configured: OPENAI_API_KEY is not set.")

        payload = {
            "model": self._model,
            "messages": [m.to_dict() for m in messages],
            "max_tokens": max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        url = f"{self._base_url}/chat/completions"

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except socket.timeout:
            return LLMResponse(error=f"Request timed out after {timeout}s.")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")[:500]
            except Exception:
                detail = str(exc)
            if self._api_key and self._api_key in detail:
                detail = detail.replace(self._api_key, "[REDACTED]")
            return LLMResponse(error=f"HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            return LLMResponse(error=f"Network error: {exc.reason}")
        except OSError as exc:
            return LLMResponse(error=f"Connection error: {exc}")
        except Exception as exc:  # catch-all: never let a connection error propagate
            return LLMResponse(error=f"Unexpected error contacting provider: {type(exc).__name__}: {exc}")

        try:
            data: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            return LLMResponse(error=f"Invalid JSON from provider: {exc}")

        try:
            content = data["choices"][0]["message"]["content"]
            finish_reason: str = data["choices"][0].get("finish_reason", "stop")
        except (KeyError, IndexError, TypeError) as exc:
            return LLMResponse(error=f"Unexpected response structure: {exc}. Raw: {raw[:200]}")
        if not isinstance(content, str):
            return LLMResponse(
                error="Unexpected response structure: choices[0].message.content is not text. "
                f"Raw: {raw[:200]}"
            )
        return LLMResponse(content=content, finish_reason=finish_reason)
