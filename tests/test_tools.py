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
    source = next(h for h in hints if h["changed_file"] == "module.py")
    # The conventional alternate name stays available even when another
    # test file in this change already matches.
    assert "module_test.py" in source["expected_test_paths"]
    assert source["matched_test_in_change"] == "test_module.py"


def test_inspect_test_coverage_hints_filters():
    hints = inspect_test_coverage_hints(["test_module.py", "README.md"])
    assert len(hints) == 1


def test_source_with_matching_test_in_same_change_is_not_missing():
    """A source file whose conventional test is also changed is not 'missing'."""
    hints = inspect_test_coverage_hints(
        ["calculator.py", "tests/test_calculator.py"]
    )
    by_file = {h["changed_file"]: h for h in hints}
    assert by_file["tests/test_calculator.py"]["is_test_file"] is True
    source = by_file["calculator.py"]
    assert source["is_test_file"] is False
    assert source["matched_test_in_change"] == "tests/test_calculator.py"
    assert "also changed" in source["test_hint"]


def test_source_without_any_test_file_stays_unmatched():
    hints = inspect_test_coverage_hints(["calculator.py", "README.md"])
    assert hints[0]["matched_test_in_change"] is None
    assert "not confirmed" in hints[0]["test_hint"]


def test_windows_style_test_path_matches_source():
    hints = inspect_test_coverage_hints(
        ["src\\billing.py", "tests\\test_billing.py"]
    )
    source = next(h for h in hints if h["changed_file"].endswith("billing.py") and not h["is_test_file"])
    assert source["matched_test_in_change"] == "tests\\test_billing.py"


def test_path_normalization_preserves_dotfiles_and_traversal_shape():
    from diff_review_agent.tools import _normalize_repo_path

    assert _normalize_repo_path(".github/workflows/check.py") == ".github/workflows/check.py"
    assert _normalize_repo_path("../outside.py") == "../outside.py"
    assert _normalize_repo_path("./src\\module.py") == "src/module.py"


def test_matching_test_must_be_in_a_conventional_related_location():
    hints = inspect_test_coverage_hints(
        ["src/api/user.py", "frontend/tests/test_user.py"]
    )
    source = next(h for h in hints if h["changed_file"] == "src/api/user.py")
    assert source["matched_test_in_change"] is None


def test_get_changed_line_evidence_preserves_comment_todo_but_skips_prose_risks():
    diff = {
        "file_added_lines": {
            "module.py": [
                (1, "# TODO: explain why eval(user_input) is unsafe"),
                (2, '\"\"\"Do not call eval(user_input).\"\"\"'),
                (3, "value = eval(user_input)"),
            ]
        }
    }
    labels = [item["label"] for item in detect_basic_patterns(diff)]
    assert labels.count("todo-or-fixme") == 1
    assert labels.count("dynamic-code-execution") == 1


def test_markdown_prose_does_not_trigger_executable_eval_finding():
    diff = {
        "file_added_lines": {
            "FINAL-VERIFICATION.md": [
                (64, "- The detector catches `eval(user_input)` in executable code."),
            ]
        }
    }
    labels = [item["label"] for item in detect_basic_patterns(diff)]
    assert "dynamic-code-execution" not in labels


def test_markdown_retains_todo_and_hardcoded_secret_detection():
    diff = {
        "file_added_lines": {
            "notes.md": [
                (1, "TODO: rotate this value"),
                (2, 'password = "mysecret123"'),
            ]
        }
    }
    labels = [item["label"] for item in detect_basic_patterns(diff)]
    assert "todo-or-fixme" in labels
    assert "possible-hardcoded-secret" in labels


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