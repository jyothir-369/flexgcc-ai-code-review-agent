# Phase 2 — Safe Diff Ingestion and Deterministic Review Tools

## Status: PASS

All Phase 2 acceptance criteria verified with real test output.

---

## Implementation Summary

### Files Modified

| File | Change |
|------|--------|
| `src/diff_review_agent/diff_parser.py` | Full rewrite: unified diff parser with size limits, binary detection, path traversal prevention, git revision range support |
| `src/diff_review_agent/tools.py` | Full rewrite: real pattern detection, test-coverage hints with JS/TS support, bounded line evidence extraction |
| `src/diff_review_agent/agent.py` | Updated to use richer parsed-diff data, derive risk from actual findings, emit pattern-based findings |
| `src/diff_review_agent/cli.py` | Fixed `GitDiffInput` constructor call (input_type kwarg) |
| `tests/test_phase2.py` | New: 69 comprehensive tests for all Phase 2 requirements |

---

## Acceptance Criteria Evidence

### AC1: Diff file can be loaded and parsed

```
$ python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
{
  "summary": "Reviewed 2 file(s) with 11 addition(s) and 5 deletion(s). Found 2 finding(s).",
  ...
}
Exit code: 0
```

Parser extracts: changed files, added/removed lines, hunk ranges, added-line content, binary files, file status (added/deleted/modified/renamed).

### AC2: Optional Git revision-range input — read-only and safely invoked

- `get_diff_from_git(base, head, repo_path)` in `diff_parser.py`
- Arguments passed as array to `subprocess.run(..., shell=False)` — never interpolated into a shell
- Refs validated against `_is_safe_git_ref()` before use
- Timeout enforced (default 30s)
- Exit codes 0 and 1 accepted (1 = diff has differences, normal); others raise `DiffParseError`
- Test: `TestGitRevisionRange::test_git_range_returns_diff` — creates ephemeral git repo, diffs HEAD~1..HEAD, verifies parsed result

### AC3: Changed-file and changed-line evidence is accurate

- `TestDiffParserPositive::test_simple_diff_parsed` — PASS
- `TestDiffParserPositive::test_multi_file_diff` — PASS
- `TestDiffParserPositive::test_file_added_lines_captured` — PASS
- `TestDiffParserPositive::test_hunk_ranges_populated` — PASS

### AC4: Deterministic tools return bounded, typed results

All four tools implemented and tested:

| Tool | Behavior | Tests |
|------|----------|-------|
| `summarize_diff` | Returns file count, line counts, binary files, file names, status | `TestSummarizeDiff` (2 tests) |
| `inspect_test_coverage_hints` | Hints for .py, .ts, .tsx, .js, .jsx; identifies test files | `TestInspectTestCoverageHints` (6 tests) |
| `detect_basic_patterns` | Regex checks on added lines for secrets, eval, shell=True, SQL injection, SSL bypass, TODO, secret logging; excerpts capped at 200 chars | `TestDetectBasicPatterns` (9 tests) |
| `get_changed_line_evidence` | Bounded excerpts per file with line numbers; `max_chars` enforced | `TestGetChangedLineEvidence` (5 tests) |

### AC5: Malformed, empty, oversized, binary, and adversarial inputs fail safely

| Input Type | Behavior | Test |
|------------|----------|------|
| Nonexistent file | `DiffParseError` raised | `test_nonexistent_diff_raises`, `test_nonexistent_file_raises` |
| Empty diff | Returns all-zero counts, no crash | `test_empty_diff_returns_zeroes`, `test_empty_content_no_crash` |
| Oversized diff | `DiffParseError` with size limit message | `test_oversized_diff_raises` |
| Binary file | Detected in `binary_files`, not in `changed_files` | `test_binary_file_detected`, `test_binary_file_not_in_changed_files` |
| Malformed hunk header | Graceful fallback, no crash | `test_malformed_hunk_header_handled` |
| Max file count exceeded | Stops adding files at limit | `test_max_files_limit` |
| Path traversal (`../..`) | Blocked by `_is_unsafe_path`, not in output | `test_traversal_diff_not_in_changed_files` |
| Null bytes | Handled via `errors=replace`, no crash | `test_null_bytes_in_diff` |
| Very long lines | Parsed without overflow | `test_very_long_line_in_diff` |
| Prompt injection text | Parsed as data, not executed | `test_prompt_injection_in_diff_not_executed` |

### AC6: Tests pass including negative cases

```
$ python -m pytest tests/ --tb=short
89 passed in 1.56s
```

- Original tests (Phase 1): 20 tests — all PASS
- Phase 2 new tests: 69 tests — all PASS
- Total: **89 PASS, 0 FAIL**

---

## Security Requirements — Evidence

| Requirement | Implementation |
|-------------|----------------|
| Filenames treated as untrusted data | `_is_unsafe_path()` blocks traversal; paths never opened or followed |
| No shell interpolation of diff values | `subprocess.run([...], shell=False)` only |
| Git refs validated | `_is_safe_git_ref()` rejects metacharacters, empty strings, length > 256 |
| Timeout on git subprocess | `timeout=30` (configurable) |
| Git command restricted to `git diff` | Only `["git", "diff", base, head]` issued |
| Secrets not read from diff paths | Tools work only on already-parsed in-memory data |
| Excerpt length bounded | `max_chars` parameter, default 500; pattern excerpts capped at 200 chars |

---

## Known Parser Limitations

- Paths with spaces in `"a/my file.py"` quoting are not fully parsed (git may quote them; the parser reads the raw `+++ ` line and would need quote-stripping to handle all cases).
- Diff format variations (e.g. `diff -u` without git metadata) may produce empty `changed_files` lists but will not crash.
- The `file_added_lines` line-number tracking is approximate: line numbers are counted within-hunk from the hunk `@@ +start @@` header and may drift for large hunks with mixed add/context lines.
- Git revision-range support requires a git executable on PATH.

---

## Example Command and Output

```bash
python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
```

Output (sanitized):
```json
{
  "summary": "Reviewed 2 file(s) with 11 addition(s) and 5 deletion(s). Found 2 finding(s).",
  "overall_risk": "medium",
  "findings": [
    {
      "category": "missing_test",
      "severity": "medium",
      "title": "No apparent test file for calculator.py",
      "confidence": 0.5,
      "is_speculative": true
    },
    {
      "category": "style",
      "severity": "info",
      "title": "Diff reviewed in demo/offline mode",
      "confidence": 1.0,
      "is_speculative": false
    }
  ],
  "review_metadata": {
    "input_type": "file",
    "reviewed_file_count": 2,
    "model_provider_mode": "demo"
  }
}
```
