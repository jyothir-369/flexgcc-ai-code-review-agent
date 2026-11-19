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
    """Load config from .env (if present) and defaults."""
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
    parser.add_argument("--diff", required=True, help="Path to a diff/patch file")
    parser.add_argument(
        "--mode", choices=["demo", "llm"], required=True,
        help="Run in demo (offline) or live LLM mode"
    )
    parser.add_argument("--base", default=None, help="Base git revision (optional)")
    parser.add_argument("--head", default=None, help="Head git revision (optional)")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="Output format (default: json)")
    args = parser.parse_args()

    config = load_config()
    diff_input = handle_diff_path(args.diff)

    if args.mode == "demo":
        result = review_diff(diff_input, config, mode="demo")
    else:
        result = review_diff(diff_input, config, mode="llm")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()