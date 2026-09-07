"""Verification result models — VisionEval-compatible core fields kept stable."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.evidence import Evidence

Verdict = Literal["supported", "contradicted", "insufficient"]


class SubClaimResult(BaseModel):
    """Per-subclaim verification outcome used in rolled-up dossiers."""

    text: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    """Inspectable scoring breakdown for the deterministic / hybrid path."""

    support_score: float = 0.0
    contradiction_score: float = 0.0
    scoring_mode: Literal["keyword", "hybrid"] = "keyword"
    keyword_weight: float = 1.0
    semantic_weight: float = 0.0
    relevant_evidence_count: int = 0
    subclaim_count: int = 1


class VerificationResult(BaseModel):
    """Structured verdict dossier.

    Core fields (claim, verdict, confidence, supporting_evidence,
    contradicting_evidence, matched_keywords) stay compatible with the
    VisionEval-vendored consumer. Newer fields are additive.
    """

    claim: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[Evidence]
    contradicting_evidence: list[Evidence]
    matched_keywords: list[str]
    # Additive v2 fields (optional for consumers that ignore extras)
    reasons: list[str] = Field(default_factory=list)
    subclaims: list[SubClaimResult] = Field(default_factory=list)
    breakdown: ScoreBreakdown | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
