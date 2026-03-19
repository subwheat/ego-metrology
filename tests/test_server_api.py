from fastapi.testclient import TestClient

import server
from ego_metrology import __version__

client = TestClient(server.app)

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "EGO Core Online"
    assert data["version"] == __version__

def test_models_endpoint():
    r = client.get("/models")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert "mistral-7b" in data
    assert "qwen-local" in data

def test_profile_endpoint_success():
    r = client.post(
        "/profile",
        json={
            "model_name": "mistral-7b",
            "prompt_tokens": 1200,
        },
    )
    assert r.status_code == 200
    data = r.json()

    assert data["model"] == "Mistral-7B"
    assert data["prompt_tokens"] == 1200
    assert data["max_context_tokens"] == 8192
    assert "alpha_s" in data
    assert "eta" in data
    assert "r_eta" in data
    assert "tau" in data
    assert "c_dyn" in data
    assert data["calibration_status"] == "heuristic"

def test_profile_endpoint_bad_model():
    r = client.post(
        "/profile",
        json={
            "model_name": "not-a-real-model",
            "prompt_tokens": 1200,
        },
    )
    assert r.status_code in (400, 422)
