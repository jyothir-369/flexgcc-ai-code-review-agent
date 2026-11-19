"""Deterministic, read-only review tools for the diff reviewer.

Deterministic tools for diff analysis.
"""

from __future__ import annotations
from typing import Any, Dict, List


def summarize_diff(diff: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize changed files, counts, and hunks."""
    return {
        "changed_files": diff.get("changed_files", 0),
        "added_lines": diff.get("added_lines", 0),
        "removed_lines": diff.get("removed_lines", 0),
        "total_hunks": diff.get("total_hunks", 0),
    }


def inspect_test_coverage_hints(changed_files: List[str]) -> List[Dict[str, Any]]:
    """Return hints about likely test files near changed source files."""
    hints = []
    for f in changed_files:
        if f.endswith('.py'):
            hints.append({
                "changed_file": f,
                "test_hint": f"Ruff-like hint: look for {f.rsplit('.', 1)[0]}_test.py or {f.rsplit('/', 1)[-1].rsplit('.', 1)[0]}_test.py"
            })
    return hints


def detect_basic_patterns(diff: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Conservative pattern checks over added lines (secrets, disabled validation)."""
    findings = []
    # Placeholder: real pattern detection would scan added lines
    return findings


def get_changed_line_evidence(diff: Dict[str, Any], max_chars: int = 500) -> List[Dict[str, Any]]:
    """Return bounded excerpts of changed lines."""
    return []

TOOLS = {
    "summarize_diff": summarize_diff,
    "inspect_test_coverage_hints": inspect_test_coverage_hints,
    "detect_basic_patterns": detect_basic_patterns,
    "get_changed_line_evidence": get_changed_line_evidence,
}
