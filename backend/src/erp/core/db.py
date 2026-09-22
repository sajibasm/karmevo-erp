import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar
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


class SqlIdentifier:
    """Validate identifiers that cannot be bound as parameters."""

    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]{0,62}")

    @classmethod
    def safe(cls, value: str) -> str:
        """Allow only lowercase names (databases, roles, prefixes)."""
        if not cls.PATTERN.fullmatch(value):
            raise ValueError(f"unsafe SQL identifier {value!r}")
        return value


@dataclass(frozen=True)
class DbCredentials:
    user: str
    password: str = field(repr=False)


class TenantDbLocator:
    """Name tenant databases and build their URLs (ADR-0002)."""

    def __init__(self, servers: Mapping[str, str], *, database_prefix: str) -> None:
        self._servers = dict(servers)
        self._prefix = SqlIdentifier.safe(database_prefix)

    def database_name(self, tenant_id: UUID) -> str:
        return SqlIdentifier.safe(f"{self._prefix}{tenant_id.hex}")

    def url(self, server: str, database: str, credentials: DbCredentials) -> URL:
        try:
            address = self._servers[server]
        except KeyError:
            raise ValueError(f"unknown tenant database server {server!r}") from None
        host, _, port = address.partition(":")
        return URL.create(
            "postgresql+psycopg",
            username=credentials.user,
            password=credentials.password,
            host=host,
            port=int(port) if port else 5432,
            database=database,
        )
