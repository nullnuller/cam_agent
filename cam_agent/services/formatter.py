"""
Response formatting helpers for CAM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from cam_agent.utils.rag import add_titles_to_cites, build_ctx_and_maps, build_legend


@dataclass(slots=True)
class RetrievalContext:
    """Encapsulates retrieved passages and derived helpers."""

    ctx_block: str
    legend: str
    id_to_title: Dict[int, str]
    id_to_passage: Dict[int, str]


def prepare_context(hits: Iterable[Dict]) -> RetrievalContext:
    """Build context string and lookup tables from hits."""
    ctx_block, id_to_title, id_to_passage = build_ctx_and_maps(hits)
    legend = build_legend(hits)
    return RetrievalContext(
        ctx_block=ctx_block,
        legend=legend,
        id_to_title=id_to_title,
        id_to_passage=id_to_passage,
    )


def enrich_citations(answer: str, context: RetrievalContext) -> str:
    """Inject source titles/clauses into `(see [n])` citations."""
    return add_titles_to_cites(answer, context.id_to_title, context.id_to_passage)


__all__ = ["RetrievalContext", "prepare_context", "enrich_citations"]

