import sqlalchemy as sa
from alembic import context
from sqlalchemy import MetaData, create_engine, pool


class AlembicEnvironment:
    """Run one Alembic environment for a metadata set and URL."""

    def __init__(self, metadata: MetaData, url: str) -> None:
        self._metadata = metadata
        self._url = url

    def run(self) -> None:
        if context.is_offline_mode():
            self._run_offline()
        else:
            self._run_online()

    def _run_offline(self) -> None:
        context.configure(
            url=self._url,
            target_metadata=self._metadata,
            literal_binds=True,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    def _run_online(self) -> None:
        engine = create_engine(self._url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=self._metadata,
                include_schemas=True,
            )
            with context.begin_transaction():
                context.run_migrations()


class MigrationColumns:
    """sa.Column factories for migrations, named per ADR-0010."""

    @staticmethod
    def uuid(column: str) -> sa.Column:
        return sa.Column(column, sa.Uuid(), nullable=False, server_default=sa.text("uuidv7()"))

    @staticmethod
    def timestamp(column: str) -> sa.Column:
        return sa.Column(
            column,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )

    @classmethod
    def created_at(cls) -> sa.Column:
        return cls.timestamp("createdAt")

    @staticmethod
    def registry_tenant_id(table: str) -> sa.Column:
        """FK column "tenantId" to registry "Tenants"."""
        return sa.Column(
            "tenantId",
            sa.Uuid(),
            sa.ForeignKey("registry.Tenants.tenantId", name=f"fk_{table}_tenantId_Tenants"),
            nullable=False,
        )

    @staticmethod
    def owner_tenant_id(table: str) -> sa.Column:
        """FK column "tenantId" to platform "DatabaseOwners"."""
        return sa.Column(
            "tenantId",
            sa.Uuid(),
            sa.ForeignKey(
                "platform.DatabaseOwners.tenantId",
                name=f"fk_{table}_tenantId_DatabaseOwners",
            ),
            nullable=False,
        )
