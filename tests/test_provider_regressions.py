"""Regression coverage for provider response and retry boundaries."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from diff_review_agent.providers.base import LLMMessage
from diff_review_agent.providers.openai_provider import OpenAIProvider


@pytest.mark.parametrize("content", [None, 42, {"not": "text"}])
def test_openai_provider_rejects_non_string_message_content(content):
    response = MagicMock()
    response.__enter__ = lambda instance: instance
    response.__exit__ = MagicMock(return_value=False)
    response.read.return_value = json.dumps(
        {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
    ).encode()

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
        with patch("urllib.request.urlopen", return_value=response):
            result = OpenAIProvider().complete([LLMMessage("user", "review")])

    assert result.is_error
    assert "content is not text" in (result.error or "")
