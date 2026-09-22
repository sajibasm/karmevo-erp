"""FastAPI dependencies for tenant-scoped requests (class-based)."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from erp.core.db import Database
from erp.core.deps import Authentication, RequestState
from erp.core.security import VerifiedToken
from erp.modules.platform.context import RequestContext, TenantContextService
from erp.modules.platform.module_state import TenantModules
from erp.modules.platform.tenant_db import TenantDatabaseRouter


class TenantContextProvider:
    """Dependency: the verified tenant context of the request."""

    @staticmethod
    def resolve(
        token: Annotated[VerifiedToken, Depends(Authentication.current_token)],
        registry: Annotated[Database, Depends(RequestState.registry)],
        x_tenant_id: Annotated[UUID | None, Header()] = None,
    ) -> RequestContext:
        return TenantContextService(registry).resolve(token, x_tenant_id)


class TenantDatabaseProvider:
    """Dependency: the selected tenant's own database."""

    @staticmethod
    def resolve(
        context: Annotated[RequestContext, Depends(TenantContextProvider.resolve)],
        request: Request,
    ) -> Database:
        tenant_router: TenantDatabaseRouter = request.app.state.tenant_router
        return tenant_router.for_tenant(context.tenant_id)


class ModuleGuard:
    """Dependency that rejects requests to a disabled module."""

    def __init__(self, module_key: str) -> None:
        self._module_key = module_key

    def __call__(
        self,
        context: Annotated[RequestContext, Depends(TenantContextProvider.resolve)],
        request: Request,
    ) -> None:
        modules: TenantModules = request.app.state.tenant_modules
        modules.require(context.tenant_id, self._module_key)
