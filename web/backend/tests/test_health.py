from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_direct_ready():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["runner"] == "direct"
    assert body["runner_ready"] is True  # direct 永远就绪
