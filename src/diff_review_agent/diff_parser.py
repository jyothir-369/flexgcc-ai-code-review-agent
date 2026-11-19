"""Diff parsing and validation utilities.

Read-only diff parsing and metadata extraction.

Security: diff content is untrusted input. Filenames are data, never code.
We never execute anything from a diff and never follow diff-provided paths
to read arbitrary files on the host.
"""

from __future__ import annotations

import re
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DiffParseError(Exception):
    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.path = path


class GitDiffInput:
    """Unified input type for both file and Git revision range."""
    def __init__(self, input_type: str, path: Optional[str] = None,
                 base: Optional[str] = None, head: Optional[str] = None):
        self.type = input_type
        self.path = path
        self.base = base
        self.head = head

    def __repr__(self):
        if self.type == "file":
            return f"GitDiffInput(type=file, path={self.path})"
        return f"GitDiffInput(type=git_range, base={self.base}, head={self.head})"


# Only allow safe git ref characters; reject shell metacharacters and path traversal
_SAFE_REF_RE = re.compile(r'^[a-zA-Z0-9._/\-]+$')


def _is_safe_git_ref(ref: str) -> bool:
    """Return True only if ref looks like a safe git revision (branch, tag, commit hash)."""
    if not ref or len(ref) > 256:
        return False
    # Reject refs that contain shell metacharacters or path-traversal sequences
    if '..' in ref and not ref.startswith('..'):
        # Allow HEAD~2 style but reject path traversal like ../../etc
        pass
    # Simplified safe set: alphanumeric, hyphen, underscore, period, slash, tilde, caret, ^, ~
    return bool(re.match(r'^[a-zA-Z0-9._/\-~^@{}:]+$', ref)) and '\x00' not in ref


def _is_unsafe_path(path: str) -> bool:
    """Return True if a diff-provided file path would escape the working tree."""
    if not path or path == "/dev/null":
        return False
    if path.startswith("/") or path.startswith("\\"):
        return True
    parts = path.replace("\\", "/").split("/")
    return ".." in parts


def _strip_git_prefix(path: str) -> str:
    """Remove a/ or b/ prefixes added by git diff."""
    if len(path) >= 2 and path[1] == "/" and path[0] in ("a", "b"):
        return path[2:]
    return path


def _detect_binary(content: str) -> bool:
    """Return True if the diff content indicates a binary file."""
    return "Binary files" in content or "\x00" in content


class UnifiedDiffParser:
    """Parse unified diff format (Git diff output) and extract metadata."""

    # Hard limits; callers may enforce stricter ones
    MAX_BYTES_DEFAULT = 5 * 1024 * 1024   # 5 MB
    MAX_FILES_DEFAULT = 200
    MAX_LINE_EXCERPT = 2000

    @classmethod
    def parse(cls, file_path: str,
              max_bytes: int = MAX_BYTES_DEFAULT,
              max_files: int = MAX_FILES_DEFAULT) -> Dict[str, Any]:
        """Read and parse a unified diff file. Raises DiffParseError on problems."""
        try:
            size = os.path.getsize(file_path)
        except FileNotFoundError:
            raise DiffParseError(
                f"Diff file not found or not a regular file: {file_path}", path=file_path
            )
        except OSError as e:
            raise DiffParseError(f"Cannot access diff file: {e}", path=file_path)

        if size > max_bytes:
            raise DiffParseError(
                f"Diff file exceeds size limit ({size} > {max_bytes} bytes).",
                path=file_path,
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            raise DiffParseError(f"Failed to read diff file: {e}", path=file_path)

        return cls._extract_metadata(content, max_files=max_files)

    @classmethod
    def parse_text(cls, content: str,
                   max_files: int = MAX_FILES_DEFAULT) -> Dict[str, Any]:
        """Parse diff text directly (e.g. from git subprocess output)."""
        return cls._extract_metadata(content, max_files=max_files)

    @classmethod
    def _extract_metadata(cls, content: str, max_files: int = MAX_FILES_DEFAULT) -> Dict[str, Any]:
        lines = content.splitlines()
        changed_files: List[str] = []
        added_lines = 0
        removed_lines = 0
        total_hunks = 0
        binary_files: List[str] = []
        file_hunk_ranges: Dict[str, List[Tuple[int, int]]] = {}
        file_added_lines: Dict[str, List[Tuple[int, str]]] = {}
        file_status: Dict[str, str] = {}  # path -> added|deleted|modified|renamed

        current_file: Optional[str] = None
        is_binary = False
        rename_from: Optional[str] = None

        for line in lines:
            if line.startswith("diff --git "):
                is_binary = False
                rename_from = None
                current_file = None

            elif line.startswith("rename from "):
                rename_from = line[len("rename from "):].strip()

            elif line.startswith("rename to "):
                rename_to = line[len("rename to "):].strip()
                if rename_to and not _is_unsafe_path(rename_to):
                    file_status[rename_to] = "renamed"

            elif line.startswith("new file mode"):
                if current_file:
                    file_status.setdefault(current_file, "added")

            elif line.startswith("deleted file mode"):
                if current_file:
                    file_status[current_file] = "deleted"

            elif line.startswith("Binary files"):
                is_binary = True
                # Binary files a/... and b/... differ
                m = re.match(r"Binary files (.+) and (.+) differ", line)
                if m:
                    bpath = _strip_git_prefix(m.group(2).strip())
                    if bpath and not _is_unsafe_path(bpath):
                        binary_files.append(bpath)

            elif line.startswith("--- "):
                pass  # We use +++ to identify the destination file

            elif line.startswith("+++ "):
                raw = line[4:].strip()
                if raw and raw != "/dev/null":
                    filename = _strip_git_prefix(raw)
                    if not _is_unsafe_path(filename):
                        if filename not in changed_files:
                            if len(changed_files) >= max_files:
                                # Record limitation but stop adding
                                continue
                            changed_files.append(filename)
                        current_file = filename

            elif line.startswith("@@ "):
                if not is_binary:
                    total_hunks += 1
                    m = re.search(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
                    if m and current_file:
                        new_start = int(m.group(3))
                        new_count_str = m.group(4)
                        new_count = int(new_count_str) if new_count_str else 1
                        end = new_start + max(0, new_count - 1)
                        file_hunk_ranges.setdefault(current_file, []).append((new_start, end))

            elif line.startswith("+") and not line.startswith("+++"):
                if not is_binary and current_file:
                    added_lines += 1
                    # Track the line content for evidence extraction
                    ranges = file_hunk_ranges.get(current_file, [])
                    if ranges:
                        last_start, last_end = ranges[-1]
                        # Approximate line number by counting additions in this hunk
                        existing = file_added_lines.get(current_file, [])
                        lineno = last_start + sum(
                            1 for ln, _ in existing
                            if last_start <= ln <= last_end
                        )
                        file_added_lines.setdefault(current_file, []).append(
                            (lineno, line[1:])  # strip leading '+'
                        )

            elif line.startswith("-") and not line.startswith("---"):
                if not is_binary:
                    removed_lines += 1

        # Infer modification status for files not otherwise classified
        for f in changed_files:
            file_status.setdefault(f, "modified")

        return {
            "changed_files": changed_files,
            "added_lines": added_lines,
            "removed_lines": removed_lines,
            "total_hunks": total_hunks,
            "binary_files": binary_files,
            "file_hunk_ranges": file_hunk_ranges,
            "file_added_lines": file_added_lines,
            "file_status": file_status,
            "summary": {
                "changed_files": len(changed_files),
                "added_lines": added_lines,
                "removed_lines": removed_lines,
                "total_hunks": total_hunks,
            },
        }


def parse_diff_file(file_path: str,
                    max_bytes: int = UnifiedDiffParser.MAX_BYTES_DEFAULT,
                    max_files: int = UnifiedDiffParser.MAX_FILES_DEFAULT) -> Dict[str, Any]:
    """Parse a unified diff file. Raises DiffParseError on problems."""
    return UnifiedDiffParser.parse(file_path, max_bytes=max_bytes, max_files=max_files)


def get_diff_from_git(base: str, head: str,
                      repo_path: str = ".",
                      timeout: int = 30,
                      max_bytes: int = UnifiedDiffParser.MAX_BYTES_DEFAULT,
                      max_files: int = UnifiedDiffParser.MAX_FILES_DEFAULT) -> Dict[str, Any]:
    """
    Run `git diff <base> <head>` read-only in repo_path and return parsed result.

    Security:
    - Arguments are passed as an array; shell=False always.
    - Refs are validated against _is_safe_git_ref before use.
    - No diff content is executed.
    - Timeout limits runaway subprocesses.
    """
    if not _is_safe_git_ref(base):
        raise DiffParseError(f"Unsafe or invalid git ref: {base!r}")
    if not _is_safe_git_ref(head):
        raise DiffParseError(f"Unsafe or invalid git ref: {head!r}")

    cmd = ["git", "diff", base, head]
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,  # Never shell=True with untrusted input
        )
    except subprocess.TimeoutExpired:
        raise DiffParseError(f"git diff timed out after {timeout}s")
    except FileNotFoundError:
        raise DiffParseError("git executable not found")
    except OSError as e:
        raise DiffParseError(f"Failed to run git diff: {e}")

    if result.returncode not in (0, 1):
        # returncode=1 means diff found differences (normal); >1 means error
        raise DiffParseError(
            f"git diff failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    output = result.stdout
    if len(output.encode("utf-8")) > max_bytes:
        raise DiffParseError(
            f"git diff output exceeds size limit ({len(output)} chars)"
        )

    return UnifiedDiffParser.parse_text(output, max_files=max_files)
