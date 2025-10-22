"""
Helper utilities for building RAG prompts and formatting outputs.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

from cam_agent.utils.sources import make_label, short_title


def add_titles_to_cites(
    answer: str,
    id_to_title: Dict[int, str],
    id_to_passage: Dict[int, str],
) -> str:
    """Replace bare `(see [n])` references with informative labels."""

    def repl(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        title = id_to_title.get(idx)
        passage = id_to_passage.get(idx, "")
        if not title:
            return match.group(0)
        label = make_label(title, passage)
        return f"({label}; see [{idx}])"

    return re.sub(r"\(see\s*\[(\d+)\]\)", repl, answer)


def build_ctx_and_maps(hits: Iterable[Dict]) -> Tuple[str, Dict[int, str], Dict[int, str]]:
    """Create context block plus lookup maps from retrieved hits."""
    lines: List[str] = []
    id_to_title: Dict[int, str] = {}
    id_to_passage: Dict[int, str] = {}
    for idx, chunk in enumerate(hits, start=1):
        title = short_title(chunk["path"])
        passage = (chunk.get("text") or "").strip()
        id_to_title[idx] = title
        id_to_passage[idx] = passage
        lines.append(f"[{idx}] SOURCE: {title}\n{passage}\n")
    return "\n".join(lines), id_to_title, id_to_passage


def build_legend(hits: Iterable[Dict]) -> str:
    """Human-friendly legend showing retrieved sources and clause labels."""
    items: List[str] = []
    for idx, chunk in enumerate(hits, start=1):
        title = short_title(chunk["path"])
        passage = chunk.get("text") or ""
        label = make_label(title, passage)
        items.append(f"[{idx}] {label}")
    return " | ".join(items) if items else ""


def build_prompt(question: str, ctx_block: str) -> str:
    """Construct the retrieval-augmented prompt with explicit instructions."""
    return f"""
You are a registered-psychologist style assistant answering a client's question in AUSTRALIA.

USE ONLY the Context. If the Context is insufficient, say you’re unsure and what would help.

CITATION STYLE (MANDATORY):
- In the body text, write the SOURCE NAME + CLAUSE/SECTION, then keep the bracketed number.
  Examples:
  • "APS Code of Ethics — Standard A.5.2 (see [1])"
  • "Privacy Act 1988 (Cth) — APP 6.2(b) (see [4])"
  • "Health Practitioner Regulation National Law Act 2009 — s 150 (see [8])"
- Put the cite at the end of the sentence/bullet. Use multiple cites if needed.

PRIORITIES:
1) Use AUSTRALIAN sources (APS Code, Ahpra/National Boards Regulatory Guide, Privacy Act/APPs, National Law).
2) Enumerate limits to confidentiality / legal exceptions precisely (APP 6, Privacy Act s 16A, National Law where relevant).
3) Be clear, client-friendly, and concise.

Question:
{question}

Context (numbered sources — each begins with SOURCE: <title>):
{ctx_block}

Answer:
""".strip()


__all__ = ["add_titles_to_cites", "build_ctx_and_maps", "build_legend", "build_prompt"]

