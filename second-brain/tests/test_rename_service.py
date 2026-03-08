"""Tests for RenameService — wiki-link rewriting on note rename."""

from backend.services.rename_service import _rewrite_content, _stem_from_path


class TestStemFromPath:
    def test_simple(self):
        assert _stem_from_path("Note A.md") == "Note A"

    def test_nested(self):
        assert _stem_from_path("daily/My Note.md") == "My Note"

    def test_no_extension(self):
        assert _stem_from_path("folder/test.md") == "test"


class TestRewriteContent:
    def test_simple_link(self):
        content = "Text with [[Note A]] here"
        result, count = _rewrite_content(content, "Note A", "Note B")
        assert "[[Note B]]" in result
        assert count == 1

    def test_aliased_link(self):
        content = "Link to [[Note A|my alias]]"
        result, count = _rewrite_content(content, "Note A", "Note B")
        assert "[[Note B|my alias]]" in result
        assert count == 1

    def test_multiple_links(self):
        content = "[[Note A]] and [[Note A|x]] and [[Note A]]"
        result, count = _rewrite_content(content, "Note A", "Note B")
        assert result.count("[[Note B]]") == 2
        assert "[[Note B|x]]" in result
        assert count == 3

    def test_case_insensitive(self):
        content = "[[note a]] and [[NOTE A]]"
        result, count = _rewrite_content(content, "Note A", "Note B")
        assert count == 2

    def test_skip_code_blocks(self):
        content = "```\n[[Note A]]\n```\n[[Note A]]"
        result, count = _rewrite_content(content, "Note A", "Note B")
        assert count == 1
        # Inside code block should be unchanged
        lines = result.split("\n")
        assert lines[1] == "[[Note A]]"
        assert lines[3] == "[[Note B]]"

    def test_no_match(self):
        content = "No links to [[Note C]] here"
        result, count = _rewrite_content(content, "Note A", "Note B")
        assert count == 0
        assert result == content
