import logging
from http import HTTPStatus
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Error with a stable API `code` (ADR-0006)."""

    status: int = 400
    code: str = "BAD_REQUEST"
    title: str = "Bad request"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class UnauthenticatedError(DomainError):
    status, code, title = 401, "UNAUTHENTICATED", "Authentication required"


class ForbiddenError(DomainError):
    status, code, title = 403, "FORBIDDEN", "Forbidden"


class NotFoundError(DomainError):
    status, code, title = 404, "NOT_FOUND", "Not found"


class ConflictError(DomainError):
    status, code, title = 409, "CONFLICT", "Conflict"


class ServiceUnavailableError(DomainError):
    status, code, title = 503, "SERVICE_UNAVAILABLE", "Service unavailable"


class Problem:
    """RFC 9457 problem+json responses (ADR-0006)."""

    MEDIA_TYPE = "application/problem+json"

    @classmethod
    def response(
        cls,
        status: int,
        code: str,
        title: str,
        detail: str,
        errors: list[dict[str, Any]] | None = None,
    ) -> JSONResponse:
        body: dict[str, Any] = {
            "type": "about:blank",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
        }
        if errors is not None:
            body["errors"] = errors
        return JSONResponse(body, status_code=status, media_type=cls.MEDIA_TYPE)


class ErrorHandlers:
    """Register the problem+json exception handlers on an app."""

    # Status codes whose default reason phrase makes a poor `code`
    # (spaces, punctuation); the rest fall back to `HTTP_<status>`.
    STATUS_CODES: ClassVar[dict[int, str]] = {
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }

    @classmethod
    def install(cls, app: FastAPI) -> None:
        app.add_exception_handler(DomainError, cls.domain_error)
        app.add_exception_handler(RequestValidationError, cls.validation_error)
        app.add_exception_handler(StarletteHTTPException, cls.http_exception)
        app.add_exception_handler(Exception, cls.unhandled_error)

    @staticmethod
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        response = Problem.response(exc.status, exc.code, exc.title, exc.detail)
        if exc.status == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @staticmethod
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        return Problem.response(
            422,
            "VALIDATION_FAILED",
            "Validation failed",
            "Request is invalid",
            errors,
        )

    @classmethod
    async def http_exception(cls, _: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Starlette's own 404/405/etc as problem+json (ADR-0006)."""
        code = cls.STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        title = HTTPStatus(exc.status_code).phrase
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        response = Problem.response(exc.status_code, code, title, detail)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @staticmethod
    async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
        """Last resort: never leak internals (ADR-0006)."""
        logger.error("unhandled exception", exc_info=exc)
        return Problem.response(
            500,
            "INTERNAL_ERROR",
            "Internal Server Error",
            "An unexpected error occurred",
        )
