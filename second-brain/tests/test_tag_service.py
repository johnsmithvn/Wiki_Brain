"""Tests for TagService — tag extraction and lookup."""

from backend.services.tag_service import TagService


class TestExtractTags:
    def setup_method(self):
        self.svc = TagService()

    def test_inline_tags(self):
        content = "Some text #python and #ai-ml here"
        tags = self.svc.extract_tags(content)
        assert "python" in tags
        assert "ai-ml" in tags

    def test_frontmatter_inline_array(self):
        content = '---\ntags: [meeting, project]\n---\nBody text'
        tags = self.svc.extract_tags(content)
        assert "meeting" in tags
        assert "project" in tags

    def test_frontmatter_yaml_list(self):
        content = '---\ntags:\n  - idea\n  - brainstorm\n---\nBody'
        tags = self.svc.extract_tags(content)
        assert "idea" in tags
        assert "brainstorm" in tags

    def test_skip_headings(self):
        content = "# Heading\n## Subheading\n#real-tag"
        tags = self.svc.extract_tags(content)
        assert "real-tag" in tags
        assert "heading" not in tags

    def test_skip_code_blocks(self):
        content = "```python\n#not-a-tag\n```\n#real-tag"
        tags = self.svc.extract_tags(content)
        assert "real-tag" in tags
        assert "not-a-tag" not in tags

    def test_case_insensitive(self):
        content = "#Python #PYTHON #python"
        tags = self.svc.extract_tags(content)
        assert tags.count("python") == 1

    def test_single_char_tag_ignored(self):
        content = "#a normal #tag"
        tags = self.svc.extract_tags(content)
        assert "a" not in tags
        assert "tag" in tags


class TestTagLookup:
    def setup_method(self):
        self.svc = TagService()
        self.svc.update_tags("note1.md", "#python #ai")
        self.svc.update_tags("note2.md", "#python #web")

    def test_get_all_tags(self):
        all_tags = self.svc.get_all_tags()
        assert all_tags["python"] == 2
        assert all_tags["ai"] == 1

    def test_get_notes_by_tag(self):
        notes = self.svc.get_notes_by_tag("python")
        assert "note1.md" in notes
        assert "note2.md" in notes

    def test_get_tags_for_note(self):
        tags = self.svc.get_tags_for_note("note1.md")
        assert "python" in tags
        assert "ai" in tags

    def test_remove_note(self):
        self.svc.remove_note("note1.md")
        all_tags = self.svc.get_all_tags()
        assert all_tags["python"] == 1
        assert "ai" not in all_tags
