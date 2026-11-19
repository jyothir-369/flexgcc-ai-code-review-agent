"""Unit tests for the review agent."""

import pytest
import tempfile
import os
from pathlib import Path

from diff_review_agent.agent import review_diff
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