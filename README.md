# FlexGCC AI Engineer Assessment: Diff Review Agent

A small, safe AI code-review agent that reads a Git diff and produces structured JSON feedback.

## What It Does

- **Accepted input**: A diff/patch file (primary) or a local Git revision range (optional).
- **Review categories**: Bugs, risks, missing tests, and style issues.
- **Output format**: JSON with a top-level object containing `summary`, `overall_risk`, `findings`, and `review_metadata`.
- **Each finding** includes: `category`, `severity`, `title`, `description`, `file`, `line_start`, `line_end`, `evidence`, `recommendation`, `confidence`, and `is_speculative`.
- **Two modes**: `--mode demo` (deterministic, no LLM) and `--mode llm` (uses a configured LLM provider).

## How It Was Built

- **Language**: Python 3.11+ (single `python` interpreter; `python3` is not available on Windows).
- **Framework**: Pydantic for schema validation; argparse for CLI.
- **Model/provider**: OpenAI-compatible provider adapter (isolated from the agent). Configurable via environment variables (`OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`). Model name is not hardcoded.
- **Orchestration**: A bounded workflow: receive validated diff summary and bounded changed-line evidence → plan review areas → call allowlisted read-only tools → observe results → synthesize findings → validate locally → retry at most once.
- **Tools called** (all read-only and allowlisted):
  - `summarize_diff` — changed files, change counts, hunk summaries.
  - `inspect_test_coverage_hints` — hints about likely test files near changed source files.
  - `detect_basic_patterns` — conservative checks for risky patterns in added lines.
  - `get_changed_line_evidence` — bounded excerpts and line references.

## What Went Wrong and How It Was Handled

The initial directory layout used a nested `src/diff_review_agent/src/diff_review_agent` structure, which broke imports. The fix was to flatten the package to `src/diff_review_agent/diff_review_agent/`. The diff parser initially returned empty results for valid diffs; this was fixed by extracting metadata from the diff content before computing summaries. The agent's `review_diff` function initially returned a result without checking for parse errors; this was fixed by wrapping the parse call in a try/except that returns an explicit error result.

## What I Would Do Next

- **PR integration**: Wire the agent into a real hosted pull-request workflow (not implemented here; this is a local diff review only).
- **Repository context**: Add a repo-aware mode that inspects existing tests and project conventions.
- **More test heuristics**: Expand `detect_basic_patterns` with language-aware checks for unsafe patterns.
- **Evaluation dataset**: Build a small benchmark of diffs with expected findings to measure precision/recall.
- **Audit logging**: Add structured logging for tool calls, retries, and provider failures.

## Setup

```bash
pip install -e ".[dev]"
```

## Environment Variables

- `OPENAI_API_KEY` — API key for the LLM provider (leave unset for demo mode).
- `OPENAI_MODEL` — Model identifier (default: `gpt-4o-mini`).
- `OPENAI_BASE_URL` — Base URL for OpenAI-compatible endpoints (optional).

## Demo Command

```bash
python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
```

## Test Command

```bash
pytest
```

## Sample Output

See `samples/expected_demo_output.json` for an example of the structured JSON output (demo mode).

## Known Limitations

- **Demo mode** is deterministic and does not use an LLM; findings are heuristic-based and may miss context-dependent issues.
- **LLM mode** is implemented but not live-verified in this environment (no API key available).
- **Local diff review only**: This is not a hosted pull-request integration.
- **Test-file heuristics** are hints, not proof that tests are missing.
- **Binary/unsupported files** are handled gracefully but not deeply analyzed.
- **No execution of diff content**: The agent never runs code or commands described by the diff.