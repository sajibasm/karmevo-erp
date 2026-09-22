"""Public surface of the platform module; import only from here."""

from erp.modules.platform.tenant_db import TenantDatabaseRouter, TenantUnavailableError

__all__ = ["TenantDatabaseRouter", "TenantUnavailableError"]
