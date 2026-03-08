import re
from collections import defaultdict
from threading import RLock

from backend.models.schemas import GraphData, GraphEdge, GraphNode

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


class LinkService:
    def __init__(self) -> None:
        # path -> set of paths it links to
        self._forward: dict[str, set[str]] = defaultdict(set)
        # path -> set of paths linking to it
        self._backward: dict[str, set[str]] = defaultdict(set)
        # all known paths
        self._all_paths: set[str] = set()
        self._lock = RLock()

    def parse_links(self, content: str) -> list[str]:
        return [match.group(1).strip() for match in WIKI_LINK_PATTERN.finditer(content)]

    def _normalize_link(self, link: str) -> str | None:
        link_lower = link.lower().replace(" ", "-")
        with self._lock:
            for path in self._all_paths:
                stem = path.rsplit("/", 1)[-1].replace(".md", "").lower().replace(" ", "-")
                if stem == link_lower:
                    return path
        return None

    def update_links(self, source_path: str, content: str) -> None:
        with self._lock:
            self._all_paths.add(source_path)
            old_targets = self._forward.get(source_path, set()).copy()
            for target in old_targets:
                self._backward[target].discard(source_path)

            raw_links = self.parse_links(content)
            new_targets: set[str] = set()
            for link in raw_links:
                resolved = self._normalize_link(link)
                if resolved and resolved != source_path:
                    new_targets.add(resolved)

            self._forward[source_path] = new_targets
            for target in new_targets:
                self._backward[target].add(source_path)

    def remove_note(self, path: str) -> None:
        with self._lock:
            targets = self._forward.pop(path, set())
            for target in targets:
                self._backward[target].discard(path)
            sources = self._backward.pop(path, set())
            for source in sources:
                self._forward[source].discard(path)
            self._all_paths.discard(path)

    def register_path(self, path: str) -> None:
        with self._lock:
            self._all_paths.add(path)

    def get_backlinks(self, path: str) -> list[str]:
        with self._lock:
            return sorted(self._backward.get(path, set()))

    def get_forward_links(self, path: str) -> list[str]:
        with self._lock:
            return sorted(self._forward.get(path, set()))

    def get_graph_data(self) -> GraphData:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        node_ids: set[str] = set()

        with self._lock:
            for path in self._all_paths:
                stem = path.rsplit("/", 1)[-1].replace(".md", "")
                link_count = len(self._forward.get(path, set())) + len(self._backward.get(path, set()))
                nodes.append(GraphNode(id=path, label=stem, size=max(1, link_count)))
                node_ids.add(path)

            for source, targets in self._forward.items():
                for target in targets:
                    if source in node_ids and target in node_ids:
                        edges.append(GraphEdge(source=source, target=target))

        return GraphData(nodes=nodes, edges=edges)

    def get_local_graph(self, path: str, depth: int = 1) -> GraphData:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        with self._lock:
            visited: set[str] = set()
            queue: list[tuple[str, int]] = [(path, 0)]
            relevant: set[str] = set()

            while queue:
                current, d = queue.pop(0)
                if current in visited or d > depth:
                    continue
                visited.add(current)
                relevant.add(current)
                for linked in self._forward.get(current, set()):
                    queue.append((linked, d + 1))
                for linked in self._backward.get(current, set()):
                    queue.append((linked, d + 1))

            for p in relevant:
                stem = p.rsplit("/", 1)[-1].replace(".md", "")
                link_count = len(self._forward.get(p, set())) + len(self._backward.get(p, set()))
                group = "center" if p == path else "connected"
                nodes.append(GraphNode(id=p, label=stem, group=group, size=max(1, link_count)))

            for source in relevant:
                for target in self._forward.get(source, set()):
                    if target in relevant:
                        edges.append(GraphEdge(source=source, target=target))

        return GraphData(nodes=nodes, edges=edges)
    def get_filtered_graph(
        self,
        tags: list[str] | None = None,
        folders: list[str] | None = None,
        depth: int = 0,
        tag_lookup: dict[str, set[str]] | None = None,
    ) -> GraphData:
        """Return graph data filtered by tags, folders, and/or depth.

        Args:
            tags: Only include nodes that have at least one of these tags.
            folders: Only include nodes whose path starts with one of these prefixes.
            depth: If > 0, expand the filtered set by N hops of connections.
            tag_lookup: path → set[tag] mapping (injected from tag_service).
        """
        has_filters = bool(tags) or bool(folders)
        if not has_filters:
            return self.get_graph_data()

        with self._lock:
            # Step 1: Collect seed nodes matching filters
            seed_paths: set[str] = set()

            for path in self._all_paths:
                match = True
                if tags:
                    note_tags = tag_lookup.get(path, set()) if tag_lookup else set()
                    if not note_tags.intersection(t.lower() for t in tags):
                        match = False
                if folders and match:
                    normalized = path.replace("\\", "/")
                    if not any(normalized.startswith(f.rstrip("/") + "/") or normalized == f for f in folders):
                        match = False
                if match:
                    seed_paths.add(path)

            # Step 2: Expand by depth hops
            visible: set[str] = set(seed_paths)
            if depth > 0:
                frontier = set(seed_paths)
                for _ in range(depth):
                    next_frontier: set[str] = set()
                    for p in frontier:
                        for linked in self._forward.get(p, set()):
                            if linked not in visible:
                                next_frontier.add(linked)
                        for linked in self._backward.get(p, set()):
                            if linked not in visible:
                                next_frontier.add(linked)
                    visible.update(next_frontier)
                    frontier = next_frontier

            # Step 3: Build nodes + edges from visible set
            nodes: list[GraphNode] = []
            edges: list[GraphEdge] = []

            for path in visible:
                stem = path.rsplit("/", 1)[-1].replace(".md", "")
                link_count = len(self._forward.get(path, set())) + len(self._backward.get(path, set()))
                group = "seed" if path in seed_paths else "expanded"
                nodes.append(GraphNode(id=path, label=stem, group=group, size=max(1, link_count)))

            for source in visible:
                for target in self._forward.get(source, set()):
                    if target in visible:
                        edges.append(GraphEdge(source=source, target=target))

        return GraphData(nodes=nodes, edges=edges)


link_service = LinkService()
