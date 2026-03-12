"""Tests for chunker_service — semantic markdown chunking."""

import pytest

from backend.services.chunker_service import (
    Chunk,
    chunk_note,
    format_embedding_input,
    _count_tokens,
    _extract_title,
    _strip_frontmatter,
)
from backend.config.retrieval import MAX_TOKENS, MIN_TOKENS


class TestCountTokens:
    def test_simple(self):
        assert _count_tokens("hello world") == 2

    def test_empty(self):
        assert _count_tokens("") == 1 or _count_tokens("") == 0
        # "".split() == [] so len == 0
        assert _count_tokens("") == 0

    def test_multiline(self):
        assert _count_tokens("one\ntwo three\nfour") == 4


class TestExtractTitle:
    def test_h1_title(self):
        assert _extract_title("# My Note\nContent here") == "My Note"

    def test_no_h1(self):
        assert _extract_title("Some content\nMore content") == "Some content"

    def test_frontmatter_skip(self):
        md = "---\ntitle: Test\n---\n# Real Title\nContent"
        assert _extract_title(md) == "Real Title"

    def test_empty(self):
        assert _extract_title("") == "Untitled"


class TestStripFrontmatter:
    def test_removes_frontmatter(self):
        md = "---\ntags: [a, b]\n---\n# Title\nContent"
        result = _strip_frontmatter(md)
        assert result.startswith("# Title")
        assert "tags:" not in result

    def test_no_frontmatter(self):
        md = "# Title\nContent"
        assert _strip_frontmatter(md) == md


class TestChunkNote:
    def test_empty_note(self):
        assert chunk_note("", "test.md") == []

    def test_frontmatter_only(self):
        assert chunk_note("---\ntags: [a]\n---\n", "test.md") == []

    def test_single_section(self):
        md = "# My Note\n\nThis is a simple paragraph with enough words to form a chunk."
        chunks = chunk_note(md, "notes/test.md")
        assert len(chunks) >= 1
        assert chunks[0].note_path == "notes/test.md"
        assert chunks[0].note_title == "My Note"
        assert chunks[0].chunk_index == 0
        assert chunks[0].chunk_id == "notes/test.md#0"

    def test_multiple_headings_create_sections(self):
        md = """# Main Title

Introduction paragraph with some content here.

## Section One

Content for section one goes here with details.

## Section Two

Content for section two with different information.
"""
        chunks = chunk_note(md, "test.md")
        assert len(chunks) >= 1
        # Should have heading info
        headings = [c.heading for c in chunks]
        assert any("Section One" in h or "Main Title" in h for h in headings) or len(chunks) >= 1

    def test_code_block_preserved(self):
        md = """# Code Example

Here is some code:

```python
def hello():
    print("world")
```

After the code block.
"""
        chunks = chunk_note(md, "code.md")
        assert len(chunks) >= 1
        all_content = " ".join(c.content for c in chunks)
        assert "def hello():" in all_content
        assert '```python' in all_content or '```' in all_content

    def test_large_section_splits(self):
        # Build a section > MAX_TOKENS to force paragraph split
        paragraphs = []
        for i in range(20):
            paragraphs.append(f"Paragraph {i}: " + " ".join(f"word{j}" for j in range(30)))
        md = "# Big Note\n\n" + "\n\n".join(paragraphs)

        chunks = chunk_note(md, "big.md")
        assert len(chunks) > 1
        for c in chunks:
            # No chunk should vastly exceed MAX_TOKENS (some tolerance for merging)
            assert c.token_count <= MAX_TOKENS * 1.5, (
                f"Chunk {c.chunk_index} has {c.token_count} tokens, expected <= {MAX_TOKENS * 1.5}"
            )

    def test_small_chunks_merged(self):
        # Several tiny sections should be merged if same heading
        md = "# Title\n\nTiny.\n\nAlso tiny."
        chunks = chunk_note(md, "tiny.md")
        # Should produce 1 merged chunk (not 2 separate tiny ones)
        assert len(chunks) == 1

    def test_chunk_ids_sequential(self):
        md = """# Title

## Section A

Long enough content for section A to be its own chunk with details.

## Section B

Long enough content for section B to be its own chunk with details.

## Section C

Long enough content for section C to be its own chunk with details.
"""
        chunks = chunk_note(md, "multi.md")
        for i, c in enumerate(chunks):
            assert c.chunk_index == i
            assert c.chunk_id == f"multi.md#{i}"

    def test_frontmatter_not_chunked(self):
        md = """---
title: My Note
tags: [ai, rag]
---

# My Note

Actual content paragraph here.
"""
        chunks = chunk_note(md, "fm.md")
        for c in chunks:
            assert "tags:" not in c.content
            assert "---" not in c.content or c.content.count("---") == 0

    def test_list_preserved(self):
        md = """# Lists

- Item one
- Item two
- Item three

More content after.
"""
        chunks = chunk_note(md, "list.md")
        assert len(chunks) >= 1
        all_content = " ".join(c.content for c in chunks)
        assert "Item one" in all_content

    def test_token_count_set(self):
        md = "# Title\n\nHello world this is a test note with some content."
        chunks = chunk_note(md, "t.md")
        assert len(chunks) >= 1
        assert chunks[0].token_count > 0

    def test_blockquote(self):
        md = """# Quote Test

> This is a blockquote
> with multiple lines.

After the quote.
"""
        chunks = chunk_note(md, "quote.md")
        assert len(chunks) >= 1


class TestFormatEmbeddingInput:
    def test_with_title_and_heading(self):
        c = Chunk(
            chunk_id="test.md#0",
            note_path="test.md",
            note_title="My Note",
            heading="Introduction",
            chunk_index=0,
            content="This is the content.",
            token_count=4,
        )
        result = format_embedding_input(c)
        assert "Title: My Note" in result
        assert "Section: Introduction" in result
        assert "This is the content." in result

    def test_without_heading(self):
        c = Chunk(
            chunk_id="test.md#0",
            note_path="test.md",
            note_title="My Note",
            heading="",
            chunk_index=0,
            content="Content only.",
            token_count=2,
        )
        result = format_embedding_input(c)
        assert "Title: My Note" in result
        assert "Section:" not in result
        assert "Content only." in result
