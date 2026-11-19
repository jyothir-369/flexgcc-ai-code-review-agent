"""Deterministic, read-only review tools for the diff reviewer.

All tools are pure functions; they never execute shell commands, read arbitrary
files, or follow paths found in the diff.  Treat all diff text as untrusted data.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Risky pattern registry
# ---------------------------------------------------------------------------

# Each entry: (regex_pattern, label, severity, caveat)
# Patterns are applied only to ADDED lines (+) from the diff.
_RISKY_PATTERNS: List[Tuple[re.Pattern, str, str, str]] = [
    (
        re.compile(
            r'(?i)(password|passwd|secret|token|api[_\-]?key|auth[_\-]?token)\s*=\s*["\'](?!.*<.*>)[^"\']{4,}',
        ),
        "possible-hardcoded-secret",
        "high",
        "False-positive rate is moderate; verify the value is not a placeholder.",
    ),
    (
        re.compile(r'(?i)(TODO|FIXME|HACK|XXX)\b'),
        "todo-or-fixme",
        "low",
        "Markers may indicate incomplete or risky logic.",
    ),
    (
        re.compile(r'(?i)(eval|exec)\s*\('),
        "dynamic-code-execution",
        "high",
        "Dynamic code execution may allow injection if input is not validated.",
    ),
    (
        re.compile(r'(?i)shell\s*=\s*True'),
        "shell-true-subprocess",
        "high",
        "shell=True in subprocess calls can allow command injection.",
    ),
    (
        re.compile(r'(?i)(sql|query)\s*[+%]=?\s*["\']|f["\'].*SELECT|f["\'].*INSERT|f["\'].*UPDATE|f["\'].*DELETE'),
        "possible-sql-injection",
        "high",
        "String interpolation in SQL statements may allow SQL injection.",
    ),
    (
        re.compile(r'verify\s*=\s*False'),
        "ssl-verification-disabled",
        "high",
        "Disabling SSL verification removes certificate validation.",
    ),
    (
        re.compile(r'(?i)#\s*nosec|#\s*noqa.*S\d{3}|#\s*type:\s*ignore'),
        "security-check-suppressed",
        "medium",
        "Security or type-check suppressions may hide real issues.",
    ),
    (
        re.compile(
            r'(?i)(print|log(ger)?\.?(debug|info|warning|error|critical))\s*\(.*\b(password|secret|token|key)\b'
        ),
        "possible-secret-logged",
        "high",
        "Sensitive values may be written to logs.",
    ),
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def summarize_diff(diff: Dict[str, Any]) -> Dict[str, Any]:
    """Return counts and file names from the parsed diff."""
    changed_files = diff.get("changed_files", [])
    file_count = len(changed_files) if isinstance(changed_files, list) else diff.get("changed_files", 0)
    binary_files = diff.get("binary_files", [])
    file_status = diff.get("file_status", {})
    return {
        "changed_files": file_count,
        "added_lines": diff.get("added_lines", 0),
        "removed_lines": diff.get("removed_lines", 0),
        "total_hunks": diff.get("total_hunks", 0),
        "binary_files": binary_files,
        "file_names": changed_files if isinstance(changed_files, list) else [],
        "file_status": file_status,
    }


def inspect_test_coverage_hints(changed_files: List[str]) -> List[Dict[str, Any]]:
    """
    Return hints about expected test files for changed source files.

    This is heuristic only — it does NOT read the filesystem, execute any
    code, or confirm that tests are absent.  Report findings as hints only.
    """
    hints = []
    for f in changed_files:
        if not isinstance(f, str):
            continue
        name = f.rsplit("/", 1)[-1] if "/" in f else f
        base_dir = f.rsplit("/", 1)[0] + "/" if "/" in f else ""

        if name.endswith(".py"):
            stem = name[:-3]  # remove .py
            if stem.startswith("test_") or stem.endswith("_test"):
                # This file itself looks like a test
                hints.append({
                    "changed_file": f,
                    "is_test_file": True,
                    "test_hint": "This file appears to be a test file.",
                })
            else:
                expected = [
                    f"tests/test_{stem}.py",
                    f"tests/{stem}_test.py",
                    f"{base_dir}test_{name}",
                    f"{base_dir}{stem}_test.py",
                ]
                hints.append({
                    "changed_file": f,
                    "is_test_file": False,
                    "test_hint": (
                        f"Look for a test file such as: {', '.join(expected)}. "
                        "This is a naming-convention hint only; test absence is not confirmed."
                    ),
                    "expected_test_paths": expected,
                })
        elif name.endswith((".ts", ".tsx", ".js", ".jsx")):
            stem = re.sub(r"\.(ts|tsx|js|jsx)$", "", name)
            if stem.startswith("__tests__") or ".test." in name or ".spec." in name:
                hints.append({"changed_file": f, "is_test_file": True,
                               "test_hint": "This file appears to be a test file."})
            else:
                hints.append({
                    "changed_file": f,
                    "is_test_file": False,
                    "test_hint": (
                        f"Look for {stem}.test.ts, {stem}.spec.ts, or __tests__/{name}. "
                        "Naming-convention hint only."
                    ),
                })
        # Non-source files (markdown, yaml, json, etc.) get no test hint
    return hints


def detect_basic_patterns(diff: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Conservative pattern detection over added lines only.

    Returns a list of findings.  Every finding carries a caveat about
    false-positive risk so callers know the result is not authoritative.
    """
    findings: List[Dict[str, Any]] = []
    file_added_lines: Dict[str, List[Tuple[int, str]]] = diff.get("file_added_lines", {})

    for filepath, line_entries in file_added_lines.items():
        for lineno, line_text in line_entries:
            for pattern, label, severity, caveat in _RISKY_PATTERNS:
                m = pattern.search(line_text)
                if m:
                    # Truncate the excerpt so we never emit oversized output
                    excerpt = line_text.strip()[:200]
                    findings.append({
                        "file": filepath,
                        "line": lineno,
                        "label": label,
                        "severity": severity,
                        "excerpt": excerpt,
                        "caveat": caveat,
                    })
    return findings


def get_changed_line_evidence(
    diff: Dict[str, Any],
    max_chars: int = 500,
    max_lines_per_file: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return bounded excerpts with line references from the parsed diff.

    Never reads files on disk; works only from the already-parsed diff data.
    Output is truncated to max_chars total per file excerpt to prevent
    oversized context injection.
    """
    results: List[Dict[str, Any]] = []
    file_added_lines: Dict[str, List[Tuple[int, str]]] = diff.get("file_added_lines", {})
    file_hunk_ranges: Dict[str, List[Tuple[int, int]]] = diff.get("file_hunk_ranges", {})
    raw_changed = diff.get("changed_files", [])
    # Support both list-of-filenames (parsed format) and legacy int count
    changed_files: List[str] = raw_changed if isinstance(raw_changed, list) else list(file_hunk_ranges.keys())

    # Produce evidence only for files we actually know about
    for filepath in changed_files:
        lines = file_added_lines.get(filepath, [])
        ranges = file_hunk_ranges.get(filepath, [])

        # Build a readable excerpt, capped at max_chars
        excerpt_parts: List[str] = []
        char_count = 0
        for lineno, text in lines[:max_lines_per_file]:
            entry = f"  +{lineno}: {text.rstrip()}"
            if char_count + len(entry) > max_chars:
                excerpt_parts.append("  ... (truncated)")
                break
            excerpt_parts.append(entry)
            char_count += len(entry)

        results.append({
            "file": filepath,
            "hunk_ranges": ranges,
            "added_line_count": len(lines),
            "excerpt": "\n".join(excerpt_parts) if excerpt_parts else "(no added lines)",
        })

    return results


# ---------------------------------------------------------------------------
# Tool registry (allowlist)
# ---------------------------------------------------------------------------

TOOLS: Dict[str, Any] = {
    "summarize_diff": summarize_diff,
    "inspect_test_coverage_hints": inspect_test_coverage_hints,
    "detect_basic_patterns": detect_basic_patterns,
    "get_changed_line_evidence": get_changed_line_evidence,
}
