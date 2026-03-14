"""
Chunker Service — Markdown → semantic chunks.

Splits markdown by heading boundaries, then by paragraph if section
exceeds MAX_TOKENS.  Merges small consecutive chunks below MIN_TOKENS.

Pure function — no I/O, no state, no side effects.

Design ref: docs/DESIGN-chunking-retrieval.md §2
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt

from backend.config.retrieval import MAX_TOKENS, MIN_TOKENS, TARGET_TOKENS

# Reusable parser — thread-safe (stateless after init)
_md = MarkdownIt("commonmark")

# Frontmatter fence pattern
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)


@dataclass
class Chunk:
    chunk_id: str  # "ai/rag.md#2"
    note_path: str  # "ai/rag.md"
    note_title: str  # "RAG Pipeline"
    heading: str  # "Retrieval"
    chunk_index: int  # 2
    content: str  # actual text
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    token_count: int = 0


def _count_tokens(text: str) -> int:
    """Approximate token count via whitespace split.

    Good enough for chunking (±10% vs tiktoken).  Avoids heavy dependency.
    """
    return len(text.split())


def _extract_title(markdown_text: str) -> str:
    """Extract title from first H1 or first non-frontmatter line."""
    in_frontmatter = False
    for line in markdown_text.split("\n"):
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped:
            return stripped
    return "Untitled"


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block from markdown."""
    return _FRONTMATTER_RE.sub("", text, count=1)


def _collect_sections(tokens: list) -> list[dict]:
    """Walk markdown-it tokens and group content by heading sections.

    Returns list of dicts: {"heading": str, "content": str}
    """
    sections: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # Heading boundary — flush previous section, start new
        if tok.type == "heading_open":
            # Flush accumulated content
            if current_lines:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip(),
                })
                current_lines = []

            # Extract heading text from inline token
            _level = tok.tag  # h1, h2, ...  # noqa: F841
            heading_text = ""
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                heading_text = tokens[i + 1].content
            current_heading = heading_text
            # Skip heading_open, inline, heading_close
            i += 3
            continue

        # Accumulate content from block tokens
        if tok.type == "fence":
            # Code block — keep intact
            info = tok.info.strip() if tok.info else ""
            code = tok.content.rstrip("\n")
            if info:
                current_lines.append(f"```{info}\n{code}\n```")
            else:
                current_lines.append(f"```\n{code}\n```")
        elif tok.type == "inline":
            current_lines.append(tok.content)
        elif tok.type == "paragraph_open":
            pass  # content comes in inline
        elif tok.type == "paragraph_close":
            current_lines.append("")  # blank line between paragraphs
        elif tok.type == "bullet_list_open":
            pass
        elif tok.type == "list_item_open":
            pass
        elif tok.type == "list_item_close":
            pass
        elif tok.type == "bullet_list_close":
            current_lines.append("")
        elif tok.type == "ordered_list_open":
            pass
        elif tok.type == "ordered_list_close":
            current_lines.append("")
        elif tok.type == "blockquote_open":
            pass
        elif tok.type == "blockquote_close":
            current_lines.append("")
        elif tok.type == "hr":
            pass  # skip horizontal rules
        elif tok.type == "html_block":
            current_lines.append(tok.content.strip())

        i += 1

    # Flush last section
    if current_lines:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_lines).strip(),
        })

    return sections


def _split_by_paragraph(text: str, target: int = TARGET_TOKENS) -> list[str]:
    """Split a large section into paragraph-based chunks targeting *target* tokens."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_tokens = _count_tokens(para)

        if current_tokens + para_tokens > target and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_tokens = para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_note(markdown_text: str, note_path: str) -> list[Chunk]:
    """Split a markdown note into semantic chunks.

    Algorithm:
      1. Strip frontmatter
      2. Parse AST via markdown-it-py
      3. Group tokens by heading sections
      4. Split large sections (> MAX_TOKENS) by paragraph
      5. Merge small consecutive chunks (< MIN_TOKENS)
      6. Attach metadata (title, heading, tags, links)

    Returns:
        List of Chunk objects ready for embedding.
    """
    title = _extract_title(markdown_text)
    body = _strip_frontmatter(markdown_text)

    if not body.strip():
        return []

    tokens = _md.parse(body)
    sections = _collect_sections(tokens)

    if not sections:
        return []

    # --- Step 1: Build raw chunks (split large sections) ---
    raw_chunks: list[dict] = []
    for section in sections:
        content = section["content"]
        if not content.strip():
            continue

        token_count = _count_tokens(content)
        if token_count > MAX_TOKENS:
            parts = _split_by_paragraph(content, TARGET_TOKENS)
            for part in parts:
                raw_chunks.append({
                    "heading": section["heading"],
                    "content": part,
                    "tokens": _count_tokens(part),
                })
        else:
            raw_chunks.append({
                "heading": section["heading"],
                "content": content,
                "tokens": token_count,
            })

    if not raw_chunks:
        return []

    # --- Step 2: Merge small chunks ---
    merged: list[dict] = [raw_chunks[0]]
    for chunk in raw_chunks[1:]:
        prev = merged[-1]
        # Merge if previous chunk is small AND same heading (or both headingless)
        if prev["tokens"] < MIN_TOKENS and prev["heading"] == chunk["heading"]:
            prev["content"] = prev["content"] + "\n\n" + chunk["content"]
            prev["tokens"] = _count_tokens(prev["content"])
        else:
            merged.append(chunk)

    # Final pass: merge any remaining tiny trailing chunk
    if len(merged) > 1 and merged[-1]["tokens"] < MIN_TOKENS:
        merged[-2]["content"] = merged[-2]["content"] + "\n\n" + merged[-1]["content"]
        merged[-2]["tokens"] = _count_tokens(merged[-2]["content"])
        merged.pop()

    # --- Step 3: Build Chunk objects ---
    result: list[Chunk] = []
    for idx, item in enumerate(merged):
        chunk = Chunk(
            chunk_id=f"{note_path}#{idx}",
            note_path=note_path,
            note_title=title,
            heading=item["heading"],
            chunk_index=idx,
            content=item["content"],
            token_count=item["tokens"],
        )
        result.append(chunk)

    return result


def format_embedding_input(chunk: Chunk) -> str:
    """Format chunk for embedding model input.

    Prepends title + heading for richer semantic context.
    """
    parts: list[str] = []
    if chunk.note_title:
        parts.append(f"Title: {chunk.note_title}")
    if chunk.heading:
        parts.append(f"Section: {chunk.heading}")
    parts.append("")
    parts.append(chunk.content)
    return "\n".join(parts)
