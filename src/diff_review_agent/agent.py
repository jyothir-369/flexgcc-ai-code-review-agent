"""Agent orchestration: bounded LLM-driven review workflow.

Agent orchestration for diff review.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from diff_review_agent.schemas import ReviewResult, Finding, ReviewMetadata, Severity, Category
from diff_review_agent.diff_parser import DiffParseError, parse_diff_file
from diff_review_agent.tools import summarize_diff, inspect_test_coverage_hints, detect_basic_patterns, get_changed_line_evidence


def review_diff(diff_input: Any, config: Any, mode: str = "demo") -> ReviewResult:
    """Run the full review workflow. Bounded and deterministic."""
    # 1. Receive validated diff summary and bounded changed-line evidence
    try:
        diff = parse_diff_file(diff_input.path)
    except DiffParseError as e:
        return ReviewResult(
            summary=f"Failed to parse diff: {e.message}",
            overall_risk="unknown",
            findings=[],
            review_metadata=ReviewMetadata(
                input_type="file",
                reviewed_file_count=0,
                model_provider_mode="error",
                limitations=[f"Parse error: {e.message}"],
            ),
        )

    # 2. Plan review areas
    # 3. Call tools from allowlist
    summary = summarize_diff(diff)
    hints = inspect_test_coverage_hints(diff.get("changed_files", []))
    patterns = detect_basic_patterns(diff)
    evidence = get_changed_line_evidence(diff)

    # 4. Observe tool results and 5. Synthesize findings
    findings: List[Finding] = []

    if mode == "demo":
        # Deterministic demo findings (clearly labeled)
        changed_files = diff.get("changed_files", [])
        first_file = changed_files[0] if changed_files else None
        findings.append(Finding(
            category=Category.missing_test,
            severity=Severity.medium,
            title="No tests changed in this diff",
            description="This diff modifies source files but does not include test updates.",
            file=first_file,
            evidence="Diff contains no test file changes",
            recommendation="Add or update tests for changed behavior",
            confidence=0.8,
            is_speculative=True,
        ))

    # 6. Validate locally (pydantic handles schema)
    # 7. Retry once at most if malformed (not needed for demo mode)

    changed_files = diff.get("changed_files", [])
    return ReviewResult(
        summary=f"Reviewed {len(changed_files)} files with {summary['added_lines']} additions and {summary['removed_lines']} deletions",
        overall_risk="medium" if findings else "low",
        findings=findings,
        review_metadata=ReviewMetadata(
            input_type="file",
            reviewed_file_count=len(changed_files),
            model_provider_mode="demo" if mode == "demo" else "llm",
            limitations=["Demo mode: deterministic rules only, no LLM reasoning"],
        ),
    )
