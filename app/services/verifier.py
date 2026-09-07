"""Claim verification engine with optional decomposition and hybrid scoring."""

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
from app.services.reputation import lookup_reputation
from app.services.semantic import semantic_similarity
from app.services.text_analyzer import (
    calculate_relevance,
    contains_negation,
    extract_numbers,
)

MINIMUM_RELEVANCE = 0.3


def _effective_reliability(evidence: Evidence, use_registry: bool) -> float:
    if use_registry:
        return lookup_reputation(evidence.source, fallback=evidence.reliability)
    return evidence.reliability


def _combined_relevance(
    claim_text: str,
    evidence_text: str,
    *,
    use_semantic: bool,
) -> tuple[float, list[str], float, float]:
    keyword_score, keywords = calculate_relevance(claim_text, evidence_text)
    semantic_score = 0.0
    if use_semantic:
        semantic_score = semantic_similarity(claim_text, evidence_text)
        kw_w = KEYWORD_WEIGHT
        sem_w = SEMANTIC_WEIGHT
        total_w = kw_w + sem_w
        if total_w <= 0:
            combined = keyword_score
        else:
            combined = (kw_w * keyword_score + sem_w * semantic_score) / total_w
        return round(combined, 3), keywords, keyword_score, semantic_score
    return keyword_score, keywords, keyword_score, 0.0


def classify_evidence(
    claim_text: str,
    evidence: Evidence,
    relevance: float,
) -> str:
    if relevance < MINIMUM_RELEVANCE:
        return "irrelevant"

    claim_numbers = extract_numbers(claim_text)
    evidence_numbers = extract_numbers(evidence.text)

    if claim_numbers and evidence_numbers:
        if claim_numbers.isdisjoint(evidence_numbers):
            return "contradict"

    claim_is_negative = contains_negation(claim_text)
    evidence_is_negative = contains_negation(evidence.text)

    if claim_is_negative != evidence_is_negative:
        return "contradict"

    return "support"


def _verify_atomic(
    claim_text: str,
    evidence_items: list[Evidence],
    *,
    use_semantic: bool = False,
    use_registry: bool = False,
) -> tuple[VerificationResult, list[str]]:
    supporting: list[Evidence] = []
    contradicting: list[Evidence] = []
    all_keywords: set[str] = set()
    reasons: list[str] = []

    support_score = 0.0
    contradiction_score = 0.0

    for evidence in evidence_items:
        relevance, keywords, kw_score, sem_score = _combined_relevance(
            claim_text,
            evidence.text,
            use_semantic=use_semantic,
        )
        stance = classify_evidence(claim_text, evidence, relevance)
        reliability = _effective_reliability(evidence, use_registry)
        weighted_score = relevance * reliability
        all_keywords.update(keywords)

        detail = (
            f"source={evidence.source!r} relevance={relevance:.3f}"
            f" (kw={kw_score:.3f}"
            + (f", sem={sem_score:.3f}" if use_semantic else "")
            + f") reliability={reliability:.2f} → {stance}"
        )

        if stance == "support":
            supporting.append(evidence)
            support_score += weighted_score
            reasons.append(f"support: {detail}")
        elif stance == "contradict":
            contradicting.append(evidence)
            contradiction_score += weighted_score
            reasons.append(f"contradict: {detail}")
        else:
            reasons.append(f"irrelevant: {detail}")

    total_score = support_score + contradiction_score
    relevant_count = len(supporting) + len(contradicting)

    if total_score == 0:
        verdict = "insufficient"
        confidence = 0.0
        reasons.append("No relevant evidence above the relevance threshold.")
    elif abs(support_score - contradiction_score) < 0.1:
        verdict = "insufficient"
        confidence = 0.5
        reasons.append("Support and contradiction scores are too close to decide.")
    elif support_score > contradiction_score:
        verdict = "supported"
        confidence = support_score / relevant_count
        reasons.append(
            f"Support score {support_score:.3f} exceeds contradiction {contradiction_score:.3f}."
        )
    else:
        verdict = "contradicted"
        confidence = contradiction_score / relevant_count
        reasons.append(
            f"Contradiction score {contradiction_score:.3f} exceeds support {support_score:.3f}."
        )

    confidence = round(min(confidence, 1.0), 3)
    scoring_mode = "hybrid" if use_semantic else "keyword"
    breakdown = ScoreBreakdown(
        support_score=round(support_score, 3),
        contradiction_score=round(contradiction_score, 3),
        scoring_mode=scoring_mode,
        keyword_weight=KEYWORD_WEIGHT if use_semantic else 1.0,
        semantic_weight=SEMANTIC_WEIGHT if use_semantic else 0.0,
        relevant_evidence_count=relevant_count,
        subclaim_count=1,
    )

    result = VerificationResult(
        claim=claim_text,
        verdict=verdict,
        confidence=confidence,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        matched_keywords=sorted(all_keywords),
        reasons=reasons,
        subclaims=[],
        breakdown=breakdown,
        meta={"use_semantic": use_semantic, "use_registry": use_registry},
    )
    return result, reasons
