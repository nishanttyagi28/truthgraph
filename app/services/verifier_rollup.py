"""Claim rollup and public verify_claim entrypoint."""

from __future__ import annotations

from app.config import (
    DECOMPOSE_CLAIMS,
    KEYWORD_WEIGHT,
    SEMANTIC_WEIGHT,
    USE_SEMANTIC,
)
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.results import (
    ScoreBreakdown,
    SubClaimResult,
    VerificationResult,
)
from app.services.decomposer import decompose_claim
from app.services.verifier_atomic import _verify_atomic


def _rollup(
    parent_text: str,
    sub_results: list[SubClaimResult],
    evidence_items: list[Evidence],
    *,
    use_semantic: bool,
    use_registry: bool,
) -> VerificationResult:
    """Combine per-subclaim verdicts into a parent dossier."""
    if not sub_results:
        atomic, _ = _verify_atomic(
            parent_text,
            evidence_items,
            use_semantic=use_semantic,
            use_registry=use_registry,
        )
        return atomic

    supported = [s for s in sub_results if s.verdict == "supported"]
    contradicted = [s for s in sub_results if s.verdict == "contradicted"]
    insufficient = [s for s in sub_results if s.verdict == "insufficient"]

    reasons: list[str] = [
        f"Decomposed into {len(sub_results)} sub-claim(s): "
        f"{len(supported)} supported, {len(contradicted)} contradicted, "
        f"{len(insufficient)} insufficient."
    ]
    for sub in sub_results:
        reasons.append(f"subclaim [{sub.verdict} @ {sub.confidence}]: {sub.text}")

    if contradicted and not supported:
        verdict = "contradicted"
        confidence = sum(s.confidence for s in contradicted) / len(contradicted)
        reasons.append("All decisive sub-claims were contradicted.")
    elif supported and not contradicted:
        if insufficient and len(insufficient) >= len(supported):
            verdict = "insufficient"
            confidence = 0.5
            reasons.append("Mixed supported/insufficient sub-claims without a clear majority.")
        else:
            verdict = "supported"
            confidence = sum(s.confidence for s in supported) / len(supported)
            reasons.append("All decisive sub-claims were supported.")
    elif supported and contradicted:
        verdict = "insufficient"
        confidence = 0.5
        reasons.append("Sub-claims disagree (both support and contradiction present).")
    else:
        verdict = "insufficient"
        confidence = 0.0
        reasons.append("No sub-claim had decisive relevant evidence.")

    confidence = round(min(confidence, 1.0), 3)

    # Aggregate evidence bags and keywords from atomic passes.
    supporting: list[Evidence] = []
    contradicting: list[Evidence] = []
    keywords: set[str] = set()
    for sub in sub_results:
        keywords.update(sub.matched_keywords)

    # Re-run a single atomic pass on the parent for evidence lists (stable UX).
    parent_atomic, _ = _verify_atomic(
        parent_text,
        evidence_items,
        use_semantic=use_semantic,
        use_registry=use_registry,
    )
    supporting = parent_atomic.supporting_evidence
    contradicting = parent_atomic.contradicting_evidence
    keywords.update(parent_atomic.matched_keywords)

    breakdown = ScoreBreakdown(
        support_score=parent_atomic.breakdown.support_score if parent_atomic.breakdown else 0.0,
        contradiction_score=(
            parent_atomic.breakdown.contradiction_score if parent_atomic.breakdown else 0.0
        ),
        scoring_mode="hybrid" if use_semantic else "keyword",
        keyword_weight=KEYWORD_WEIGHT if use_semantic else 1.0,
        semantic_weight=SEMANTIC_WEIGHT if use_semantic else 0.0,
        relevant_evidence_count=(
            parent_atomic.breakdown.relevant_evidence_count if parent_atomic.breakdown else 0
        ),
        subclaim_count=len(sub_results),
    )

    return VerificationResult(
        claim=parent_text,
        verdict=verdict,
        confidence=confidence,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        matched_keywords=sorted(keywords),
        reasons=reasons,
        subclaims=sub_results,
        breakdown=breakdown,
        meta={
            "use_semantic": use_semantic,
            "use_registry": use_registry,
            "decomposed": True,
        },
    )


def verify_claim(
    claim: Claim,
    evidence_items: list[Evidence],
    *,
    use_semantic: bool | None = None,
    use_registry: bool = False,
    decompose: bool | None = None,
) -> VerificationResult:
    """Verify a claim against evidence.

    Defaults preserve the deterministic keyword-only path. Semantic similarity
    and decomposition can be enabled per call or via environment flags.
    """
    semantic = USE_SEMANTIC if use_semantic is None else use_semantic
    do_decompose = DECOMPOSE_CLAIMS if decompose is None else decompose

    if do_decompose:
        parts = decompose_claim(claim.text)
        if len(parts) > 1:
            sub_results: list[SubClaimResult] = []
            for part in parts:
                atomic, reasons = _verify_atomic(
                    part,
                    evidence_items,
                    use_semantic=semantic,
                    use_registry=use_registry,
                )
                sub_results.append(
                    SubClaimResult(
                        text=part,
                        verdict=atomic.verdict,
                        confidence=atomic.confidence,
                        matched_keywords=atomic.matched_keywords,
                        reasons=reasons,
                    )
                )
            return _rollup(
                claim.text,
                sub_results,
                evidence_items,
                use_semantic=semantic,
                use_registry=use_registry,
            )

    result, _ = _verify_atomic(
        claim.text,
        evidence_items,
        use_semantic=semantic,
        use_registry=use_registry,
    )
    # Mirror single claim as one subclaim for uniform dossier shape when asked.
    result.subclaims = [
        SubClaimResult(
            text=claim.text,
            verdict=result.verdict,
            confidence=result.confidence,
            matched_keywords=result.matched_keywords,
            reasons=list(result.reasons),
        )
    ]
    if result.breakdown:
        result.breakdown.subclaim_count = 1
    result.meta["decomposed"] = False
    return result
