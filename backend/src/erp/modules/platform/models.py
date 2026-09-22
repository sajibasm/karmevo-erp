"""Platform tables inside each tenant database."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy import text as sql
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
