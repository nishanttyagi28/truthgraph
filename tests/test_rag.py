"""Tests for RAG citation verify mode."""

from fastapi.testclient import TestClient

from app.api import app
from app.services.rag import Citation, RagVerifyInput, citations_to_evidence, rag_to_claim_evidence

client = TestClient(app)


def test_citations_to_evidence():
    cites = [
        Citation(text="Earth has one natural satellite called the Moon.", source="NASA", citation_id="1"),
        Citation(text="Mars has two moons named Phobos and Deimos.", source="Mag"),
    ]
    evidence = citations_to_evidence(cites)
    assert len(evidence) == 2
    assert "NASA#1" in evidence[0].source


def test_rag_to_claim_evidence():
    payload = RagVerifyInput(
        answer="Earth has one natural satellite called the Moon.",
        citations=[
            Citation(
                text="Astronomers note Earth has one natural satellite known as the Moon.",
                source="Textbook",
                reliability=0.9,
            )
        ],
    )
    claim, evidence = rag_to_claim_evidence(payload)
    assert "Earth" in claim.text
    assert len(evidence) == 1


def test_verify_rag_mode_api():
    payload = {
        "answer": "Earth has one natural satellite called the Moon.",
        "citations": [
            {
                "text": "Astronomers note Earth has one natural satellite known as the Moon.",
                "source": "Textbook",
                "reliability": 0.92,
            }
        ],
        "decompose": False,
    }
    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "supported"
    assert body["meta"]["mode"] == "rag_citation"
    assert any("RAG citation mode" in r for r in body["reasons"])


def test_verify_mode_flag_with_claim_evidence():
    payload = {
        "claim": {"text": "Earth has one natural satellite."},
        "evidence": [
            {
                "text": "Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.95,
            }
        ],
        "mode": "rag",
        "decompose": False,
    }
    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["mode"] == "rag_citation"
