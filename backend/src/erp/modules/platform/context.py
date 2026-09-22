from dataclasses import dataclass
from typing import Annotated, Self
from uuid import UUID

from fastapi import Depends

from erp.core.db import Database
from erp.core.deps import RequestState
from erp.core.errors import DomainError, ForbiddenError
from erp.core.security import VerifiedToken
from erp.modules.platform.registry_repository import (
    IdentityRepository,
    MembershipRepository,
)


@dataclass(frozen=True)
class RequestContext:
    tenant_id: UUID
    membership_id: UUID
    identity_id: UUID


@dataclass(frozen=True)
class TenantChoice:
    tenant_id: UUID
    account_number: str
    tenant_name: str


@dataclass(frozen=True)
class ActiveMembership:
    membership_id: UUID
    tenant: TenantChoice


class TenantSelectionRequiredError(DomainError):
    status = 400
    code = "TENANT_SELECTION_REQUIRED"
    title = "Tenant selection required"


class TenantContextService:
    """Select a request's tenant from verified memberships (TEN-03)."""

    def __init__(self, registry: Database) -> None:
        self._registry = registry

    @classmethod
    def provide(cls, registry: Annotated[Database, Depends(RequestState.registry)]) -> Self:
        return cls(registry)

    def choices(self, token: VerifiedToken) -> list[TenantChoice]:
        _, memberships = self._active_memberships(token)
        return [m.tenant for m in memberships]

    def resolve(self, token: VerifiedToken, requested_tenant_id: UUID | None) -> RequestContext:
        identity_id, memberships = self._active_memberships(token)
        chosen = self._choose(memberships, requested_tenant_id)
        return RequestContext(chosen.tenant.tenant_id, chosen.membership_id, identity_id)

    @staticmethod
    def _choose(memberships: list[ActiveMembership], requested: UUID | None) -> ActiveMembership:
        if requested is None:
            if not memberships:
                raise ForbiddenError("no active membership", code="TENANT_ACCESS_DENIED")
            if len(memberships) > 1:
                raise TenantSelectionRequiredError("select a tenant with the X-Tenant-Id header")
            return memberships[0]
        for membership in memberships:
            if membership.tenant.tenant_id == requested:
                return membership
        raise ForbiddenError(
            "no active membership for the requested tenant",
            code="TENANT_ACCESS_DENIED",
        )

    def _active_memberships(self, token: VerifiedToken) -> tuple[UUID, list[ActiveMembership]]:
        with self._registry.platform_session() as s:
            identity_id = IdentityRepository(s).find_id(token.issuer, token.subject)
        if identity_id is None:
            raise ForbiddenError("identity is not provisioned", code="IDENTITY_NOT_PROVISIONED")
        with self._registry.platform_session(identity_id=identity_id) as s:
            rows = MembershipRepository(s).active_staff_tenants()
        memberships = [
            ActiveMembership(
                row.membership_id,
                TenantChoice(row.tenant_id, row.account_number, row.tenant_name),
            )
            for row in rows
        ]
        return identity_id, memberships
