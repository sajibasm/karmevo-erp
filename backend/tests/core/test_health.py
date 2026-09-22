from fastapi.testclient import TestClient

from erp.app import ApplicationFactory


def test_healthz_returns_ok():
    client = TestClient(ApplicationFactory().build())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
