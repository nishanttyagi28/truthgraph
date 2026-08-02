from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.results import VerificationResult
from app.services.text_analyzer import (
    calculate_relevance,
    contains_negation,
    extract_numbers,
)


MINIMUM_RELEVANCE = 0.3


def classify_evidence(
    claim: Claim,
    evidence: Evidence,
    relevance: float,
) -> str:
    if relevance < MINIMUM_RELEVANCE:
        return "irrelevant"

    claim_numbers = extract_numbers(claim.text)
    evidence_numbers = extract_numbers(evidence.text)

    if claim_numbers and evidence_numbers:
        if claim_numbers.isdisjoint(evidence_numbers):
            return "contradict"

    claim_is_negative = contains_negation(claim.text)
    evidence_is_negative = contains_negation(evidence.text)

    if claim_is_negative != evidence_is_negative:
        return "contradict"

    return "support"


def verify_claim(
    claim: Claim,
    evidence_items: list[Evidence],
) -> VerificationResult:
    supporting = []
    contradicting = []
    all_keywords = set()

    support_score = 0.0
    contradiction_score = 0.0

    for evidence in evidence_items:
        relevance, keywords = calculate_relevance(
            claim.text,
            evidence.text,
        )

        stance = classify_evidence(
            claim,
            evidence,
            relevance,
        )

        weighted_score = relevance * evidence.reliability
        all_keywords.update(keywords)

        if stance == "support":
            supporting.append(evidence)
            support_score += weighted_score

        if stance == "contradict":
            contradicting.append(evidence)
            contradiction_score += weighted_score

    total_score = support_score + contradiction_score
    relevant_count = len(supporting) + len(contradicting)

    if total_score == 0:
        verdict = "insufficient"
        confidence = 0.0
    elif abs(support_score - contradiction_score) < 0.1:
        verdict = "insufficient"
        confidence = 0.5
    elif support_score > contradiction_score:
        verdict = "supported"
        confidence = support_score / relevant_count
    else:
        verdict = "contradicted"
        confidence = contradiction_score / relevant_count

    confidence = round(min(confidence, 1.0), 3)

    return VerificationResult(
        claim=claim.text,
        verdict=verdict,
        confidence=confidence,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        matched_keywords=sorted(all_keywords),
    )