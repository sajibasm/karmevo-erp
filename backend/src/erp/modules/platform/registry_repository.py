"""Repositories for registry tables (ADR-0011)."""

from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from erp.modules.platform.registry_models import (
    Identity,
    Membership,
    Tenant,
    TenantModule,
)


class TenantRepository:
    """All queries on registry "Tenants"."""

    NEW_ID = text("select uuidv7()")

    def __init__(self, session: Session) -> None:
        self._session = session

    def new_id(self) -> UUID:
        return self._session.scalar(self.NEW_ID)

    def add(self, tenant: Tenant) -> None:
        self._session.add(tenant)
        self._session.flush()

    def get(self, tenant_id: UUID) -> Tenant | None:
        return self._session.get(Tenant, tenant_id)

    def lock(self, tenant_id: UUID) -> bool:
        """Row-lock a tenant until the transaction ends."""
        row = self._session.execute(
            select(Tenant.tenant_id).where(Tenant.tenant_id == tenant_id).with_for_update()
        ).first()
        return row is not None

    def with_database_status(self, status: str) -> list[Tenant]:
        return list(
            self._session.scalars(
                select(Tenant).where(Tenant.database_status == status).order_by(Tenant.tenant_id)
            )
        )

    def active_ids(self) -> list[UUID]:
        return list(
            self._session.scalars(
                select(Tenant.tenant_id)
                .where(
                    Tenant.tenant_status == "active",
                    Tenant.database_status == "ready",
                )
                .order_by(Tenant.tenant_id)
            )
        )

    def record_database_state(
        self,
        tenant_id: UUID,
        *,
        status: str,
        revision: str | None = None,
        error: str | None = None,
    ) -> None:
        values: dict[object, object] = {
            Tenant.database_status: status,
            Tenant.last_migration_error: error,
        }
        if revision is not None:
            values[Tenant.schema_revision] = revision
        self._session.execute(update(Tenant).where(Tenant.tenant_id == tenant_id).values(values))


class IdentityRepository:
    """All queries on registry "Identities"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_id(self, issuer: str, subject: str) -> UUID | None:
        return self._session.scalar(
            select(Identity.identity_id).where(
                Identity.issuer == issuer, Identity.subject == subject
            )
        )


class MembershipRepository:
    """All queries on registry "Memberships".

    Reads rely on the identity context of the session (RLS).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_staff_tenants(self) -> list[Row]:
        """Active staff memberships with their tenant's name/number."""
        return list(
            self._session.execute(
                select(
                    Membership.membership_id,
                    Tenant.tenant_id,
                    Tenant.account_number,
                    Tenant.tenant_name,
                )
                .join(Tenant, Tenant.tenant_id == Membership.tenant_id)
                .where(
                    Membership.membership_kind == "staff",
                    Membership.membership_status == "active",
                    Tenant.tenant_status == "active",
                )
                .order_by(Tenant.account_number)
            )
        )


class TenantModuleRepository:
    """All queries on registry "TenantModules"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enabled_keys(self, tenant_id: UUID) -> set[str]:
        return set(
            self._session.scalars(
                select(TenantModule.module_key).where(
                    TenantModule.tenant_id == tenant_id,
                    TenantModule.is_enabled.is_(True),
                )
            )
        )

    def upsert(self, tenant_id: UUID, key: str, *, is_enabled: bool) -> None:
        statement = (
            insert(TenantModule)
            .values(
                {
                    TenantModule.tenant_id: tenant_id,
                    TenantModule.module_key: key,
                    TenantModule.is_enabled: is_enabled,
                }
            )
            .on_conflict_do_update(
                index_elements=["tenantId", "moduleKey"],
                set_={"isEnabled": is_enabled, "changedAt": func.now()},
            )
        )
        self._session.execute(statement)
