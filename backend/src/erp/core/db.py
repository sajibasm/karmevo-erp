from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """One engine (one physical database) with explicit transactions.

    Tenant and identity context are transaction-local, so a pooled
    connection never carries one request's context into the next; this
    also works with PgBouncer transaction pooling (ADR-0002).
    """

    SET_LOCAL = text("select set_config(:name, :value, true)")

    def __init__(self, url: str | URL, **engine_kwargs: Any) -> None:
        self.engine = create_engine(url, pool_pre_ping=True, **engine_kwargs)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def tenant_session(self, tenant_id: UUID) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._set_local(session, "app.tenant_id", str(tenant_id))
            yield session

    @contextmanager
    def platform_session(self, *, identity_id: UUID | None = None) -> Iterator[Session]:
        """A transaction without tenant context.

        Tenant-owned tables return no rows in it.
        """
        with self._sessions() as session, session.begin():
            if identity_id is not None:
                self._set_local(session, "app.identity_id", str(identity_id))
            yield session

    def dispose(self) -> None:
        self.engine.dispose()

    @classmethod
    def _set_local(cls, session: Session, name: str, value: str) -> None:
        session.execute(cls.SET_LOCAL, {"name": name, "value": value})
