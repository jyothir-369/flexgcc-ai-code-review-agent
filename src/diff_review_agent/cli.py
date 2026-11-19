"""Entry point for the diff-review-agent CLI."""

"""Review a git diff and produce structured feedback."""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

import diff_review_agent.config
from diff_review_agent.agent import review_diff
from diff_review_agent.schemas import ReviewResult
from diff_review_agent.diff_parser import parse_diff_file, GitDiffInput, DiffParseError
from diff_review_agent.tools import (
    summarize_diff,
    inspect_test_coverage_hints,
    detect_basic_patterns,
    get_changed_line_evidence,
)


def setup_logging():
    """Minimal logging stub. Replace with proper logging if needed."""
    pass


def load_config():
    """Load runtime configuration from process environment and defaults."""
    return diff_review_agent.config.get_config()


def handle_diff_path(diff_arg: str) -> GitDiffInput:
    """Validate that the diff file exists and is readable."""
    if not os.path.isfile(diff_arg):
        raise DiffParseError(
            f"Diff file not found or not a regular file: {diff_arg}",
            os.path.abspath(diff_arg),
        )
    return GitDiffInput(input_type="file", path=diff_arg)


def main():
    parser = argparse.ArgumentParser(
        description="Review a git diff and produce structured feedback."
    )
    parser.add_argument("--diff", help="Path to a diff/patch file")
    parser.add_argument(
        "--mode", choices=["demo", "llm"], required=True,
        help="Run in demo (offline) or live LLM mode"
    )
    parser.add_argument("--base", default=None, help="Base git revision (optional)")
    parser.add_argument("--head", default=None, help="Head git revision (optional)")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="Output format (default: json)")
    args = parser.parse_args()

    if args.diff and (args.base or args.head):
        parser.error("Use either --diff or both --base and --head, not both.")
    if not args.diff and not (args.base and args.head):
        parser.error("Provide --diff or both --base and --head.")

    config = load_config()
    if args.diff:
        diff_input = handle_diff_path(args.diff)
    else:
        diff_input = GitDiffInput(input_type="git_range", base=args.base, head=args.head)

    result = review_diff(diff_input, config, mode=args.mode)
    if args.format == "text":
        print(result.summary)
        print(f"Risk: {result.overall_risk}")
        for finding in result.findings:
            location = finding.file or "(no file)"
            if finding.line_start is not None:
                location = f"{location}:{finding.line_start}"
            print(f"- [{finding.severity.value}] {finding.title} ({location})")
    else:
        print(result.model_dump_json(indent=2))

    if result.review_metadata.model_provider_mode == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()