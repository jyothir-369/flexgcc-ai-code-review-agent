"""Google Gemini provider using the official generateContent REST API.

Uses only the Python standard library. Credentials come from the environment
and are never written to logs or error messages.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from diff_review_agent.providers.base import BaseProvider, LLMMessage, LLMResponse

# Official Generative Language API. Override with GEMINI_BASE_URL only for a
# compatible endpoint; the path below is always appended.
_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiProvider(BaseProvider):
    """Gemini generateContent provider.

    Environment variables:
      GEMINI_API_KEY   — required; sent as the ``x-goog-api-key`` header
      GEMINI_MODEL     — optional, defaults to gemini-2.5-flash
      GEMINI_BASE_URL  — optional, defaults to the official v1beta host
    """

    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self._api_key: Optional[str] = api_key or None
        self._model: str = os.environ.get("GEMINI_MODEL", "").strip() or _DEFAULT_MODEL
        base = os.environ.get("GEMINI_BASE_URL", "").strip() or _DEFAULT_BASE_URL
        self._base_url: str = base.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _build_payload(
        self, messages: List[LLMMessage], max_tokens: int
    ) -> Dict[str, Any]:
        """Map chat messages onto Gemini's generateContent body.

        System messages become ``systemInstruction``. User and assistant
        turns become ``contents`` with roles ``user`` and ``model``.
        """
        system_parts: List[str] = []
        contents: List[Dict[str, Any]] = []
        for message in messages:
            text = message.content if isinstance(message.content, str) else str(message.content)
            role = (message.role or "user").lower()
            if role == "system":
                system_parts.append(text)
                continue
            gemini_role = "model" if role in {"assistant", "model"} else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})

        if not contents:
            # generateContent requires at least one content turn.
            contents.append({"role": "user", "parts": [{"text": ""}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }
        return payload

    def _endpoint(self) -> str:
        model = urllib.parse.quote(self._model, safe="")
        return f"{self._base_url}/models/{model}:generateContent"

    def complete(
        self,
        messages: List[LLMMessage],
        max_tokens: int = 1000,
        timeout: int = 30,
    ) -> LLMResponse:
        if not self.is_configured():
            return LLMResponse(error="Provider not configured: GEMINI_API_KEY is not set.")

        body = json.dumps(self._build_payload(messages, max_tokens)).encode("utf-8")
        # Key travels only in the header. Never place it in the URL or an error string.
        req = urllib.request.Request(
            self._endpoint(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key or "",
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
            kind = _classify_http_error(exc.code)
            return LLMResponse(error=f"HTTP {exc.code} ({kind}): {detail}")
        except urllib.error.URLError as exc:
            return LLMResponse(error=f"Network error: {exc.reason}")
        except OSError as exc:
            return LLMResponse(error=f"Connection error: {exc}")
        except Exception as exc:  # never let a transport error escape
            return LLMResponse(
                error=f"Unexpected error contacting provider: {type(exc).__name__}: {exc}"
            )

        try:
            data: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            return LLMResponse(error=f"Invalid JSON from provider: {exc}")

        return _parse_generate_content(data, raw)


def _classify_http_error(code: int) -> str:
    if code in (401, 403):
        return "authentication"
    if code == 429:
        return "quota"
    if code == 400:
        return "bad request"
    return "http error"


def _parse_generate_content(data: Dict[str, Any], raw: str) -> LLMResponse:
    """Read candidates[0].content.parts[].text from a generateContent body."""
    if not isinstance(data, dict):
        return LLMResponse(error=f"Unexpected response structure: not an object. Raw: {raw[:200]}")

    # The API reports a blocked prompt without candidates.
    prompt_feedback = data.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason") if isinstance(prompt_feedback, dict) else None

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        if block_reason:
            return LLMResponse(error=f"Gemini blocked the prompt: {block_reason}")
        return LLMResponse(
            error=f"Unexpected response structure: missing candidates. Raw: {raw[:200]}"
        )

    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return LLMResponse(error=f"Unexpected response structure: candidate is not an object. Raw: {raw[:200]}")

    finish_reason = str(candidate.get("finishReason") or "STOP")
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        return LLMResponse(
            error=f"Unexpected response structure: missing content.parts. Raw: {raw[:200]}",
            finish_reason=finish_reason,
        )

    texts: List[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    if not texts:
        return LLMResponse(
            error=f"Unexpected response structure: no text part. Raw: {raw[:200]}",
            finish_reason=finish_reason,
        )
    return LLMResponse(content="".join(texts), finish_reason=finish_reason)
