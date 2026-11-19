# FlexGCC AI Engineer Assessment: Diff Review Agent

A small, safe AI code-review agent that reads a Git diff and produces structured JSON feedback.

## What It Does

- **Accepted input**: A diff/patch file (primary) or a local Git revision range (`--base` and `--head`).
- **Review categories**: Bugs, risks, missing tests, and style issues.
- **Output format**: JSON with a top-level object containing `summary`, `overall_risk`, `findings`, and `review_metadata`.
- **Each finding** includes: `category`, `severity`, `title`, `description`, `file`, `line_start`, `line_end`, `evidence`, `recommendation`, `confidence`, and `is_speculative`.
- **Two modes**: `--mode demo` (deterministic, no LLM) and `--mode llm` (uses a configured LLM provider).

## How It Was Built

- **Language**: Python 3.11+ (single `python` interpreter; `python3` is not available on Windows).
- **Framework**: Pydantic for schema validation; argparse for CLI.
- **Model/provider**: Provider adapter isolated from the agent. `LLM_PROVIDER=openai` (default) uses an OpenAI-compatible chat API. `LLM_PROVIDER=gemini` uses Google's official Gemini `generateContent` API (`GEMINI_API_KEY` as `x-goog-api-key`). Model names are not hardcoded. Selecting Gemini never falls back to demo output.
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

- `LLM_PROVIDER` — `openai` (default) or `gemini`.
- `OPENAI_API_KEY` — OpenAI key. Unset → demo fallback when OpenAI is selected.
- `OPENAI_MODEL` — OpenAI model (default: `gpt-4o-mini`).
- `OPENAI_BASE_URL` — OpenAI-compatible base URL (optional).
- `GEMINI_API_KEY` — required for `LLM_PROVIDER=gemini`. Missing key is an error, not a demo run.
- `GEMINI_MODEL` — Gemini model (default: `gemini-2.5-flash`).
- `GEMINI_BASE_URL` — optional; default `https://generativelanguage.googleapis.com/v1beta`.

## Commands

Review a diff file in deterministic demo mode:

```bash
python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
```

Review a local Git revision range instead of a patch file:

```bash
python -m diff_review_agent --base HEAD~1 --head HEAD --mode demo --format text
```

Use either `--diff` or both `--base` and `--head`. `--format json` is the default;
`--format text` prints a concise human-readable summary. Provider or parse errors
return structured output and a non-zero process exit code.

## Test Command

```bash
pytest
```

## Sample Output

See `samples/expected_demo_output.json` for an example of the structured JSON output (demo mode).

## Known Limitations

- **Demo mode** is deterministic and does not use an LLM; findings are heuristic-based and may miss context-dependent issues.
- **LLM mode** is implemented and covered by mocked tests. A live Gemini or OpenAI call has not been made in this environment (no API key). Demo output is never presented as a Gemini review.
- **Local diff review only**: This is not a hosted pull-request integration.
- **Test-file heuristics** are hints, not proof that tests are missing.
- **Binary/unsupported files** are handled gracefully but not deeply analyzed.
- **No execution of diff content**: The agent never runs code or commands described by the diff.