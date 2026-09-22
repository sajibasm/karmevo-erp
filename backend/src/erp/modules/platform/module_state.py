"""Per-tenant module enablement (ADR-0009, PLT-05)."""

from uuid import UUID

from sqlalchemy.orm import Session

from erp.core.db import Database
from erp.core.errors import ConflictError, ForbiddenError, NotFoundError
from erp.core.modules import ModuleCatalog
from erp.modules.platform.registry_repository import (
    TenantModuleRepository,
    TenantRepository,
)


class ModuleDisabledError(ForbiddenError):
    code = "MODULE_DISABLED"


class ModuleChangeRejectedError(ConflictError):
    code = "MODULE_CHANGE_REJECTED"


class TenantModules:
    """Enable, disable and check modules for one tenant at a time."""

    def __init__(self, registry: Database, catalog: ModuleCatalog) -> None:
        self._registry = registry
        self._catalog = catalog

    def enabled(self, tenant_id: UUID) -> frozenset[str]:
        with self._registry.tenant_session(tenant_id) as s:
            return self._enabled(s, tenant_id)

    def require(self, tenant_id: UUID, key: str) -> None:
        if key not in self.enabled(tenant_id):
            name = self._catalog.get(key).name
            raise ModuleDisabledError(f"the {name} module is not enabled for this account")

    def enable(self, tenant_id: UUID, key: str, *, with_dependencies: bool = False) -> list[str]:
        """Enable `key`; return the newly enabled modules in order.

        Missing dependencies are rejected unless the caller explicitly
        asks to enable them as well.
        """
        self._catalog.get(key)
        with self._registry.tenant_session(tenant_id) as s:
            self._lock(s, tenant_id)
            current = self._enabled(s, tenant_id)
            dependencies = self._catalog.dependencies(key)
            missing = [d for d in dependencies if d not in current]
            if missing and not with_dependencies:
                raise ModuleChangeRejectedError(
                    f"{key} requires {', '.join(missing)} to be enabled first"
                )
            newly_enabled = missing + ([] if key in current else [key])
            modules = TenantModuleRepository(s)
            for module_key in newly_enabled:
                modules.upsert(tenant_id, module_key, is_enabled=True)
        return newly_enabled

    def disable(self, tenant_id: UUID, key: str) -> None:
        if self._catalog.get(key).core:
            raise ModuleChangeRejectedError(f"{key} is a core module and cannot be disabled")
        with self._registry.tenant_session(tenant_id) as s:
            self._lock(s, tenant_id)
            current = self._enabled(s, tenant_id)
            dependents = self._catalog.dependents(key)
            blocking = [d for d in dependents if d in current]
            if blocking:
                raise ModuleChangeRejectedError(f"disable {', '.join(blocking)} before {key}")
            if key in current:
                TenantModuleRepository(s).upsert(tenant_id, key, is_enabled=False)

    def _enabled(self, session: Session, tenant_id: UUID) -> frozenset[str]:
        installed = {m.key for m in self._catalog}
        stored = TenantModuleRepository(session).enabled_keys(tenant_id)
        return self._catalog.core_keys() | (stored & installed)

    @staticmethod
    def _lock(session: Session, tenant_id: UUID) -> None:
        """Serialise module changes per tenant."""
        if not TenantRepository(session).lock(tenant_id):
            raise NotFoundError("unknown tenant", code="TENANT_NOT_FOUND")
