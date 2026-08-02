from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.verifier import verify_claim


def test_supported_claim():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        )
    ]

    result = verify_claim(claim, evidence)

    assert result.verdict == "supported"
    assert result.confidence == 0.95
    assert len(result.supporting_evidence) == 1


def test_contradicted_claim():
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth does not have one natural satellite.",
            source="Incorrect Source",
            reliability=0.80,
        )
    ]

    result = verify_claim(claim, evidence)

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

    result = verify_claim(claim, evidence)

    assert result.verdict == "insufficient"
    assert result.confidence == 0.0
    