"""Gemini provider: official generateContent client and LLM_PROVIDER selection.

All HTTP is mocked. No test contacts the network or requires a real API key.
"""
from __future__ import annotations

import io
import json
import os
import socket
import urllib.error
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from diff_review_agent.agent import review_diff
from diff_review_agent.providers.base import LLMMessage
from diff_review_agent.providers.gemini_provider import GeminiProvider
from diff_review_agent.providers.openai_provider import OpenAIProvider


_SIMPLE_DIFF = """\
diff --git a/calculator.py b/calculator.py
index 1111111..2222222 100644
--- a/calculator.py
+++ b/calculator.py
@@ -1,3 +1,4 @@
 def add(a, b):
+    return a + b
     pass
"""


class _MockConfig:
    """Minimal config used by review_diff. Defaults match the OpenAI path."""

    def __init__(self, **overrides: Any) -> None:
        self._values: Dict[str, Any] = {
            "diff_max_bytes": 1_000_000,
            "diff_max_files": 50,
            "max_retries": 1,
            "max_response_tokens": 1000,
            "timeout_seconds": 30,
            "max_tool_calls": 10,
            "llm_provider": "openai",
        }
        self._values.update(overrides)

    def get(self, key: str, default: Any = None) -> Any:
        if default is None and key not in self._values:
            raise KeyError(key)
        return self._values.get(key, default)


def _diff_input(tmp_path):
    path = tmp_path / "change.diff"
    path.write_text(_SIMPLE_DIFF, encoding="utf-8")

    class _Input:
        type = "file"

    item = _Input()
    item.path = str(path)
    return item


def _http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        code=code,
        msg="error",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(body),
    )


def _ok_response(text: str = "hello from gemini", finish: str = "STOP") -> MagicMock:
    body = {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": finish,
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(body).encode()
    return mock_resp


def _without(*names: str) -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in names}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_gemini_provider_is_configured():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        assert GeminiProvider().is_configured()


def test_gemini_provider_not_configured():
    with patch.dict(os.environ, _without("GEMINI_API_KEY"), clear=True):
        assert not GeminiProvider().is_configured()


def test_gemini_provider_complete_not_configured():
    with patch.dict(os.environ, _without("GEMINI_API_KEY"), clear=True):
        result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "not configured" in result.error.lower()
    assert "GEMINI_API_KEY" in result.error


def test_gemini_default_model_and_official_host():
    with patch.dict(os.environ, _without("GEMINI_MODEL", "GEMINI_BASE_URL"), clear=True):
        os.environ["GEMINI_API_KEY"] = "fake-key"
        provider = GeminiProvider()
    assert provider._model == "gemini-2.5-flash"
    assert provider._base_url == "https://generativelanguage.googleapis.com/v1beta"


def test_gemini_custom_model_and_base_url():
    with patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "fake-key",
            "GEMINI_MODEL": "gemini-2.0-flash",
            "GEMINI_BASE_URL": "https://example.test/v1beta/",
        },
        clear=False,
    ):
        provider = GeminiProvider()
    assert provider._model == "gemini-2.0-flash"
    assert provider._base_url == "https://example.test/v1beta"
    assert provider._endpoint().endswith("/models/gemini-2.0-flash:generateContent")


# ---------------------------------------------------------------------------
# Successful generateContent response
# ---------------------------------------------------------------------------


def test_gemini_complete_success_parses_candidates():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        provider = GeminiProvider()
        with patch("urllib.request.urlopen", return_value=_ok_response()) as opened:
            result = provider.complete(
                [LLMMessage("system", "rules"), LLMMessage("user", "review this")]
            )

    assert not result.is_error
    assert result.content == "hello from gemini"
    assert result.finish_reason == "STOP"

    request = opened.call_args.args[0]
    assert request.full_url.startswith(
        "https://generativelanguage.googleapis.com/v1beta/models/"
    )
    assert request.full_url.endswith(":generateContent")
    assert request.get_header("X-goog-api-key") == "fake-key"
    assert "key=" not in request.full_url
    sent = json.loads(request.data.decode())
    assert sent["systemInstruction"]["parts"][0]["text"] == "rules"
    assert sent["contents"][0]["role"] == "user"
    assert sent["contents"][0]["parts"][0]["text"] == "review this"
    assert sent["generationConfig"]["maxOutputTokens"] == 1000


def test_gemini_joins_multiple_text_parts():
    body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "hel"}, {"text": "lo"}]},
                "finishReason": "STOP",
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(body).encode()
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = GeminiProvider().complete([LLMMessage("user", "hi")])
    assert result.content == "hello"


def test_gemini_maps_assistant_role_to_model():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        provider = GeminiProvider()
        with patch("urllib.request.urlopen", return_value=_ok_response()) as opened:
            provider.complete(
                [LLMMessage("user", "q"), LLMMessage("assistant", "a"), LLMMessage("user", "again")]
            )
    roles = [item["role"] for item in json.loads(opened.call_args.args[0].data)["contents"]]
    assert roles == ["user", "model", "user"]


# ---------------------------------------------------------------------------
# Authentication, quota, malformed, timeout, network
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [401, 403])
def test_gemini_authentication_error(code: int):
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=_http_error(code, b"bad key")):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "authentication" in result.error.lower()
    assert str(code) in result.error


def test_gemini_quota_error():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch(
            "urllib.request.urlopen",
            side_effect=_http_error(429, b'{"error":"quota exceeded"}'),
        ):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "quota" in result.error.lower()
    assert "429" in result.error


def test_gemini_timeout():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "timed out" in result.error.lower()


def test_gemini_network_failure():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "network error" in result.error.lower()


def test_gemini_malformed_json():
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = b"not json at all"
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "json" in result.error.lower()


def test_gemini_malformed_missing_candidates():
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps({"unexpected": "shape"}).encode()
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "candidates" in result.error.lower()


def test_gemini_malformed_missing_text_part():
    body = {"candidates": [{"content": {"parts": [{"inlineData": {}}]}, "finishReason": "STOP"}]}
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(body).encode()
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = GeminiProvider().complete([LLMMessage("user", "test")])
    assert result.is_error
    assert "text" in result.error.lower()


def test_gemini_api_key_not_logged(capsys):
    with patch.dict(os.environ, {"GEMINI_API_KEY": "super-secret-gemini-key"}, clear=False):
        with patch(
            "urllib.request.urlopen",
            side_effect=_http_error(401, b"key super-secret-gemini-key rejected"),
        ):
            result = GeminiProvider().complete([LLMMessage("user", "hi")])
    captured = capsys.readouterr()
    assert "super-secret-gemini-key" not in captured.out
    assert "super-secret-gemini-key" not in captured.err
    assert "super-secret-gemini-key" not in (result.error or "")
    assert "[REDACTED]" in (result.error or "")


# ---------------------------------------------------------------------------
# Provider selection through review_diff
# ---------------------------------------------------------------------------


def test_selects_gemini_when_configured(tmp_path):
    from diff_review_agent.providers.base import LLMResponse

    diff_input = _diff_input(tmp_path)
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"},
        clear=False,
    ):
        with patch(
            "diff_review_agent.providers.gemini_provider.GeminiProvider.complete",
            return_value=LLMResponse(content="{}"),
        ) as complete:
            with patch(
                "diff_review_agent.providers.openai_provider.OpenAIProvider.complete"
            ) as openai_complete:
                review_diff(diff_input, _MockConfig(llm_provider="gemini"), mode="llm")
    assert complete.called
    assert not openai_complete.called


def test_gemini_selected_does_not_fall_back_when_key_missing(tmp_path):
    diff_input = _diff_input(tmp_path)
    with patch.dict(os.environ, _without("GEMINI_API_KEY"), clear=True):
        result = review_diff(diff_input, _MockConfig(llm_provider="gemini"), mode="llm")
    assert result.review_metadata.model_provider_mode == "error"
    limitations = " ".join(result.review_metadata.limitations)
    assert "GEMINI_API_KEY" in limitations
    assert result.findings == []


def test_gemini_provider_error_is_not_rewritten_as_demo(tmp_path):
    from diff_review_agent.providers.base import LLMResponse

    diff_input = _diff_input(tmp_path)
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        with patch(
            "diff_review_agent.providers.gemini_provider.GeminiProvider.complete",
            return_value=LLMResponse(error="HTTP 429 (quota): resource exhausted"),
        ):
            result = review_diff(diff_input, _MockConfig(llm_provider="gemini"), mode="llm")
    assert result.review_metadata.model_provider_mode == "error"
    assert "429" in result.summary or "quota" in result.summary
    assert result.review_metadata.model_provider_mode != "demo"


def test_openai_still_selected_by_default(tmp_path):
    diff_input = _diff_input(tmp_path)
    with patch.dict(os.environ, _without("OPENAI_API_KEY", "GEMINI_API_KEY"), clear=True):
        result = review_diff(diff_input, _MockConfig(), mode="llm")
    assert result.review_metadata.model_provider_mode == "demo"
    assert "OPENAI_API_KEY" in " ".join(result.review_metadata.limitations)


def test_openai_provider_class_unchanged_when_selected(tmp_path):
    from diff_review_agent.providers.base import BaseProvider, LLMResponse

    diff_input = _diff_input(tmp_path)
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
        with patch(
            "diff_review_agent.providers.openai_provider.OpenAIProvider.complete",
            return_value=LLMResponse(error="stopped for test"),
        ) as complete:
            with patch(
                "diff_review_agent.providers.gemini_provider.GeminiProvider.complete"
            ) as gemini_complete:
                review_diff(diff_input, _MockConfig(llm_provider="openai"), mode="llm")
    assert complete.called
    assert not gemini_complete.called
    assert issubclass(OpenAIProvider, BaseProvider)
    assert issubclass(GeminiProvider, BaseProvider)


def test_demo_mode_ignores_gemini_selection(tmp_path):
    diff_input = _diff_input(tmp_path)
    with patch(
        "diff_review_agent.providers.gemini_provider.GeminiProvider.complete"
    ) as complete:
        result = review_diff(diff_input, _MockConfig(llm_provider="gemini"), mode="demo")
    assert result.review_metadata.model_provider_mode == "demo"
    assert not complete.called


def test_config_reads_llm_provider_from_environment(monkeypatch):
    import importlib

    import diff_review_agent.config as config_mod

    monkeypatch.setenv("LLM_PROVIDER", "GeMiNi")
    reloaded = importlib.reload(config_mod)
    try:
        assert reloaded.get_config().get("llm_provider") == "gemini"
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        importlib.reload(config_mod)


def test_config_defaults_to_openai(monkeypatch):
    import importlib

    import diff_review_agent.config as config_mod

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    reloaded = importlib.reload(config_mod)
    try:
        assert reloaded.get_config().get("llm_provider") == "openai"
    finally:
        importlib.reload(config_mod)


def test_unsupported_provider_is_an_error_not_demo(tmp_path):
    diff_input = _diff_input(tmp_path)
    result = review_diff(diff_input, _MockConfig(llm_provider="anthropic"), mode="llm")
    assert result.review_metadata.model_provider_mode == "error"
    assert "not supported" in result.summary.lower() or "Unsupported" in result.summary
