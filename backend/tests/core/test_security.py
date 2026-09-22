import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from support import TEST_ISSUER

from erp.core.errors import UnauthenticatedError
from erp.core.security import TokenVerifier

FOREIGN_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_valid_token_is_accepted(verifier, make_token):
    verified = verifier.verify(make_token("alice"))

    assert (verified.issuer, verified.subject) == (TEST_ISSUER, "alice")


@pytest.mark.parametrize(
    "overrides",
    [
        {"issuer": "https://evil.test/realms/staff"},
        {"audience": "some-other-api"},
        {"expires_in": -120},
        {"subject": None},
        {"algorithm": "HS256", "key": "k" * 64},
        {"key": FOREIGN_KEY},
    ],
    ids=[
        "wrong-issuer",
        "wrong-audience",
        "expired",
        "missing-sub",
        "hmac-alg",
        "foreign-key",
    ],
)
def test_invalid_tokens_are_rejected(verifier, make_token, overrides):
    with pytest.raises(UnauthenticatedError):
        verifier.verify(make_token(**overrides))


def test_garbage_is_rejected(verifier):
    with pytest.raises(UnauthenticatedError):
        verifier.verify("not-a-jwt")


@pytest.mark.parametrize("algorithms", [["HS256"], ["none"], []])
def test_verifier_refuses_symmetric_or_empty_algorithms(algorithms):
    with pytest.raises(ValueError):
        TokenVerifier(
            issuer=TEST_ISSUER,
            audience="erp-api",
            algorithms=algorithms,
            key_resolver=lambda _t: None,
        )
