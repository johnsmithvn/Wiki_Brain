"""Tests for LinkService — wiki-link parsing, graph data, and filtering."""

from backend.services.link_service import LinkService


class TestParseLinks:
    def setup_method(self):
        self.svc = LinkService()

    def test_simple_link(self):
        links = self.svc.parse_links("Text with [[Note A]] link")
        assert "Note A" in links

    def test_aliased_link(self):
        links = self.svc.parse_links("Link to [[Note B|custom alias]]")
        assert "Note B" in links

    def test_multiple_links(self):
        links = self.svc.parse_links("[[A]] and [[B]] and [[C|alias]]")
        assert len(links) == 3

    def test_no_links(self):
        links = self.svc.parse_links("Plain text without links")
        assert len(links) == 0


class TestForwardBackward:
    def setup_method(self):
        self.svc = LinkService()
        self.svc.register_path("Note A.md")
        self.svc.register_path("Note B.md")
        self.svc.register_path("Note C.md")

    def test_update_creates_edges(self):
        self.svc.update_links("Note A.md", "Links to [[Note B]]")
        fwd = self.svc.get_forward_links("Note A.md")
        back = self.svc.get_backlinks("Note B.md")
        assert "Note B.md" in fwd
        assert "Note A.md" in back

    def test_update_removes_old_edges(self):
        self.svc.update_links("Note A.md", "Links to [[Note B]]")
        self.svc.update_links("Note A.md", "Now links to [[Note C]]")
        fwd = self.svc.get_forward_links("Note A.md")
        assert "Note C.md" in fwd
        assert "Note B.md" not in fwd

    def test_remove_note_cleans_edges(self):
        self.svc.update_links("Note A.md", "Links to [[Note B]]")
        self.svc.remove_note("Note A.md")
        back = self.svc.get_backlinks("Note B.md")
        assert "Note A.md" not in back


class TestGraphData:
    def setup_method(self):
        self.svc = LinkService()
        self.svc.register_path("Note A.md")
        self.svc.register_path("Note B.md")
        self.svc.update_links("Note A.md", "Links to [[Note B]]")

    def test_full_graph(self):
        graph = self.svc.get_graph_data()
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1


class TestFilteredGraph:
    def setup_method(self):
        self.svc = LinkService()
        for p in ["a.md", "b.md", "daily/c.md"]:
            self.svc.register_path(p)
        self.svc.update_links("a.md", "[[b]]")
        self.svc.update_links("daily/c.md", "[[a]]")

    def test_filter_by_folder(self):
        graph = self.svc.get_filtered_graph(folders=["daily"])
        node_ids = {n.id for n in graph.nodes}
        assert "daily/c.md" in node_ids
        assert "a.md" not in node_ids

    def test_filter_by_tag(self):
        tag_lookup = {"a.md": {"python"}, "b.md": set(), "daily/c.md": {"python"}}
        graph = self.svc.get_filtered_graph(tags=["python"], tag_lookup=tag_lookup)
        node_ids = {n.id for n in graph.nodes}
        assert "a.md" in node_ids
        assert "daily/c.md" in node_ids
        assert "b.md" not in node_ids

    def test_empty_filter_returns_full(self):
        graph = self.svc.get_filtered_graph()
        assert len(graph.nodes) == 3

    def test_depth_expansion(self):
        tag_lookup = {"a.md": {"python"}, "b.md": set(), "daily/c.md": set()}
        graph = self.svc.get_filtered_graph(tags=["python"], depth=1, tag_lookup=tag_lookup)
        node_ids = {n.id for n in graph.nodes}
        # a.md is seed, b.md linked from a, daily/c.md links to a → all reachable in 1 hop
        assert "a.md" in node_ids
        assert "b.md" in node_ids
        assert "daily/c.md" in node_ids
