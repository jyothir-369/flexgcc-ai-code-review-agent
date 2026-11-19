# PHASE-5-REPORT.md — Candidate Questionnaire, README, Final Audit, and Submission Package

## Status: COMPLETE (with expected candidate-input placeholders)

Date: 2026-11-19

---

## A. Candidate Information

The form fields below **require the candidate's own input**. They have been left as explicit
`[CANDIDATE INPUT REQUIRED]` placeholders in `CANDIDATE_RESPONSES.md`.
No personal data has been fabricated or inferred.

| Field | Status |
|-------|--------|
| Full name | `[CANDIDATE INPUT REQUIRED]` |
| Email address | `[CANDIDATE INPUT REQUIRED]` |
| Phone number | `[CANDIDATE INPUT REQUIRED]` |
| Current city / location | `[CANDIDATE INPUT REQUIRED]` |
| LinkedIn URL | `[CANDIDATE INPUT REQUIRED]` |
| GitHub profile URL | `[CANDIDATE INPUT REQUIRED]` |
| Total professional experience | `[CANDIDATE INPUT REQUIRED]` |
| Notice period / earliest joining date | `[CANDIDATE INPUT REQUIRED]` |
| California hours overlap (Yes/No) | `[CANDIDATE INPUT REQUIRED]` |

---

## B. Five Technical Experience Answers

All five answers have been drafted in `CANDIDATE_RESPONSES.md` with explicit prompt text
and `[CANDIDATE INPUT REQUIRED]` markers. The candidate must supply first-person,
project-specific answers for each. Templates are provided per the assessment rubric.

**Why placeholders, not invented answers:**
The IMPLEMENTATION.md rules forbid fabricating candidate experience. Inventing facts
would produce misleading submission content and violate assessment integrity.

---

## C. One-Page README

`README.md` covers all four required assessment topics:

| Required topic | Present | Location |
|----------------|---------|----------|
| What it does (input, categories, output) | Yes | "What It Does" section |
| How it was built (language, framework, model, orchestration, tools) | Yes | "How It Was Built" section |
| What went wrong and how it was handled | Yes | "What Went Wrong and How It Was Handled" section |
| What I would do next | Yes | "What I Would Do Next" section |

Also included: prerequisites, environment variable names (never values), exact demo command,
exact test command, link to sample JSON, and known limitations.

README length: approximately one page (72 lines).

---

## D. Final Audit and Packaging

### D1. Secrets audit

No secrets, API keys, or tokens found in tracked or untracked files.

| Check | Result |
|-------|--------|
| `.env` file absent (gitignored) | PASS — no `.env` file; `.env.example` contains placeholders only |
| `OPENAI_API_KEY` not in source | PASS — agent reads from env var; not hardcoded anywhere |
| Temp/demo files (`demo_output.json`, `demo_err_tmp.txt`, `tmp.diff`) | PASS — contain only synthetic diff and demo JSON; no credentials |
| Candidate personal data in source | N/A — all form fields are placeholders; no real PII committed |

### D2. Untracked / temporary files

The following untracked files are safe-but-not-committed artifacts from prior phases:

| File | Content | Action |
|------|---------|--------|
| `demo_output.json` | Synthetic demo output | Not sensitive; may be committed or left untracked |
| `demo_output_tmp.json` | Intermediate demo run | Safe; temporary; can be deleted |
| `demo_err_tmp.txt` | Stderr from a demo run | Safe; temporary; can be deleted |
| `tmp.diff` | Synthetic diff used in testing | Safe; temporary |
| `tmp/` | Temp directory from phase runs | Safe; can be removed |
| `src/diff_review_agent/diff_parser.py.bak` | Backup from Phase 2 rewrite | Safe; can be removed |
| `PHASE-2-REPORT.md` through `PHASE-4-REPORT.md` | Phase evidence docs | Useful to keep; no PII |

None of these files contain employer code, confidential data, API keys, or private paths.

### D3. Demo commands verified

All commands run from the repository root on 2026-11-19:

**Setup:**
```
pip install -e ".[dev]"
```

**Demo (deterministic, no API key needed):**
```
python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
```
Actual result: valid JSON, exit 0. Output matches `samples/expected_demo_output.json`.

**LLM mode (requires API key — not live-verified):**
```
export OPENAI_API_KEY=sk-...
python -m diff_review_agent --diff samples/sample_change.diff --mode llm --format json
```
Not run: no real API key in this environment. LLM mode is implemented and mock-tested.
See Known Limitations below.

**Tests:**
```
python -m pytest tests/ -v
```
Actual result: `170 passed in 15.16s`.

**Help:**
```
python -m diff_review_agent --help
```
Exit 0, documents `--diff`, `--mode`, `--format`, `--base`, `--head`.

### D4. JSON sample validation

`samples/expected_demo_output.json` is valid JSON (confirmed by Python's `json` module
in test_phase4.py::test_expected_output_file_is_valid_json). It matches the actual
CLI output on all key fields: `overall_risk`, `model_provider_mode`, `reviewed_file_count`,
and finding count.

### D5. Recording

No screen recording was captured — the environment does not support screen capture.
A reliable live-demo script is provided instead (see Demo Walkthrough below).

---

## Demo Walkthrough

### Prerequisites

```bash
# Python 3.11+ required (project tested on Python 3.13.14)
pip install -e ".[dev]"
```

### Step-by-step reproducible demo

**1. Show the input diff**
```bash
# On Windows
type samples\sample_change.diff

# On Linux/macOS
cat samples/sample_change.diff
```
This is a synthetic Python diff adding a divide-by-zero risk and a new function.

**2. Run in demo mode (no API key required)**
```bash
python -m diff_review_agent --diff samples/sample_change.diff --mode demo --format json
```

Expected output (exact):
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
    "model_provider_mode": "demo",
    "reviewed_file_count": 2
  }
}
```

**3. Explain a finding**

The `missing_test` finding identifies `calculator.py` as a changed source file with no
visible companion test file. `is_speculative: true` and `confidence: 0.5` correctly
reflect that this is a naming-convention hint — test existence is not proven absent.

**4. Show failure-safe behavior**
```bash
# Oversized diff
python -m diff_review_agent --diff /nonexistent.diff --mode demo --format json
# → non-zero exit, error message to stderr, no crash

# Missing required arg
python -m diff_review_agent --mode demo --format json
# → non-zero exit, argparse error
```

**5. Run LLM mode (if API key is available)**
```bash
export OPENAI_API_KEY=sk-...          # or set OPENAI_API_KEY=sk-... on Windows
python -m diff_review_agent --diff samples/sample_change.diff --mode llm --format json
```
Without a key, the agent falls back to demo mode and adds a limitation note.

**6. Run tests**
```bash
python -m pytest tests/ -v
# 170 passed
```

---

## Final Submission Checklist

| Item | Status | Notes |
|------|--------|-------|
| Agent accepts diff file, validates, produces JSON | PASS | Verified 2026-11-19 |
| Feedback includes bugs, risks, missing tests, style | PASS | All four categories implemented |
| Each finding has severity, evidence, confidence, speculative flag | PASS | Schema-validated |
| LLM mode configured via env vars; not hardcoded | PASS | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` |
| Offline/demo mode works without credentials | PASS | Explicitly labeled "demo" |
| Diff size and file count bounded | PASS | Configurable via env vars |
| Binary/unsupported files handled gracefully | PASS | Excluded from count |
| Malformed input handled safely | PASS | Returns error result, not crash |
| No diff content executed | PASS | Verified by test |
| Unit tests: 170 passing | PASS | `python -m pytest tests/ -v` → 170 passed |
| Sample diff included | PASS | `samples/sample_change.diff` |
| Sample output included | PASS | `samples/expected_demo_output.json` |
| One-page README covers all four topics | PASS | `README.md` |
| No secrets in source control | PASS | `.env` is gitignored |
| No employer or confidential code | PASS | Only synthetic fixtures used |
| Candidate information form present | PARTIAL | Placeholders; candidate input required |
| Five technical answers present | PARTIAL | Placeholders; candidate input required |
| Screen recording | N/A | Environment cannot capture; live-demo script provided |
| FINAL-VERIFICATION.md updated | PASS | Updated with actual evidence |
| PHASE-5-REPORT.md created | PASS | This file |

---

## Phase 5 Acceptance Criteria

- [x] Candidate information: form present with all fields; missing input explicitly marked.
- [x] Five technical answers: all five prompts drafted; all require candidate personal facts.
- [x] One-page README covers all four required topics plus setup, env vars, commands, sample, limitations.
- [x] Demo: deterministic live-demo script provided; step-by-step walkthrough documented.
- [x] Final tests rerun: 170/170 pass (2026-11-19, Python 3.13.14, pytest-8.4.2).
- [x] Demo command rerun: exit 0, valid JSON, matches expected output.
- [x] No secrets or employer code in submission.
- [x] FINAL-VERIFICATION.md updated with actual evidence.

---

## Known Limitations and Submission Blockers

### Limitations (by design)

1. **No live LLM verification** — LLM mode is implemented and mock-tested but not verified
   with a real API call. Label: UNVERIFIED. Reason: no API key in environment.
   To verify: set `OPENAI_API_KEY` and run `--mode llm`.

2. **Local diff only** — Not a hosted pull-request integration. Only local `.diff` files
   and `git diff` revision ranges are supported.

3. **Test coverage hints are heuristic** — `inspect_test_coverage_hints` uses file-naming
   conventions only. It reports hints, not proof of missing tests.

4. **Single provider** — Only OpenAI-compatible APIs. No Anthropic, Ollama, or local model.

5. **No screen recording** — Environment has no screen capture. Live-demo script above
   is the documented alternative.

### Submission blockers

- **Candidate personal information** — All nine form fields require the candidate's own input.
- **Five technical answers** — All five questionnaire answers require the candidate's
  first-person account of real projects and decisions.
