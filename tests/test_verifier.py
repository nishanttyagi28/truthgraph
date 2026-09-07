from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.verifier import classify_evidence, verify_claim


def test_supported_claim():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        )
    ]

    result = verify_claim(claim, evidence, decompose=False)

    assert result.verdict == "supported"
    assert result.confidence == 0.95
    assert len(result.supporting_evidence) == 1
    assert result.reasons
    assert result.breakdown is not None
    assert result.breakdown.scoring_mode == "keyword"


def test_contradicted_claim():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth does not have one natural satellite.",
            source="Incorrect Source",
            reliability=0.80,
        )
    ]

    result = verify_claim(claim, evidence, decompose=False)

    assert result.verdict == "contradicted"
    assert result.confidence == 0.80
    assert len(result.contradicting_evidence) == 1


def test_insufficient_evidence():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Python is a programming language used for software development.",
            source="Programming Book",
            reliability=0.90,
        )
    ]

    result = verify_claim(claim, evidence, decompose=False)

    assert result.verdict == "insufficient"
    assert result.confidence == 0.0


def test_number_contradiction():
    claim = Claim(text="Mars has 2 natural satellites orbiting it.")
    evidence = [
        Evidence(
            text="Mars has 3 natural satellites according to this note.",
            source="Bad Source",
            reliability=0.9,
        )
    ]
    result = verify_claim(claim, evidence, decompose=False)
    assert result.verdict == "contradicted"


def test_classify_irrelevant():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = Evidence(
        text="Bananas are yellow fruits grown in tropical climates worldwide.",
        source="Food",
        reliability=0.5,
    )
    stance = classify_evidence(claim.text, evidence, relevance=0.1)
    assert stance == "irrelevant"


def test_hybrid_semantic_does_not_break_support():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        )
    ]
    result = verify_claim(claim, evidence, use_semantic=True, decompose=False)
    assert result.verdict == "supported"
    assert result.breakdown is not None
    assert result.breakdown.scoring_mode == "hybrid"
    assert result.meta.get("use_semantic") is True


def test_vision_eval_compatible_core_fields():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        )
    ]
    result = verify_claim(claim, evidence, decompose=False)
    data = result.model_dump()
    for key in (
        "claim",
        "verdict",
        "confidence",
        "supporting_evidence",
        "contradicting_evidence",
        "matched_keywords",
    ):
        assert key in data
    assert data["verdict"] in {"supported", "contradicted", "insufficient"}
