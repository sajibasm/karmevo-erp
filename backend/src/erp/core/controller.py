from typing import ClassVar

from fastapi import APIRouter


class Controller:
    """Base for class-based controllers (ADR-0011).

    Subclasses set `prefix` and `tags` and register their bound methods
    as routes in `register_routes()`.
    """

    prefix: ClassVar[str] = ""
    tags: ClassVar[tuple[str, ...]] = ()

    def __init__(self) -> None:
        self.router = APIRouter(prefix=self.prefix, tags=list(self.tags))
        self.register_routes()

    def register_routes(self) -> None:
        raise NotImplementedError
