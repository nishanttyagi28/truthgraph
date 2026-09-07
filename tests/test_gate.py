"""Tests for agent gate helper + decorator."""

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.gate import GateBlockedError, gate, gated, gate_context, require_allow

client = TestClient(app)


def _moon_claim():
    return Claim(text="Earth has one natural satellite.")


def _moon_evidence(reliability=0.98):
    return [
        Evidence(
            text="NASA confirms that Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=reliability,
        )
    ]


def test_gate_allow():
    gr = gate(_moon_claim(), _moon_evidence(), policy_id="agent_tool_gate", decompose=False)
    assert gr.decision == "ALLOW"
    assert gr.verdict == "supported"
    assert gr.policy_id == "agent_tool_gate"
    assert gr.allowed()


def test_gate_block_contradiction():
    evidence = [
        Evidence(
            text="Earth does not have one natural satellite according to this survey note.",
            source="Anon",
            reliability=0.9,
        )
    ]
    gr = gate(_moon_claim(), evidence, policy_id="agent_tool_gate", decompose=False)
    assert gr.decision == "BLOCK"
    assert gr.blocked()


def test_gate_string_claim():
    gr = gate(
        "Earth has one natural satellite.",
        _moon_evidence(),
        decompose=False,
    )
    assert gr.decision == "ALLOW"


def test_require_allow_raises():
    evidence = [
        Evidence(
            text="Python is a programming language used worldwide today by engineers.",
            source="Book",
            reliability=0.9,
        )
    ]
    gr = gate(_moon_claim(), evidence, decompose=False)
    assert gr.decision == "REVIEW"
    with pytest.raises(GateBlockedError):
        require_allow(gr)


def test_gate_context_allows():
    with gate_context(_moon_claim(), _moon_evidence(), decompose=False) as gr:
        assert gr.decision == "ALLOW"


def test_gate_decorator():
    @gated(decompose=False, policy_id="agent_tool_gate")
    def act(*, claim, evidence, _gate_result=None):
        return _gate_result.decision

    assert act(claim=_moon_claim(), evidence=_moon_evidence()) == "ALLOW"


def test_gate_rag_mode():
    gr = gate(
        answer="Earth has one natural satellite called the Moon.",
        citations=[
            {
                "text": "Astronomers note Earth has one natural satellite known as the Moon.",
                "source": "Textbook",
                "reliability": 0.92,
            }
        ],
        policy_id="rag_citation_gate",
        decompose=False,
    )
    assert gr.decision == "ALLOW"
    assert gr.verification.meta.get("mode") == "rag_citation"
    assert any("RAG citation mode" in r for r in gr.reasons)


def test_api_gate_endpoint():
    payload = {
        "claim": {"text": "Earth has one natural satellite."},
        "evidence": [
            {
                "text": "NASA confirms that Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.98,
            }
        ],
        "policy_id": "agent_tool_gate",
        "decompose": False,
        "include_audit": True,
    }
    response = client.post("/gate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["verdict"] == "supported"
    assert body["policy_id"] == "agent_tool_gate"
    assert body["audit"] is not None
    assert "TruthGraph Audit" in (body["audit_markdown"] or "")


def test_api_gate_rag():
    payload = {
        "answer": "Earth has one natural satellite called the Moon.",
        "citations": [
            {
                "text": "Astronomers note Earth has one natural satellite known as the Moon.",
                "source": "Textbook",
                "reliability": 0.92,
                "citation_id": "c1",
            }
        ],
        "policy_id": "rag_citation_gate",
        "decompose": False,
    }
    response = client.post("/gate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["verification"]["meta"]["mode"] == "rag_citation"


def test_api_policies():
    response = client.get("/policies")
    assert response.status_code == 200
    body = response.json()
    assert "agent_tool_gate" in body["presets"]


def test_verify_still_works():
    """Regression: /verify contract unbroken."""
    payload = {
        "claim": {"text": "Earth has one natural satellite."},
        "evidence": [
            {
                "text": "Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.95,
            }
        ],
        "decompose": False,
    }
    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["verdict"] == "supported"
    assert result["confidence"] == 0.95
