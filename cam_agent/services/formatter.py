"""
Response formatting helpers for CAM.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional, Set

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


APP_PATTERN = re.compile(
    r"\bAPP\s*(?P<major>\d{1,2})(?:\.(?P<minor>\d))?(?:\((?P<letter>[a-z])\))?",
    re.IGNORECASE,
)

SECTION_PATTERN = re.compile(
    r"\b(?:section|s)\s*(?P<number>\d{1,3})(?P<suffix>[A-Za-z]?)"
    r"(?P<subsection>(?:\([\w\d]+\))*)",
    re.IGNORECASE,
)


def sanitize_legal_references(answer: str, retrieval_context: str) -> str:
    """
    Ensure clause references align with retrieved material.

    If a cited APP or legal section is not present in the retrieval context,
    fall back to the closest parent clause or drop it entirely.
    """

    if not answer.strip():
        return answer

    context_refs = _extract_legal_refs(retrieval_context)

    def _replace_app(match: re.Match[str]) -> str:
        major = match.group("major")
        minor = match.group("minor")
        letter = match.group("letter")
        options = []
        if letter and minor:
            options.append((f"app{major}.{minor}({letter})", (major, minor, letter)))
        if minor:
            options.append((f"app{major}.{minor}", (major, minor, None)))
        options.append((f"app{major}", (major, None, None)))

        for key, fmt_args in options:
            if _normalize_ref(key) in context_refs:
                return _format_app_reference(*fmt_args)

        if _normalize_ref(f"app{major}") in context_refs:
            return f"APP {int(major)}"
        return "APP"

    def _replace_section(match: re.Match[str]) -> str:
        number = match.group("number")
        suffix = (match.group("suffix") or "").upper()
        subsection = match.group("subsection") or ""
        raw = f"section{number}{suffix}{subsection}"
        norm = _normalize_ref(raw)

        candidates = [norm]
        if subsection:
            candidates.append(_normalize_ref(f"section{number}{suffix}"))
            if suffix:
                candidates.append(_normalize_ref(f"section{number}"))
        elif suffix:
            candidates.append(_normalize_ref(f"section{number}"))

        for candidate in candidates:
            if candidate in context_refs:
                return _format_section_reference(number, suffix, subsection)

        if _normalize_ref(f"section{number}") in context_refs:
            return f"section {int(number)}"

        return "section"

    sanitized = APP_PATTERN.sub(_replace_app, answer)
    sanitized = SECTION_PATTERN.sub(_replace_section, sanitized)
    return sanitized


def _extract_legal_refs(text: str) -> Set[str]:
    refs: Set[str] = set()
    if not text:
        return refs

    for match in APP_PATTERN.finditer(text):
        major = match.group("major")
        minor = match.group("minor")
        letter = match.group("letter")
        refs.add(_normalize_ref(f"app{major}"))
        if minor:
            refs.add(_normalize_ref(f"app{major}.{minor}"))
        if minor and letter:
            refs.add(_normalize_ref(f"app{major}.{minor}({letter})"))

    for match in SECTION_PATTERN.finditer(text):
        number = match.group("number")
        suffix = (match.group("suffix") or "").upper()
        subsection = match.group("subsection") or ""
        refs.add(_normalize_ref(f"section{number}{suffix}{subsection}"))
        if subsection:
            refs.add(_normalize_ref(f"section{number}{suffix}"))
        if suffix:
            refs.add(_normalize_ref(f"section{number}"))
    return refs


def _normalize_ref(value: str) -> str:
    return re.sub(r"[\s\-]", "", value.strip().lower())


def _format_app_reference(
    major: str,
    minor: Optional[str],
    letter: Optional[str],
) -> str:
    result = f"APP {int(major)}"
    if minor:
        result += f".{minor}"
    if letter:
        result += f"({letter.lower()})"
    return result


def _format_section_reference(
    number: str,
    suffix: str,
    subsection: str,
) -> str:
    parts = ["section", str(int(number))]
    if suffix:
        parts[-1] += suffix.upper()
    result = " ".join(parts)
    if subsection:
        result += subsection
    return result


__all__ = [
    "RetrievalContext",
    "prepare_context",
    "enrich_citations",
    "sanitize_legal_references",
]
