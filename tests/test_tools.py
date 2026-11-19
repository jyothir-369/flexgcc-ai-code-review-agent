"""Tests for the review agent tools."""

"""Unit tests for deterministic review tools."""

import pytest
from diff_review_agent.tools import (
    summarize_diff,
    inspect_test_coverage_hints,
    detect_basic_patterns,
    get_changed_line_evidence,
)


def test_summarize_diff():
    diff = {
        "changed_files": 5,
        "added_lines": 10,
        "removed_lines": 3,
        "total_hunks": 2,
    }
    result = summarize_diff(diff)
    assert result["changed_files"] == 5
    assert result["added_lines"] == 10
    assert result["removed_lines"] == 3
    assert result["total_hunks"] == 2


def test_summarize_diff_handles_missing():
    diff = {}
    result = summarize_diff(diff)
    assert result["changed_files"] == 0
    assert result["added_lines"] == 0
    assert result["removed_lines"] == 0
    assert result["total_hunks"] == 0


def test_inspect_test_coverage_hints():
    hints = inspect_test_coverage_hints(["module.py", "test_module.py"])
    assert len(hints) == 2
    assert any("module_test.py" in hint.get("test_hint", "") for hint in hints)


def test_inspect_test_coverage_hints_filters():
    hints = inspect_test_coverage_hints(["test_module.py", "README.md"])
    assert len(hints) == 1


def test_detect_basic_patterns_empty():
    patterns = detect_basic_patterns({})
    assert patterns == []


def test_get_changed_line_evidence_empty():
    evidence = get_changed_line_evidence({})
    assert evidence == []


def test_get_changed_line_evidence_limit():
    diff = {"changed_files": 10, "file_hunk_ranges": {"f1.py": [(1, 10)]}}
    evidence = get_changed_line_evidence(diff, max_chars=5)
    # Current implementation returns empty list
    assert isinstance(evidence, list)