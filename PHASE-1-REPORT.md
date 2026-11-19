# Phase 1 --- Repository Reconnaissance and Requirements Mapping

## Repository State

**Working Directory**: `C:\Users\raghava\OneDrive\Desktop\FlexGCC_AI_Engineer_Assessment`

**Git Status**: Not a git repository (no .git directory)

**Existing Files**: Only `IMPLEMENTATION.md` (28,138 bytes)

**Runtime Environment**:
- Python 3.13.14 (via python command)
- pip 26.2.1
- Git 2.52.0.windows.1
- Node.js v26.0.0
- npm 11.12.1
- PowerShell 7.6.10

**Dependencies**: None installed yet

## Assessment Requirements Analysis

### Core Requirements (from IMPLEMENTATION.md)

1. **Candidate Information**: Name, contact, location, LinkedIn/GitHub, experience level, notice period, availability
2. **Five Technical Answers**: Each requiring personal implementation experience
3. **AI Code-Review Agent**: 
   - Accepts diff input (file or Git revision range)
   - Validates input and produces structured JSON feedback
   - Feedback includes bugs, risks, missing tests, style issues
   - Each finding has severity, explanation, evidence, recommendation
   - Uses LLM when configured, offline/demo mode works without credentials
   - Safe diff parsing, bounded output, no execution of diff content
   - Unit tests covering parsing, tool behavior, CLI path
   - Sample public/synthetic diff included
4. **Working Demo/Recording**: CLI demonstration with sample diff
5. **One-page README**: Covers what it does, how built, what went wrong, what next

### Required Implementation Phases

- **Phase 1**: Repository inspection, requirements mapping, architecture selection
- **Phase 2**: Diff ingestion and deterministic review tools
- **Phase 3**: AI reviewer and controlled tool orchestration
- **Phase 4**: End-to-end tests and demo readiness
- **Phase 5**: Candidate questionnaire, README, final audit

## Architecture Decision

**Chosen Architecture**: Python CLI with focus on compact implementation

Rationale:
- Python supports compact agent/tool workflows
- Fast automated tests via pytest
- CLI provides sufficient demonstration interface
- Avoids unnecessary infrastructure
- Compatible with 3-4 hour assessment timeline

## Proposed Project Structure

```
.
├── IMPLEMENTATION.md
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── src/
│   └── diff_review_agent/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── schemas.py
│       ├── diff_parser.py
│       ├── tools.py
│       ├── agent.py
│       └── providers/
│           ├── __init__.py
│           ├── base.py
│           └── openai_provider.py
├── tests/
│   ├── test_diff_parser.py
│   ├── test_tools.py
│   ├── test_schemas.py
│   ├── test_agent.py
│   └── test_cli.py
├── samples/
│   ├── sample_change.diff
│   └── expected_demo_output.json
└── recordings/
```

## Requirement-to-Artifact Mapping

| Requirement | Deliverable | Verification Method | Status |
|-------------|-------------|---------------------|--------|
| Candidate info complete | CANDIDATE_INFO.md | All fields filled or marked [CANDIDATE INPUT REQUIRED] | NOT STARTED |
| Five technical answers | CANDIDATE_RESPONSES.md | Each answer present, concise, factual | NOT STARTED |
| Agent accepts diff file | src/diff_review_agent/cli.py --diff path | CLI test with sample.diff | NOT STARTED |
| Agent accepts git range | src/diff_review_agent/cli.py --base ref --head ref | Git integration test | NOT STARTED |
| Structured JSON output | src/diff_review_agent/schemas.py | JSON validation test | NOT STARTED |
| Feedback categories | src/diff_review_agent/agent.py | Output contains bug/risk/test/style findings | NOT STARTED |
| LLM with tool-calling | src/diff_review_agent/providers/ | Real API call or mock with documentation | NOT STARTED |
| Offline/demo mode | src/diff_review_agent/cli.py --mode demo | CLI runs without API key | NOT STARTED |
| Safe diff parsing | src/diff_review_agent/diff_parser.py | Unit tests with malformed input | NOT STARTED |
| Unit tests | tests/ | pytest passes, coverage check | NOT STARTED |
| Sample diff | samples/sample_change.diff | Diff parses correctly | NOT STARTED |
| Demo recording | recordings/ or live demo script | Video file or documented commands | NOT STARTED |
| One-page README | README.md | Contains all 4 required sections | NOT STARTED |
| Final verification | FINAL-VERIFICATION.md | All checklist items addressed | NOT STARTED |

## Inspection Evidence (concrete)

| Check | Command | Actual Result |
|-------|---------|---------------|
| Working directory | `ls -la` (bash) | 1 file: `IMPLEMENTATION.md` (28,138 bytes) |
| Git repo? | `git status` | `fatal: not a git repository (or any of the parent directories): .git` (exit 128) |
| Branches | `git branch -a` | same fatal error (no branches exist) |
| Python | `python --version` | `Python 3.13.14` |
| `python3` alias | `python3 --version` | `command not found` (must use `python` on Windows) |
| pip | `python -m pip --version` | `pip 26.2.1 ... (python 3.13)` |
| Git CLI | `git --version` | `git version 2.52.0.windows.1` |
| Node | `node --version` | `v26.0.0` |
| npm | `npm --version` | `11.12.1` |
| PowerShell | `pwsh --version` | `PowerShell 7.6.10` |
| Hidden files | `ls -la .*` | none (no `.gitignore`, no `.env`) |
| Dependency manifests | `find . -type f` | only `IMPLEMENTATION.md` |
| Existing tests | `find . -type f` | none |
| CLAUDE.md (project) | project root | none; global instructions at `~/.claude/CLAUDE.md` + `SUPERAGENT.md` |
| Reusable existing code | n/a | none — greenfield workspace |

**Interpretation**: The workspace is greenfield. There are no user changes to preserve beyond
`IMPLEMENTATION.md`. The absence of a Git repository means the optional `--base/--head` input path
cannot be exercised in this directory unless a throwaway repo is created for tests; the `--diff`
file path is the primary supported input. No implementation code exists to audit or reuse.

## Candidate Information Gaps

The following fields must be supplied by the candidate. They are not derivable from the repository
and must not be fabricated (IMPLEMENTATION.md §"Non-negotiable execution rules" and Phase 5A):

| # | Field | Status |
|---|-------|--------|
| 1 | Full name | [CANDIDATE INPUT REQUIRED] |
| 2 | Email address | [CANDIDATE INPUT REQUIRED] |
| 3 | Phone number | [CANDIDATE INPUT REQUIRED] |
| 4 | Current city / location | [CANDIDATE INPUT REQUIRED] |
| 5 | LinkedIn URL | [CANDIDATE INPUT REQUIRED] |
| 6 | GitHub profile URL | [CANDIDATE INPUT REQUIRED] |
| 7 | Total professional experience (years) — internships excluded unless candidate confirms otherwise | [CANDIDATE INPUT REQUIRED] |
| 8 | Notice period / earliest joining date | [CANDIDATE INPUT REQUIRED] |
| 9 | Available 3 hours daily California working-hours overlap (Yes/No) | [CANDIDATE INPUT REQUIRED] |

Additional candidate inputs needed later (Phase 5B):

| # | Topic | Status |
|---|-------|--------|
| 10 | Which real AI-agent project to use for Q1 (LangGraph orchestrator / Kiddo AI / RAG / other) and which details are personally verifiable | [CANDIDATE INPUT REQUIRED] |
| 11 | Real technical failure for Q2 — what failed, root cause, exact fix, verification | [CANDIDATE INPUT REQUIRED] |
| 12 | Full-stack feature for Q3 — actual languages/frameworks/database used (do NOT assume C#/.NET/SQL Server) | [CANDIDATE INPUT REQUIRED] |
| 13 | Reliability/security example for Q4 — guardrail actually implemented and how tested | [CANDIDATE INPUT REQUIRED] |
| 14 | AI coding tools actually used + a real example of catching generated-code problems for Q5 | [CANDIDATE INPUT REQUIRED] |

## Risks and Blockers

| Risk / Blocker | Class | Impact | Mitigation |
|----------------|-------|--------|------------|
| No git repo in working dir | A (fixable) | Optional `--base/--head` path cannot be demonstrated here | Create a throwaway local repo under `samples/` or a temp dir for the git-range test; keep `--diff` as primary |
| No LLM API key | B (needs authorization) | LLM mode implemented but not live-verified | Implement offline/demo mode; document `--mode llm` as implemented-but-unverified with exact key env var names in `.env.example` |
| Recording capability in this environment | D (external) | Cannot capture video here | Provide a repeatable live-demo script; mark recording as outstanding |
| Candidate facts absent | C (human decision) | 9 form fields + 5 answers cannot be completed truthfully | Keep `[CANDIDATE INPUT REQUIRED]` placeholders; do not fabricate |
| Diff text is untrusted (prompt injection, malicious paths) | A (fixable) | Tool permission expansion / unsafe file access | Allowlisted read-only tools; never interpolate diff values into shells; never follow diff paths to read files |
| OneDrive auto-sync may touch files | D (external) | Possible file-state churn during edits | Note only; no action required |
