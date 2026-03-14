"""
Graph Expansion Service — BFS expansion from seed notes via wiki-link graph.

Used by RAG pipeline to discover related notes that vector search might miss.

Design ref: docs/DESIGN-graph-vector-reasoning.md §4
"""

from __future__ import annotations

import logging

from backend.services.link_service import link_service

logger = logging.getLogger(__name__)


def expand_notes(
    seed_notes: list[str],
    depth: int = 1,
    max_neighbors: int = 5,
) -> list[str]:
    """BFS expand from seed notes → return neighbor paths (excluding seeds).

    Args:
        seed_notes: Starting note paths (from vector search).
        depth: BFS depth (1 = direct neighbors only).
        max_neighbors: Maximum neighbor paths to return.
    """
    seed_set = set(seed_notes)
    neighbors: set[str] = set()

    current_frontier = set(seed_notes)
    for _ in range(depth):
        next_frontier: set[str] = set()
        for note_path in current_frontier:
            forward = link_service._forward.get(note_path, set())
            backward = link_service._backward.get(note_path, set())
            next_frontier.update(forward | backward)
        next_frontier -= seed_set
        next_frontier -= neighbors
        neighbors.update(next_frontier)
        current_frontier = next_frontier

    result = sorted(neighbors)[:max_neighbors]
    logger.debug("Graph expand: %d seeds → %d neighbors", len(seed_notes), len(result))
    return result


def graph_proximity_score(note_path: str, seed_notes: list[str]) -> float:
    """Score a note's proximity to seed notes via the wiki-link graph.

    Returns:
        1.0 — note is one of the seeds
        0.7 — note is a direct (1-hop) neighbor of any seed
        0.0 — not connected
    """
    if note_path in seed_notes:
        return 1.0

    for seed in seed_notes:
        forward = link_service._forward.get(seed, set())
        backward = link_service._backward.get(seed, set())
        if note_path in (forward | backward):
            return 0.7

    return 0.0
