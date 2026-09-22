"""Registry database tables: cross-tenant data only (ADR-0002)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import Columns, RegistryBase

SCHEMA = {"schema": "registry"}


class Tenant(RegistryBase):
    """A client business account and where its database lives."""

    __tablename__ = "Tenants"
    __table_args__ = (
        CheckConstraint("\"tenantStatus\" in ('active', 'suspended')", name="tenantStatus"),
        CheckConstraint(
            "\"databaseStatus\" in ('provisioning', 'ready', 'failed')",
            name="databaseStatus",
        ),
        SCHEMA,
    )

    tenant_id: Mapped[uuid.UUID] = Columns.uuid_pk("tenantId")
    account_number: Mapped[str] = mapped_column("accountNumber", String(32), unique=True)
    tenant_name: Mapped[str] = mapped_column("tenantName", String(200))
    tenant_status: Mapped[str] = mapped_column("tenantStatus", String(16), server_default="active")
    database_server: Mapped[str] = mapped_column(
        "databaseServer", String(64), server_default="default"
    )
    database_name: Mapped[str] = mapped_column("databaseName", String(63), unique=True)
    database_status: Mapped[str] = mapped_column(
        "databaseStatus", String(16), server_default="provisioning"
    )
    schema_revision: Mapped[str | None] = mapped_column("schemaRevision", String(32))
    last_migration_error: Mapped[str | None] = mapped_column("lastMigrationError", String(1000))
    created_at: Mapped[datetime] = Columns.created_at()


class Identity(RegistryBase):
    """A signed-in person or client, keyed by issuer + subject."""

    __tablename__ = "Identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"), SCHEMA)

    identity_id: Mapped[uuid.UUID] = Columns.uuid_pk("identityId")
    issuer: Mapped[str] = mapped_column("issuer", String(500))
    subject: Mapped[str] = mapped_column("subject", String(255))
    created_at: Mapped[datetime] = Columns.created_at()


class Membership(RegistryBase):
    __tablename__ = "Memberships"
    __table_args__ = (
        UniqueConstraint("tenantId", "membershipId"),
        UniqueConstraint("tenantId", "identityId", "membershipKind"),
        CheckConstraint(
            "\"membershipKind\" in ('staff', 'buyer', 'service')",
            name="membershipKind",
        ),
        CheckConstraint(
            "\"membershipStatus\" in ('active', 'suspended')",
            name="membershipStatus",
        ),
        SCHEMA,
    )

    membership_id: Mapped[uuid.UUID] = Columns.uuid_pk("membershipId")
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        "tenantId", ForeignKey("registry.Tenants.tenantId")
    )
    identity_id: Mapped[uuid.UUID] = mapped_column(
        "identityId", ForeignKey("registry.Identities.identityId")
    )
    membership_kind: Mapped[str] = mapped_column(
        "membershipKind", String(16), server_default="staff"
    )
    membership_status: Mapped[str] = mapped_column(
        "membershipStatus", String(16), server_default="active"
    )
    created_at: Mapped[datetime] = Columns.created_at()
