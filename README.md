# FlexGCC AI Engineer Assessment: Diff Review Agent

A Python-based AI code-review agent that analyzes Git diffs and returns structured feedback about potential bugs, risks, missing tests, and code-quality issues.

## What It Does

- Accepts a Git diff/patch file or a local Git revision range.
- Reviews changes for potential bugs, risks, missing tests, and style issues.
- Produces structured JSON or human-readable text output.
- Supports deterministic offline demo mode and LLM-powered review mode.
- Includes explicit error handling and structured review metadata.

## How It Was Built

- **Language:** Python 3.11+
- **CLI:** argparse
- **Validation:** Pydantic
- **Testing:** pytest
- **LLM providers:** Google Gemini and OpenAI-compatible chat APIs.

The review pipeline processes the diff, identifies changed files and relevant evidence, plans review areas, invokes allowlisted read-only analysis tools, synthesizes findings, validates the response, and returns structured output.

### Analysis Tools

- `summarize_diff`: Identifies changed files, additions, deletions, and diff hunks.
- `inspect_test_coverage_hints`: Identifies likely related test files.
- `detect_basic_patterns`: Checks added lines for selected risky patterns.
- `get_changed_line_evidence`: Retrieves bounded evidence and line references.

The agent does not execute submitted code or commands from the diff.

## LLM Integration

The application supports two provider configurations:

- `LLM_PROVIDER=openai`: Uses an OpenAI-compatible chat API. Supports a configurable base URL.
- `LLM_PROVIDER=gemini`: Uses Google's Gemini `generateContent` API.

Provider integration is isolated from the core review workflow. LLM responses are validated before being returned. Transient provider failures receive bounded retries, while unrecoverable errors are reported explicitly.

A live Gemini CLI review was successfully verified using `gemini-3.1-flash-lite`. The review processed two changed files and returned structured JSON with low overall risk and no identified findings.

An OpenAI-compatible gateway was also successfully tested. A separate official OpenAI API attempt encountered an insufficient-credit error; this is an account quota limitation, not evidence of a successful official OpenAI API review.

## What Went Wrong and How It Was Handled

- **Package layout and imports:** An initially nested package structure caused import problems. The package layout was corrected.
- **Diff parsing:** Valid diffs initially produced incomplete summaries. Diff metadata extraction was corrected.
- **Parse failures:** Explicit error handling was added so parsing failures return structured errors instead of silently producing incomplete reviews.
- **Provider reliability:** API errors, rate limits, malformed responses, and temporary service failures are handled through validation, bounded retries where applicable, and explicit error reporting.
- **Test isolation:** Provider environment variables inherited by subprocess tests can affect tests that expect missing credentials. Tests must isolate provider configuration to verify fallback behavior reliably.

## Setup

Python 3.11 or later is recommended.

```bash
python -m pip install -e ".[dev]"
```

Create your local environment configuration using `.env.example` as a reference. Never commit API keys.

### Gemini Configuration (PowerShell)

```powershell
$env:LLM_PROVIDER = "gemini"
$env:GEMINI_MODEL = "gemini-3.1-flash-lite"
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
$env:DIFF_REVIEW_AGENT_TIMEOUT_SECONDS = "90"
```

### Supported Environment Variables

- `LLM_PROVIDER`: `openai` or `gemini`.
- `OPENAI_API_KEY`: API key for the OpenAI-compatible provider.
- `OPENAI_MODEL`: OpenAI-compatible model selection.
- `OPENAI_BASE_URL`: Optional compatible API endpoint.
- `GEMINI_API_KEY`: Required for Gemini.
- `GEMINI_MODEL`: Gemini model selection.
- `GEMINI_BASE_URL`: Optional Gemini API base URL.

## Usage

Run a deterministic offline review:

```bash
python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
```

Run an LLM-powered review:

```bash
python -m diff_review_agent --diff samples/sample_change.diff --mode llm --format json
```

Review a local Git revision range:

```bash
python -m diff_review_agent --base HEAD~1 --head HEAD --mode demo --format text
```

The CLI supports `--format json` and `--format text`. Provider and parsing failures are reported explicitly with structured output and a non-zero exit code.

## Testing and Verification

Run the automated test suite:

```bash
python -m pytest -q
```

Run Python compilation checks:

```bash
python -m compileall -q src tests
```

Check Git whitespace errors:

```bash
git diff --check
```

The project has previously completed a 224-test run with provider credentials isolated from the test subprocesses. Live Gemini and OpenAI-compatible gateway CLI execution were also verified separately.

## What I Would Do Next

- Integrate with hosted GitHub pull-request workflows.
- Add deeper repository context and language-aware analysis.
- Expand the evaluation dataset and measure review precision and recall.
- Improve audit logging for tool calls, retries, and provider failures.

## Known Limitations

- Demo mode uses deterministic rules, not LLM reasoning.
- LLM findings depend on model quality and the supplied diff context.
- Test-coverage detection provides hints, not proof that tests are missing.
- The agent reviews supplied changes rather than guaranteeing full repository correctness.
- Binary and unsupported files receive limited analysis.
- Live provider availability depends on API credentials, quotas, and service availability.
- Hosted pull-request integration is not implemented.

## Sample Output

See `samples/expected_demo_output.json` for an example of deterministic structured JSON output.
