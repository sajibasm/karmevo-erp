from fastapi.testclient import TestClient

from erp.app import ApplicationFactory
from erp.core.errors import ConflictError
from erp.shared.money import DecimalStr
from erp.shared.schemas import ApiSchema


class PricePayload(ApiSchema):
    unit_price: DecimalStr


def _client():
    app = ApplicationFactory().build()

    @app.get("/_test/conflict")
    def conflict() -> None:
        raise ConflictError("version mismatch", code="VERSION_CONFLICT")

    @app.post("/_test/echo")
    def echo(payload: PricePayload) -> PricePayload:
        return payload

    @app.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("db password is hunter2")

    return TestClient(app, raise_server_exceptions=False)


def test_domain_error_is_rendered_as_problem_json():
    response = _client().get("/_test/conflict")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "code": "VERSION_CONFLICT",
        "detail": "version mismatch",
    }


def test_decimal_round_trips_as_string_with_camel_case_key():
    response = _client().post("/_test/echo", json={"unitPrice": "10.50"})

    assert response.status_code == 200
    assert response.json() == {"unitPrice": "10.50"}


def test_float_amount_is_rejected_with_validation_code():
    response = _client().post("/_test/echo", json={"unitPrice": 10.5})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert body["errors"][0]["loc"] == ["body", "unitPrice"]


def test_unknown_path_is_404_problem_json():
    response = _client().get("/nope")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["status"] == 404


def test_wrong_method_is_405_problem_json_with_allow_header():
    response = _client().post("/healthz")

    assert response.status_code == 405
    assert response.headers["content-type"] == "application/problem+json"
    assert "GET" in response.headers["allow"]
    body = response.json()
    assert body["code"] == "METHOD_NOT_ALLOWED"


def test_unhandled_exception_is_500_problem_json_without_leaking_detail():
    response = _client().get("/_test/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text
