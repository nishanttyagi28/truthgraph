from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body


def test_verify_endpoint():
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
    result = response.json()

    assert response.status_code == 200
    assert result["verdict"] == "supported"
    assert result["confidence"] == 0.95
    assert "reasons" in result
    assert "matched_keywords" in result


def test_verify_batch_endpoint():
    payload = {
        "items": [
            {
                "claim": {"text": "Earth has one natural satellite."},
                "evidence": [
                    {
                        "text": "Earth has one natural satellite called the Moon.",
                        "source": "NASA",
                        "reliability": 0.95,
                    }
                ],
                "decompose": False,
            },
            {
                "claim": {"text": "Earth has one natural satellite."},
                "evidence": [
                    {
                        "text": "Python is a programming language used worldwide today.",
                        "source": "Book",
                        "reliability": 0.9,
                    }
                ],
                "decompose": False,
            },
        ]
    }
    response = client.post("/verify/batch", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["results"][0]["verdict"] == "supported"
    assert body["results"][1]["verdict"] == "insufficient"


def test_sources_endpoint():
    response = client.get("/sources")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] > 0
    assert "nasa" in body["sources"]


def test_history_endpoint_default_off():
    response = client.get("/history")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
