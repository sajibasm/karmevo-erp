"""Platform tables inside each tenant database."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import Columns, TenantBase

SCHEMA = {"schema": "platform"}


class DatabaseOwner(TenantBase):
    """Exactly one row: the tenant this database belongs to.

    Every "tenantId" column references it, so another tenant's rows
    cannot be stored here, even under a wrong context.
    """

    __tablename__ = "DatabaseOwners"
    __table_args__ = (CheckConstraint('"isSingleton"', name="isSingleton"), SCHEMA)

    is_singleton: Mapped[bool] = mapped_column(
        "isSingleton", primary_key=True, server_default=sql("true")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column("tenantId", unique=True)


class Company(TenantBase):
    __tablename__ = "Companies"
    __table_args__ = (UniqueConstraint("tenantId", "companyId"), SCHEMA)

    company_id: Mapped[uuid.UUID] = Columns.uuid_pk("companyId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    company_name: Mapped[str] = mapped_column("companyName", String(200))
    country_code: Mapped[str] = mapped_column("countryCode", String(2))
    base_currency: Mapped[str] = mapped_column("baseCurrency", String(3))
    time_zone: Mapped[str] = mapped_column("timeZone", String(64))
    created_at: Mapped[datetime] = Columns.created_at()


class Branch(TenantBase):
    __tablename__ = "Branches"
    __table_args__ = (
        UniqueConstraint("tenantId", "branchId"),
        UniqueConstraint("tenantId", "companyId", "branchCode"),
        ForeignKeyConstraint(
            ["tenantId", "companyId"],
            ["platform.Companies.tenantId", "platform.Companies.companyId"],
        ),
        SCHEMA,
    )

    branch_id: Mapped[uuid.UUID] = Columns.uuid_pk("branchId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    company_id: Mapped[uuid.UUID] = mapped_column("companyId")
    branch_code: Mapped[str] = mapped_column("branchCode", String(32))
    branch_name: Mapped[str] = mapped_column("branchName", String(200))
    created_at: Mapped[datetime] = Columns.created_at()


class AuditEvent(TenantBase):
    """Append-only record of sensitive actions (IAM-04).

    The runtime role may only INSERT and SELECT. actorIdentityId points
    to registry "Identities" in another database, so it has no FK.
    """

    __tablename__ = "AuditEvents"
    __table_args__ = (
        UniqueConstraint("tenantId", "auditEventId"),
        CheckConstraint(
            "\"auditOutcome\" in ('success', 'denied', 'failure')",
            name="auditOutcome",
        ),
        SCHEMA,
    )

    audit_event_id: Mapped[uuid.UUID] = Columns.uuid_pk("auditEventId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    occurred_at: Mapped[datetime] = Columns.timestamp("occurredAt")
    actor_identity_id: Mapped[uuid.UUID | None] = mapped_column("actorIdentityId")
    audit_action: Mapped[str] = mapped_column("auditAction", String(100))
    target_type: Mapped[str] = mapped_column("targetType", String(100))
    target_id: Mapped[str | None] = mapped_column("targetId", String(100))
    audit_outcome: Mapped[str] = mapped_column("auditOutcome", String(16))
    audit_reason: Mapped[str | None] = mapped_column("auditReason", Text)
    audit_details: Mapped[dict[str, Any]] = mapped_column(
        "auditDetails", JSONB, server_default=sql("'{}'::jsonb")
    )
