from fastapi.testclient import TestClient

from erp.app import ApplicationFactory


def test_healthz_returns_ok():
    client = TestClient(ApplicationFactory().build())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_checks_the_registry(registry):
    app = ApplicationFactory(registry=registry).build()

    response = TestClient(app).get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_without_registry_is_503():
    response = TestClient(ApplicationFactory().build()).get("/readyz")

    assert response.status_code == 503
