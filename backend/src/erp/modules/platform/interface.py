"""Public surface of the platform module; import only from here."""

from erp.modules.platform.context import RequestContext, TenantContextService
from erp.modules.platform.dependencies import (
    ModuleGuard,
    TenantContextProvider,
    TenantDatabaseProvider,
)
from erp.modules.platform.module_state import (
    ModuleChangeRejectedError,
    ModuleDisabledError,
    TenantModules,
)
from erp.modules.platform.tenant_db import TenantDatabaseRouter, TenantUnavailableError

__all__ = [
    "ModuleChangeRejectedError",
    "ModuleDisabledError",
    "ModuleGuard",
    "RequestContext",
    "TenantContextProvider",
    "TenantContextService",
    "TenantDatabaseProvider",
    "TenantDatabaseRouter",
    "TenantModules",
    "TenantUnavailableError",
]
