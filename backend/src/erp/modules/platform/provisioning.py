"""Create, migrate and upgrade tenant databases (ADR-0002).

Operator tooling (python -m erp.cli) that runs as erp_owner. The API
never uses it.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self
from uuid import UUID

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Connection, create_engine, text
from sqlalchemy.pool import NullPool

from erp.core.db import Database, DbCredentials, SqlIdentifier, TenantDbLocator
from erp.core.errors import NotFoundError
from erp.modules.platform.registry_models import Tenant
from erp.modules.platform.registry_repository import TenantRepository


class MissingTenantDatabaseError(RuntimeError):
    """A previously migrated tenant database is gone.

    Restore it from backup; never re-create it empty.
    """


@dataclass(frozen=True)
class MigrationOutcome:
    tenant_id: UUID
    revision: str | None
    error: str | None


class TenantDatabaseAdmin:
    """Server-level operations on tenant databases, as erp_owner."""

    DATABASE_EXISTS = text("select 1 from pg_database where datname = :name")
    BIND_OWNER = text(
        'INSERT INTO platform."DatabaseOwners" ("tenantId") '
        'VALUES (:tenant_id) ON CONFLICT ("isSingleton") DO NOTHING'
    )
    BOUND_OWNER = text('SELECT "tenantId" FROM platform."DatabaseOwners"')

    def __init__(
        self,
        locator: TenantDbLocator,
        *,
        owner: DbCredentials,
        runtime_roles: Sequence[str],
    ) -> None:
        self._locator = locator
        self._owner = DbCredentials(SqlIdentifier.safe(owner.user), owner.password)
        self._runtime_roles = [SqlIdentifier.safe(r) for r in runtime_roles]

    def url(self, server: str, database: str) -> URL:
        name = SqlIdentifier.safe(database)
        return self._locator.url(server, name, self._owner)

    def exists(self, server: str, database: str) -> bool:
        with self._server_connection(server) as conn:
            found = conn.scalar(self.DATABASE_EXISTS, {"name": database})
        return found is not None

    def create(self, server: str, database: str) -> None:
        name = SqlIdentifier.safe(database)
        with self._server_connection(server) as conn:
            conn.execute(text(f'CREATE DATABASE "{name}" OWNER "{self._owner.user}"'))

    def grant_connect(self, server: str, database: str) -> None:
        name = SqlIdentifier.safe(database)
        with self._server_connection(server) as conn:
            conn.execute(text(f'REVOKE CONNECT ON DATABASE "{name}" FROM PUBLIC'))
            for role in self._runtime_roles:
                conn.execute(text(f'GRANT CONNECT ON DATABASE "{name}" TO "{role}"'))

    def bind_owner(self, server: str, database: str, tenant_id: UUID) -> None:
        """Record the owning tenant in the database's DatabaseOwners."""
        engine = create_engine(self.url(server, database), poolclass=NullPool)
        try:
            with engine.begin() as conn:
                conn.execute(self.BIND_OWNER, {"tenant_id": tenant_id})
                bound_to = conn.scalar(self.BOUND_OWNER)
        finally:
            engine.dispose()
        if bound_to != tenant_id:
            raise RuntimeError(f"{database} already belongs to {bound_to}")

    @contextmanager
    def _server_connection(self, server: str) -> Iterator[Connection]:
        engine = create_engine(
            self._locator.url(server, "postgres", self._owner),
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )
        try:
            with engine.connect() as conn:
                yield conn
        finally:
            engine.dispose()


class TenantMigrator:
    """Run the tenant Alembic tree against one database."""

    def __init__(self, alembic_ini: Path) -> None:
        self._alembic_ini = alembic_ini

    def head_revision(self) -> str:
        return ScriptDirectory.from_config(self._config()).get_current_head()

    def upgrade(self, url: URL) -> str:
        config = self._config()
        # configparser treats % as interpolation; escaped passwords may
        # contain it.
        rendered = url.render_as_string(hide_password=False)
        config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))
        command.upgrade(config, "head")
        return self.current_revision(url)

    @staticmethod
    def current_revision(url: URL) -> str:
        engine = create_engine(url, poolclass=NullPool)
        try:
            with engine.connect() as conn:
                return MigrationContext.configure(conn).get_current_revision()
        finally:
            engine.dispose()

    def _config(self) -> Config:
        return Config(str(self._alembic_ini), ini_section="tenant")


class TenantProvisioner:
    """Provision tenant databases and keep them migrated."""

    def __init__(
        self,
        registry: Database,
        locator: TenantDbLocator,
        admin: TenantDatabaseAdmin,
        migrator: TenantMigrator,
        *,
        server: str = "default",
    ) -> None:
        self._registry = registry
        self._locator = locator
        self._admin = admin
        self._migrator = migrator
        self._server = server

    @classmethod
    def create(
        cls,
        registry: Database,
        locator: TenantDbLocator,
        *,
        owner: DbCredentials,
        runtime_roles: Sequence[str],
        alembic_ini: Path,
        server: str = "default",
    ) -> Self:
        admin = TenantDatabaseAdmin(locator, owner=owner, runtime_roles=runtime_roles)
        migrator = TenantMigrator(alembic_ini)
        return cls(registry, locator, admin, migrator, server=server)

    def head_revision(self) -> str:
        return self._migrator.head_revision()

    def provision(self, *, account_number: str, tenant_name: str) -> UUID:
        with self._registry.platform_session() as s:
            tenants = TenantRepository(s)
            tenant_id = tenants.new_id()
            tenants.add(
                Tenant(
                    tenant_id=tenant_id,
                    account_number=account_number,
                    tenant_name=tenant_name,
                    database_server=self._server,
                    database_name=self._locator.database_name(tenant_id),
                )
            )
        self.complete(tenant_id)
        return tenant_id

    def complete(self, tenant_id: UUID) -> str:
        """Create, migrate and bind the database; safe to re-run."""
        with self._registry.platform_session() as s:
            tenant = TenantRepository(s).get(tenant_id)
        if tenant is None:
            raise NotFoundError("unknown tenant", code="TENANT_NOT_FOUND")
        server, database = tenant.database_server, tenant.database_name
        try:
            if not self._admin.exists(server, database):
                if tenant.schema_revision is not None:
                    raise MissingTenantDatabaseError(
                        f"{database} is missing; restore it from backup instead of re-creating it"
                    )
                self._admin.create(server, database)
            self._admin.grant_connect(server, database)
            revision = self._migrator.upgrade(self._admin.url(server, database))
            self._admin.bind_owner(server, database, tenant_id)
        except Exception as exc:
            self._record(tenant_id, status="failed", error=exc)
            raise
        self._record(tenant_id, status="ready", revision=revision)
        return revision

    def upgrade_all(self) -> list[MigrationOutcome]:
        """Upgrade every ready tenant DB; failures don't stop others."""
        with self._registry.platform_session() as s:
            tenants = TenantRepository(s).with_database_status("ready")
        outcomes = []
        for tenant in tenants:
            try:
                url = self._admin.url(tenant.database_server, tenant.database_name)
                revision = self._migrator.upgrade(url)
            except Exception as exc:
                self._record(tenant.tenant_id, status="failed", error=exc)
                outcomes.append(MigrationOutcome(tenant.tenant_id, None, self._describe(exc)))
            else:
                self._record(tenant.tenant_id, status="ready", revision=revision)
                outcomes.append(MigrationOutcome(tenant.tenant_id, revision, None))
        return outcomes

    def _record(
        self,
        tenant_id: UUID,
        *,
        status: str,
        revision: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        message = self._describe(error) if error else None
        with self._registry.platform_session() as s:
            TenantRepository(s).record_database_state(
                tenant_id, status=status, revision=revision, error=message
            )

    @staticmethod
    def _describe(exc: BaseException) -> str:
        return f"{type(exc).__name__}: {exc}"[:1000]
