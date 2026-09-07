"""RAG citation verify mode — treat answer + citations[] as claim/evidence.

Primary business use case: gate whether retrieved citations actually support
a generated answer before showing it to a user or letting an agent act on it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.claim import Claim
from app.models.evidence import Evidence


class Citation(BaseModel):
    """One retrieved citation / chunk used to ground an answer."""

    text: str = Field(min_length=10, max_length=1000)
    source: str = Field(default="citation", min_length=1, max_length=100)
    reliability: float = Field(default=0.8, ge=0.0, le=1.0)
    citation_id: str | None = None
    url: str | None = None


class RagVerifyInput(BaseModel):
    """Answer + citations payload for citation-aware verification."""

    answer: str = Field(min_length=10, max_length=500)
    citations: list[Citation] = Field(min_length=1)
    source_url: str | None = None


def citations_to_evidence(citations: list[Citation]) -> list[Evidence]:
    """Map citations to Evidence, preserving source labels for the dossier."""
    evidence: list[Evidence] = []
    for i, c in enumerate(citations):
        label = c.source
        if c.citation_id:
            label = f"{c.source}#{c.citation_id}"
        elif len(citations) > 1 and c.source == "citation":
            label = f"citation[{i}]"
        evidence.append(
            Evidence(text=c.text, source=label[:100], reliability=c.reliability)
        )
    return evidence


def rag_to_claim_evidence(payload: RagVerifyInput) -> tuple[Claim, list[Evidence]]:
    """Convert answer+citations into the standard claim/evidence pair."""
    claim = Claim(text=payload.answer, source_url=payload.source_url)
    return claim, citations_to_evidence(payload.citations)


def citation_aware_reasons(
    result_reasons: list[str],
    citations: list[Citation],
    *,
    supporting_sources: list[str],
    contradicting_sources: list[str],
) -> list[str]:
    """Prepend citation-aware summary reasons for RAG dossiers."""
    reasons: list[str] = [
        f"RAG citation mode: answer checked against {len(citations)} citation(s)."
    ]
    if supporting_sources:
        reasons.append(
            "Citations supporting the answer: " + ", ".join(supporting_sources) + "."
        )
    else:
        reasons.append("No citation clearly supported the answer.")
    if contradicting_sources:
        reasons.append(
            "Citations contradicting the answer: "
            + ", ".join(contradicting_sources)
            + "."
        )
    # Keep original engine reasons after the citation summary.
    reasons.extend(result_reasons)
    return reasons


def annotate_rag_meta(
    meta: dict[str, Any],
    citations: list[Citation],
) -> dict[str, Any]:
    out = dict(meta)
    out["mode"] = "rag_citation"
    out["citation_count"] = len(citations)
    out["citation_ids"] = [c.citation_id for c in citations if c.citation_id]
    return out
