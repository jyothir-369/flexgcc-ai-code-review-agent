"""Tests for diff parser - required by assessment."""

"""Unit tests for diff parsing, tools, schemas, and CLI."""

import pytest
from pathlib import Path

from diff_review_agent.diff_parser import parse_diff_file, GitDiffInput, DiffParseError


def test_parse_diff_file_exists(tmp_path):
    # Create a small valid-looking diff
    diff_content = """diff --git a/test_module.py b/test_module.py
index abc1234..def5678 100644
--- a/test_module.py
+++ b/test_module.py
@@ -1,4 +1,5 @@
 def hello():
     print("hello")
+    print("world")
 """
    p = tmp_path / "test.diff"
    p.write_text(diff_content)
    result = parse_diff_file(str(p))
    assert result["added_lines"] >= 1
    assert len(result["changed_files"]) > 0


def test_nonexistent_diff_raises():
    with pytest.raises(DiffParseError):
        parse_diff_file("/nonexistent/path.diff")


def test_empty_diff_returns_zeroes():
    diff_content = ""
    p = Path("tmp.diff")
    p.write_text(diff_content)
    result = parse_diff_file(str(p))
    assert result["summary"]["changed_files"] == 0
    assert result["added_lines"] == 0
    assert result["removed_lines"] == 0
    assert result["total_hunks"] == 0


def test_unified_diff_parses_hunks():
    diff_content = """diff --git a/foo.py b/foo.py
index abc1234..def5678 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def foo():
-    old
+    new
+    added
 """
    p = Path("tmp.diff")
    p.write_text(diff_content)
    result = parse_diff_file(str(p))
    assert result["total_hunks"] >= 1
    assert result["added_lines"] >= 1
    assert result["removed_lines"] >= 1