"""Diff parsing and validation utilities.

Read-only diff parsing and metadata extraction.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GitDiffInput:
    type: str  # "file"
    path: str


class DiffParseError(Exception):
    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.path = path


class UnifiedDiffParser:
    """Parse unified diff format (Git diff output) and extract metadata."""

    @staticmethod
    def parse(file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except FileNotFoundError as e:
            raise DiffParseError(f"Diff file not found or not a regular file: {file_path}", path=file_path)
        except Exception as e:
            raise DiffParseError(f"Failed to read diff file: {e}", path=file_path)
        return UnifiedDiffParser._extract_metadata(content)

    @staticmethod
    def _extract_metadata(content: str) -> Dict[str, Any]:
        lines = content.splitlines()
        changed_files = []
        added_lines = 0
        removed_lines = 0
        total_hunks = 0
        file_hunk_ranges: Dict[str, List[Tuple[int, int]]] = {}

        current_file = None
        current_hunk_range: Optional[Tuple[int, int]] = None

        for line in lines:
            if line.startswith('diff --git '):
                # Extract filenames
                parts = line.split()
                current_file = None
            elif line.startswith('@@ '):
                total_hunks += 1
                match = re.search(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2) or 1)
                    new_start = int(match.group(3))
                    new_count = int(match.group(4) or 1)
                    if current_file:
                        if current_file not in file_hunk_ranges:
                            file_hunk_ranges[current_file] = []
                        file_hunk_ranges[current_file].append((new_start, new_start + max(0, new_count - 1)))
            elif line.startswith('+++ '):
                # Track the new-side file path; '---' is the old side.
                filename = line[4:].strip()
                if filename and filename != '/dev/null':
                    # Strip Git's a/ b/ prefixes; keep path relative (untrusted data).
                    if filename.startswith('b/'):
                        filename = filename[2:]
                    if filename not in changed_files:
                        changed_files.append(filename)
                    current_file = filename
            elif line.startswith('--- '):
                pass
            elif line.startswith('+'):
                added_lines += 1
            elif line.startswith('-'):
                removed_lines += 1

        return {
            'changed_files': changed_files,
            'added_lines': added_lines,
            'removed_lines': removed_lines,
            'total_hunks': total_hunks,
            'file_hunk_ranges': file_hunk_ranges,
            'summary': UnifiedDiffParser._build_summary(
                changed_files, added_lines, removed_lines, total_hunks
            ),
        }

    @staticmethod
    def _build_summary(changed_files, added_lines, removed_lines, total_hunks) -> Dict[str, Any]:
        return {
            'changed_files': len(changed_files),
            'added_lines': added_lines,
            'removed_lines': removed_lines,
            'total_hunks': total_hunks,
        }

# Backward-compatible function
def parse_diff_file(file_path: str) -> Dict[str, Any]:
    return UnifiedDiffParser.parse(file_path)