"""Agent orchestration: bounded LLM-driven review workflow.

Agent orchestration for diff review.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from diff_review_agent.schemas import ReviewResult, Finding, ReviewMetadata, Severity, Category
from diff_review_agent.diff_parser import DiffParseError, parse_diff_file
from diff_review_agent.tools import (
    summarize_diff,
    inspect_test_coverage_hints,
    detect_basic_patterns,
    get_changed_line_evidence,
)


def _severity_from_str(s: str) -> Severity:
    return {
        "critical": Severity.critical,
        "high": Severity.high,
        "medium": Severity.medium,
        "low": Severity.low,
        "info": Severity.info,
    }.get(s, Severity.medium)


def review_diff(diff_input: Any, config: Any, mode: str = "demo") -> ReviewResult:
    """Run the full review workflow. Bounded and deterministic."""
    # 1. Parse the diff
    try:
        max_bytes = config.get("diff_max_bytes") if hasattr(config, "get") else 1_000_000
        max_files = config.get("diff_max_files") if hasattr(config, "get") else 50
        diff = parse_diff_file(diff_input.path, max_bytes=max_bytes, max_files=max_files)
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

    # 2. Run deterministic tools
    summary = summarize_diff(diff)
    changed_files: List[str] = diff.get("changed_files", [])
    hints = inspect_test_coverage_hints(changed_files)
    patterns = detect_basic_patterns(diff)
    evidence = get_changed_line_evidence(diff)

    # 3. Synthesize findings from tool results
    findings: List[Finding] = []

    # Pattern-based findings
    for p in patterns:
        findings.append(Finding(
            category=Category.risk,
            severity=_severity_from_str(p.get("severity", "medium")),
            title=f"Possible risky pattern: {p.get('label', 'unknown')}",
            description=(
                f"A potentially risky pattern was detected in added lines. "
                f"Caveat: {p.get('caveat', 'Manual review required.')}"
            ),
            file=p.get("file"),
            line_start=p.get("line"),
            line_end=p.get("line"),
            evidence=f"Added line excerpt: {p.get('excerpt', '(unavailable)')}",
            recommendation=(
                "Review the flagged line carefully. If the value is a placeholder "
                "or legitimately safe, this finding can be dismissed."
            ),
            confidence=0.6,
            is_speculative=True,
        ))

    # Test-coverage hint findings
    source_files_without_test = [
        h for h in hints
        if not h.get("is_test_file", True) and h.get("changed_file")
    ]
    if source_files_without_test and mode == "demo":
        for h in source_files_without_test[:3]:  # cap at 3 to avoid noise
            findings.append(Finding(
                category=Category.missing_test,
                severity=Severity.medium,
                title=f"No apparent test file for {h['changed_file']}",
                description=(
                    "A changed source file has no obvious corresponding test file "
                    "based on naming conventions. This is a heuristic hint only — "
                    "tests may exist under a different name or structure."
                ),
                file=h.get("changed_file"),
                evidence=h.get("test_hint", "Naming-convention hint."),
                recommendation=(
                    "Check whether tests exist and add or update them if the "
                    "changed behavior is not already covered."
                ),
                confidence=0.5,
                is_speculative=True,
            ))

    # In demo mode add a generic style observation if no patterns found
    if mode == "demo" and not patterns and changed_files:
        first_file = changed_files[0]
        findings.append(Finding(
            category=Category.style,
            severity=Severity.info,
            title="Diff reviewed in demo/offline mode",
            description=(
                "This review was produced by deterministic rules only. "
                "No LLM reasoning was applied. Results may miss subtle issues "
                "that require semantic understanding."
            ),
            file=first_file,
            evidence="Demo mode active — no API key configured.",
            recommendation="Re-run with --mode llm and a valid API key for AI-assisted review.",
            confidence=1.0,
            is_speculative=False,
        ))

    # 4. Derive overall risk
    severities = [f.severity for f in findings]
    if Severity.critical in severities or Severity.high in severities:
        overall_risk = "high"
    elif Severity.medium in severities:
        overall_risk = "medium"
    elif findings:
        overall_risk = "low"
    else:
        overall_risk = "low"

    limitations = ["Demo mode: deterministic rules only, no LLM reasoning"] if mode == "demo" else []
    if diff.get("binary_files"):
        limitations.append(f"Binary files skipped: {', '.join(diff['binary_files'])}")

    return ReviewResult(
        summary=(
            f"Reviewed {len(changed_files)} file(s) with "
            f"{summary['added_lines']} addition(s) and {summary['removed_lines']} deletion(s). "
            f"Found {len(findings)} finding(s)."
        ),
        overall_risk=overall_risk,
        findings=findings,
        review_metadata=ReviewMetadata(
            input_type=getattr(diff_input, "type", "file"),
            reviewed_file_count=len(changed_files),
            model_provider_mode="demo" if mode == "demo" else "llm",
            limitations=limitations,
        ),
    )
