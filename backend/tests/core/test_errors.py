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

    return TestClient(app)


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
