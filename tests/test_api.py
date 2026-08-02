from fastapi.testclient import TestClient

from app.api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_verify_endpoint():
    payload = {
        "claim": {
            "text": "Earth has one natural satellite."
        },
        "evidence": [
            {
                "text": "Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.95
            }
        ]
    }

    response = client.post("/verify", json=payload)
    result = response.json()

    assert response.status_code == 200
    assert result["verdict"] == "supported"
    assert result["confidence"] == 0.95