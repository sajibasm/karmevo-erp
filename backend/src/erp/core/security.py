from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

import jwt

from erp.core.errors import UnauthenticatedError

KeyResolver = Callable[[str], Any]


@dataclass(frozen=True)
class VerifiedToken:
    issuer: str
    subject: str
    claims: dict[str, Any] = field(repr=False)


class TokenVerifier:
    """Validate Keycloak access tokens (IAM-02).

    Checks signature, pinned issuer, audience and expiry. In
    production the key resolver reads the realm JWKS by `kid`, so
    signing-key rotation needs no restart.
    """

    REQUIRED_CLAIMS: ClassVar[list[str]] = [
        "exp",
        "iat",
        "iss",
        "aud",
        "sub",
    ]

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: list[str],
        key_resolver: KeyResolver,
        leeway_seconds: int = 30,
    ) -> None:
        if not algorithms or any(a.lower() == "none" or a.startswith("HS") for a in algorithms):
            raise ValueError("only asymmetric signing algorithms are allowed")
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)
        self._key_resolver = key_resolver
        self._leeway = leeway_seconds

    def verify(self, token: str) -> VerifiedToken:
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
            if algorithm not in self._algorithms:
                raise UnauthenticatedError("token algorithm is not allowed")
            claims = jwt.decode(
                token,
                self._key_resolver(token),
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": self.REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError("invalid access token") from exc
        return VerifiedToken(
            issuer=claims["iss"],
            subject=claims["sub"],
            claims=claims,
        )


class JwksKeyResolver:
    """Resolve a token's verification key from a JWKS URL by `kid`."""

    def __init__(self, jwks_url: str) -> None:
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def __call__(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key
