"""Unit tests for the review agent."""

import json
import os
import tempfile
from typing import Any, Dict, List

import pytest

from diff_review_agent.agent import _build_user_message, _review_llm, review_diff
from diff_review_agent.providers.base import BaseProvider, LLMMessage, LLMResponse
from diff_review_agent.schemas import DiffSummary


def test_review_diff_demo_mode():
    # Create a dummy diff file for parsing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write("""diff --git a/example.py b/example.py
index abc1234..def5678 100644
--- a/example.py
+++ b/example.py
@@ -1,4 +1,5 @@
 def example():
     print("hello")
+    print("world")
 """)
        diff_path = f.name

    diff_input = type("DiffInput", (), {"type": "file", "path": diff_path})()
    config = type("Config", (), {"get": lambda self, key: 1000000})()

    result = review_diff(diff_input, config, mode="demo")

    assert hasattr(result, "summary")
    assert hasattr(result, "overall_risk")
    assert hasattr(result, "findings")
    assert hasattr(result, "review_metadata")
    assert result.review_metadata.model_provider_mode == "demo"

    # Cleanup
    os.unlink(diff_path)


def test_review_diff_missing_file():
    diff_input = type("DiffInput", (), {"type": "file", "path": "/nonexistent/path.diff"})()
    config = type("Config", (), {"get": lambda self, key: 1000000})()
    result = review_diff(diff_input, config, mode="demo")
    assert result.summary.startswith("Failed to parse diff")
    assert len(result.review_metadata.limitations) > 0
    assert any("Parse error" in limitation for limitation in result.review_metadata.limitations)


def test_review_diff_empty_file():
    # Create empty diff file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write("")
        diff_path = f.name

    diff_input = type("DiffInput", (), {"type": "file", "path": diff_path})()
    config = type("Config", (), {"get": lambda self, key: 1000000})()

    result = review_diff(diff_input, config, mode="demo")
    assert hasattr(result, "summary")
    assert result.review_metadata.model_provider_mode == "demo"

    # Cleanup
    os.unlink(diff_path)


def _write_diff(text: str) -> str:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False)
    handle.write(text)
    handle.close()
    return handle.name


class _Config:
    def __init__(self, **overrides: Any) -> None:
        self.values: Dict[str, Any] = {
            "diff_max_bytes": 1_000_000,
            "diff_max_files": 50,
            "max_retries": 1,
            "max_response_tokens": 200,
            "timeout_seconds": 5,
            "max_tool_calls": 10,
            "max_context_tokens": 2000,
        }
        self.values.update(overrides)

    def get(self, key: str, default: Any = None) -> Any:
        if default is None and key not in self.values:
            raise KeyError(key)
        return self.values.get(key, default)


_VALID = {
    "summary": "No defect found in the supplied diff.",
    "overall_risk": "low",
    "findings": [],
    "review_metadata": {
        "input_type": "file",
        "reviewed_file_count": 1,
        "model_provider_mode": "llm",
        "limitations": [],
    },
}


class _ScriptedProvider(BaseProvider):
    def __init__(self, responses: List[LLMResponse]) -> None:
        self._responses = list(responses)
        self.timeouts: List[int] = []
        self.call_count = 0

    def is_configured(self) -> bool:
        return True

    def complete(self, messages, max_tokens=1000, timeout=30) -> LLMResponse:
        self.call_count += 1
        self.timeouts.append(timeout)
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(error="no more responses")


_PAIRED_DIFF = """\
diff --git a/calculator.py b/calculator.py
index 1111111..2222222 100644
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,3 @@
 def add(a, b):
+    return a + b
     pass
diff --git a/tests/test_calculator.py b/tests/test_calculator.py
index 1111111..2222222 100644
--- a/tests/test_calculator.py
+++ b/tests/test_calculator.py
@@ -1,2 +1,3 @@
 def test_add():
+    assert add(1, 2) == 3
     pass
"""

_DEFECT_DIFF = """\
diff --git a/auth.py b/auth.py
index 1111111..2222222 100644
--- a/auth.py
+++ b/auth.py
@@ -1,2 +1,3 @@
 def login():
+    password = "hunter2-secret"
     return True
"""

_HARMLESS_DIFF = """\
diff --git a/notes.py b/notes.py
index 1111111..2222222 100644
--- a/notes.py
+++ b/notes.py
@@ -1,2 +1,3 @@
 def ready():
+    # Clarify the return value for readers.
     return True
"""


def test_demo_does_not_flag_source_when_its_test_is_in_the_diff():
    path = _write_diff(_PAIRED_DIFF)
    try:
        result = review_diff(
            type("DiffInput", (), {"type": "file", "path": path})(),
            _Config(),
            mode="demo",
        )
    finally:
        os.unlink(path)
    missing = [f for f in result.findings if f.category.value == "missing_test"]
    assert missing == []
    assert result.overall_risk == "low"


def test_demo_flags_hardcoded_secret_as_high_risk():
    path = _write_diff(_DEFECT_DIFF)
    try:
        result = review_diff(
            type("DiffInput", (), {"type": "file", "path": path})(),
            _Config(),
            mode="demo",
        )
    finally:
        os.unlink(path)
    risks = [f for f in result.findings if f.category.value == "risk"]
    assert risks
    assert risks[0].severity.value == "high"
    assert risks[0].is_speculative is True
    assert result.overall_risk == "high"


def test_demo_behavior_change_without_a_test_stays_a_hint():
    path = _write_diff(_PAIRED_DIFF.split("diff --git a/tests/")[0])
    try:
        result = review_diff(
            type("DiffInput", (), {"type": "file", "path": path})(),
            _Config(),
            mode="demo",
        )
    finally:
        os.unlink(path)
    missing = [f for f in result.findings if f.category.value == "missing_test"]
    assert len(missing) == 1
    assert missing[0].is_speculative is True
    assert result.overall_risk == "medium"


def test_demo_harmless_comment_is_low_risk_without_a_defect():
    path = _write_diff(_HARMLESS_DIFF)
    try:
        result = review_diff(
            type("DiffInput", (), {"type": "file", "path": path})(),
            _Config(),
            mode="demo",
        )
    finally:
        os.unlink(path)
    assert result.overall_risk == "low"
    assert [f for f in result.findings if f.category.value == "risk"] == []
    assert [f for f in result.findings if f.category.value == "bug"] == []


def test_user_message_is_clipped_to_context_budget():
    evidence = [
        {"file": f"f{i}.py", "excerpt": "x" * 500} for i in range(40)
    ]
    text = _build_user_message(
        {"changed_files": [f"f{i}.py" for i in range(40)]},
        {"added_lines": 1, "removed_lines": 0, "total_hunks": 1},
        [],
        [],
        evidence,
        max_chars=1000,
    )
    assert len(text) <= 1000 + len("\n... (truncated to context limit)")
    assert "truncated to context limit" in text


def test_llm_enforces_context_and_excerpt_budgets():
    path = _write_diff(_HARMLESS_DIFF)
    provider = _ScriptedProvider([LLMResponse(content=json.dumps(_VALID))])
    captured = {}

    def capture(messages, max_tokens=1000, timeout=30):
        captured["user"] = messages[-1].content
        return LLMResponse(content=json.dumps(_VALID))

    provider.complete = capture
    try:
        from diff_review_agent.diff_parser import parse_diff_file

        diff = parse_diff_file(path)
        _review_llm(
            diff,
            type("DiffInput", (), {"type": "file", "path": path})(),
            provider,
            _Config(max_context_tokens=120, excerpt_max_chars=12),
        )
    finally:
        os.unlink(path)
    assert len(captured["user"]) <= 120 * 4 + len("\n... (truncated to context limit)")


def test_validate_response_accepts_braces_in_json_strings():
    response = dict(_VALID)
    response["summary"] = "Literal { braces } are valid JSON string content."
    result, errors = __import__("diff_review_agent.agent", fromlist=["_validate_response"])._validate_response(
        json.dumps(response)
    )
    assert errors == []
    assert result is not None


def test_llm_retries_malformed_response_once_then_accepts():
    path = _write_diff(_HARMLESS_DIFF)
    provider = _ScriptedProvider(
        [
            LLMResponse(content="this is not json"),
            LLMResponse(content=json.dumps(_VALID)),
        ]
    )
    try:
        from diff_review_agent.diff_parser import parse_diff_file

        diff = parse_diff_file(path)
        result = _review_llm(
            diff,
            type("DiffInput", (), {"type": "file", "path": path})(),
            provider,
            _Config(max_retries=1, timeout_seconds=7),
        )
    finally:
        os.unlink(path)
    assert provider.call_count == 2
    assert provider.timeouts == [7, 7]
    assert result.review_metadata.model_provider_mode == "llm"
    assert result.overall_risk == "low"


def test_llm_malformed_twice_returns_error_without_invented_findings():
    path = _write_diff(_HARMLESS_DIFF)
    provider = _ScriptedProvider(
        [LLMResponse(content="nope"), LLMResponse(content="still nope")]
    )
    try:
        from diff_review_agent.diff_parser import parse_diff_file

        diff = parse_diff_file(path)
        result = _review_llm(
            diff,
            type("DiffInput", (), {"type": "file", "path": path})(),
            provider,
            _Config(max_retries=1),
        )
    finally:
        os.unlink(path)
    assert provider.call_count == 2
    assert result.review_metadata.model_provider_mode == "error"
    assert result.findings == []


def test_llm_transient_provider_error_retries_then_accepts():
    path = _write_diff(_HARMLESS_DIFF)
    provider = _ScriptedProvider(
        [LLMResponse(error="Request timed out after 7s."), LLMResponse(content=json.dumps(_VALID))]
    )
    try:
        from diff_review_agent.diff_parser import parse_diff_file

        diff = parse_diff_file(path)
        result = _review_llm(
            diff,
            type("DiffInput", (), {"type": "file", "path": path})(),
            provider,
            _Config(),
        )
    finally:
        os.unlink(path)
    assert provider.call_count == 2
    assert result.review_metadata.model_provider_mode == "llm"