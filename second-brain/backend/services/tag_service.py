import re
from collections import defaultdict
from threading import RLock

TAG_INLINE_PATTERN = re.compile(r"(?:^|\s)#([a-zA-Z\u00C0-\u024F\u0400-\u04FF][a-zA-Z0-9_\-/]*)", re.MULTILINE)
TAG_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
TAG_YAML_LINE = re.compile(r"^\s*-\s*(.+)$", re.MULTILINE)


class TagService:
    def __init__(self) -> None:
        # path -> set of tags
        self._note_tags: dict[str, set[str]] = defaultdict(set)
        self._lock = RLock()

    def extract_tags(self, content: str) -> list[str]:
        tags: set[str] = set()

        # Extract from YAML frontmatter
        fm_match = TAG_FRONTMATTER_PATTERN.match(content)
        if fm_match:
            frontmatter = fm_match.group(1)
            in_tags = False
            for line in frontmatter.split("\n"):
                stripped = line.strip()
                if stripped.startswith("tags:"):
                    value = stripped[5:].strip()
                    if value.startswith("[") and value.endswith("]"):
                        # Inline array: tags: [tag1, tag2]
                        inner = value[1:-1]
                        for t in inner.split(","):
                            t = t.strip().strip('"').strip("'")
                            if t:
                                tags.add(t.lower())
                    elif not value:
                        in_tags = True
                    continue
                if in_tags:
                    m = TAG_YAML_LINE.match(line)
                    if m:
                        tags.add(m.group(1).strip().strip('"').strip("'").lower())
                    elif not stripped.startswith("-") and stripped:
                        in_tags = False

        # Extract inline #tags (skip headings and code blocks)
        lines = content.split("\n")
        in_code = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code or line.strip().startswith("#" * 1 + " "):
                continue
            for match in TAG_INLINE_PATTERN.finditer(line):
                tag = match.group(1).lower()
                if len(tag) > 1:
                    tags.add(tag)

        return sorted(tags)

    def update_tags(self, path: str, content: str) -> list[str]:
        tags = self.extract_tags(content)
        with self._lock:
            self._note_tags[path] = set(tags)
        return tags

    def remove_note(self, path: str) -> None:
        with self._lock:
            self._note_tags.pop(path, None)

    def get_all_tags(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        with self._lock:
            for tags in self._note_tags.values():
                for tag in tags:
                    counts[tag] += 1
        return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))

    def get_notes_by_tag(self, tag: str) -> list[str]:
        tag_lower = tag.lower()
        with self._lock:
            return sorted(
                path for path, tags in self._note_tags.items() if tag_lower in tags
            )

    def get_tags_for_note(self, path: str) -> list[str]:
        with self._lock:
            return sorted(self._note_tags.get(path, set()))


tag_service = TagService()
