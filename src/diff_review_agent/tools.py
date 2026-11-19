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
# Markdown and similar prose formats can document dangerous APIs without adding
# executable behavior. Universal hygiene patterns (secrets and TODO/FIXME) stay
# enabled for every file type; only behavior-dependent patterns are skipped.
_PROSE_FILE_SUFFIXES = (".md", ".mdx", ".rst", ".txt")
_EXECUTABLE_PATTERN_LABELS = {
    "dynamic-code-execution",
    "shell-true-subprocess",
    "possible-sql-injection",
    "ssl-verification-disabled",
    "security-check-suppressed",
    "possible-secret-logged",
}

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


def _normalize_repo_path(path: str) -> str:
    """Normalize slash style and only literal leading ``./`` path segments.

    ``str.lstrip('./')`` is intentionally not used: it treats ``.`` and ``/``
    as an unordered character set and corrupts legitimate names such as
    ``.github/workflows/check.py`` or traversal-shaped input such as
    ``../outside.py``.
    """
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _path_parts(path: str) -> Tuple[str, str]:
    normalized = _normalize_repo_path(path)
    if "/" not in normalized:
        return "", normalized
    parent, name = normalized.rsplit("/", 1)
    return parent + "/", name


def _python_test_names(stem: str) -> set[str]:
    return {f"test_{stem}.py", f"{stem}_test.py"}


def _js_test_names(stem: str, suffix: str) -> set[str]:
    exts = {suffix, ".ts", ".tsx", ".js", ".jsx"}
    names: set[str] = set()
    for ext in exts:
        names.add(f"{stem}.test{ext}")
        names.add(f"{stem}.spec{ext}")
    return names


def _expected_test_paths(source_path: str) -> set[str]:
    """Return conventional, repo-relative test paths for a changed source path."""
    parent, name = _path_parts(source_path)
    py = re.match(r"^(.+)\.py$", name)
    js = re.match(r"^(.+)\.(ts|tsx|js|jsx)$", name)
    if py:
        names = _python_test_names(py.group(1))
    elif js:
        names = _js_test_names(js.group(1), "." + js.group(2))
    else:
        return set()

    # Root test suites and tests next to a source module are conventional.
    # Constrain matching to these locations so unrelated paths with the same
    # basename do not suppress a source file's missing-test hint.
    directories = {"tests/", parent, f"{parent}tests/", f"{parent}__tests__/"}
    return {f"{directory}{test_name}" for directory in directories for test_name in names}


def _matching_test_in_change(source_path: str, changed_files: List[str]) -> Optional[str]:
    """Return a conventionally located changed test for ``source_path``.

    This is a naming hint, not proof of coverage. Paths are normalized before
    comparison, but the original diff spelling is returned for user-visible
    evidence.
    """
    expected_paths = _expected_test_paths(source_path)
    normalized_source = _normalize_repo_path(source_path)
    for other in changed_files:
        if not isinstance(other, str):
            continue
        normalized_other = _normalize_repo_path(other)
        if normalized_other != normalized_source and normalized_other in expected_paths:
            return other
    return None


def inspect_test_coverage_hints(changed_files: List[str]) -> List[Dict[str, Any]]:
    """
    Return hints about expected test files for changed source files.

    This is heuristic only — it does NOT read the filesystem, execute any
    code, or confirm that tests are absent.  When another file in this same
    change matches the conventional test name, the hint says so and sets
    ``matched_test_in_change``.  Report findings as hints only.
    """
    hints = []
    for f in changed_files:
        if not isinstance(f, str):
            continue
        _parent, name = _path_parts(f)
        base_dir = _parent

        if name.endswith(".py"):
            stem = name[:-3]  # remove .py
            if stem.startswith("test_") or stem.endswith("_test"):
                hints.append({
                    "changed_file": f,
                    "is_test_file": True,
                    "matched_test_in_change": None,
                    "test_hint": "This file appears to be a test file.",
                })
            else:
                expected = [
                    f"tests/test_{stem}.py",
                    f"tests/{stem}_test.py",
                    f"{base_dir}test_{name}",
                    f"{base_dir}{stem}_test.py",
                ]
                matched = _matching_test_in_change(f, changed_files)
                if matched:
                    hint = (
                        f"A conventionally named test file is also changed: {matched}. "
                        "This is a naming match inside the diff only; coverage of the "
                        "new behavior is not confirmed."
                    )
                else:
                    hint = (
                        f"Look for a test file such as: {', '.join(expected)}. "
                        "This is a naming-convention hint only; test absence is not confirmed."
                    )
                hints.append({
                    "changed_file": f,
                    "is_test_file": False,
                    "matched_test_in_change": matched,
                    "test_hint": hint,
                    "expected_test_paths": expected,
                })
        elif name.endswith((".ts", ".tsx", ".js", ".jsx")):
            stem = re.sub(r"\.(ts|tsx|js|jsx)$", "", name)
            if ".test." in name or ".spec." in name or "/__tests__/" in f"/{_normalize_repo_path(f)}":
                hints.append({
                    "changed_file": f,
                    "is_test_file": True,
                    "matched_test_in_change": None,
                    "test_hint": "This file appears to be a test file.",
                })
            else:
                matched = _matching_test_in_change(f, changed_files)
                if matched:
                    hint = (
                        f"A conventionally named test file is also changed: {matched}. "
                        "Naming match inside the diff only; coverage is not confirmed."
                    )
                else:
                    hint = (
                        f"Look for {stem}.test.ts, {stem}.spec.ts, or __tests__/{name}. "
                        "Naming-convention hint only."
                    )
                hints.append({
                    "changed_file": f,
                    "is_test_file": False,
                    "matched_test_in_change": matched,
                    "test_hint": hint,
                })
        # Non-source files (markdown, yaml, json, etc.) get no test hint
    return hints


def _is_comment_or_docstring_line(line: str, in_docstring: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Classify simple Python/JS prose lines without parsing untrusted code.

    The detector deliberately skips comments and triple-quoted docstring
    content. These lines describe code but cannot execute it, so reporting
    patterns such as ``eval(`` in them as active behavior is a false positive.
    """
    stripped = line.strip()
    if in_docstring:
        if in_docstring in stripped:
            return True, None
        return True, in_docstring
    if not stripped or stripped.startswith(("#", "//", "/*", "*", "*/")):
        return True, None
    for marker in ('"""', "'''"):
        if stripped.startswith(marker):
            return True, None if stripped.count(marker) >= 2 else marker
    return False, None


def detect_basic_patterns(diff: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Conservative pattern detection over executable added lines only.

    Returns a list of findings. Every finding carries a caveat about
    false-positive risk so callers know the result is not authoritative.
    """
    findings: List[Dict[str, Any]] = []
    file_added_lines: Dict[str, List[Tuple[int, str]]] = diff.get("file_added_lines", {})

    for filepath, line_entries in file_added_lines.items():
        is_prose_file = _normalize_repo_path(filepath).lower().endswith(_PROSE_FILE_SUFFIXES)
        docstring_marker: Optional[str] = None
        for lineno, line_text in line_entries:
            is_prose, docstring_marker = _is_comment_or_docstring_line(
                line_text, docstring_marker
            )
            for pattern, label, severity, caveat in _RISKY_PATTERNS:
                # TODO/FIXME markers are deliberately comments in most codebases,
                # unlike executable-risk patterns such as eval() or shell=True.
                if is_prose and label != "todo-or-fixme":
                    continue
                # Markdown prose can document ``eval()`` but cannot execute it.
                # Keep secrets/TODO detection active in prose files because those
                # findings are about content, rather than code execution.
                if is_prose_file and label in _EXECUTABLE_PATTERN_LABELS:
                    continue
                if pattern.search(line_text):
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
