from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.decomposer import decompose_claim
from app.services.verifier import verify_claim


def test_decompose_single_sentence_unchanged():
    parts = decompose_claim("Earth has one natural satellite.")
    assert len(parts) == 1
    assert "Earth" in parts[0]


def test_decompose_compound_claim():
    text = "Earth has one natural satellite. Mars has two moons."
    parts = decompose_claim(text)
    assert len(parts) >= 2
    assert any("Earth" in p for p in parts)
    assert any("Mars" in p for p in parts)


def test_verify_with_decomposition_rollup():
    claim = Claim(
        text="Earth has one natural satellite. Mars has two moons."
    )
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        ),
        Evidence(
            text="Mars has two moons named Phobos and Deimos.",
            source="Astronomy Textbook",
            reliability=0.9,
        ),
    ]
    result = verify_claim(claim, evidence, decompose=True)
    assert len(result.subclaims) >= 2
    assert result.verdict == "supported"
    assert result.breakdown is not None
    assert result.breakdown.subclaim_count >= 2


def test_decomposition_conflict_yields_insufficient():
    claim = Claim(
        text="Earth has one natural satellite. Mars has two moons."
    )
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        ),
        Evidence(
            text="Mars does not have two moons according to this post.",
            source="Blog",
            reliability=0.8,
        ),
    ]
    result = verify_claim(claim, evidence, decompose=True)
    assert len(result.subclaims) >= 2
    assert result.verdict == "insufficient"
