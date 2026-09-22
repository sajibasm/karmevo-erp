from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from erp.core.db import Database
from erp.core.errors import UnauthenticatedError
from erp.core.security import TokenVerifier, VerifiedToken

BEARER = HTTPBearer(auto_error=False)


class RequestState:
    """Accessors for objects the app factory put on app.state."""

    @staticmethod
    def registry(request: Request) -> Database:
        return request.app.state.registry

    @staticmethod
    def verifier(request: Request) -> TokenVerifier:
        return request.app.state.verifier


class Authentication:
    """Bearer-token authentication (IAM-02)."""

    @staticmethod
    def current_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)],
        verifier: Annotated[TokenVerifier, Depends(RequestState.verifier)],
    ) -> VerifiedToken:
        if credentials is None:
            raise UnauthenticatedError("missing bearer token")
        return verifier.verify(credentials.credentials)
