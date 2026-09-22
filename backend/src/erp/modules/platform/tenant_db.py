"""Route each tenant to its own database (ADR-0002)."""

import threading
from collections import OrderedDict
from typing import Any, ClassVar
from uuid import UUID

from erp.core.db import Database, DbCredentials, TenantDbLocator
from erp.core.errors import NotFoundError, ServiceUnavailableError
from erp.modules.platform.registry_repository import TenantRepository


class TenantUnavailableError(ServiceUnavailableError):
    code = "TENANT_UNAVAILABLE"


class TenantDatabaseRouter:
    """One small pool per recently used tenant database (LRU-bounded).

    Build one router per runtime role: erp_app for the API and workers,
    erp_relay for the outbox relay. Call evict() after moving or
    restoring a tenant database.
    """

    DEFAULT_POOL: ClassVar[dict[str, int]] = {
        "pool_size": 2,
        "max_overflow": 3,
        "pool_recycle": 1800,
    }

    def __init__(
        self,
        registry: Database,
        locator: TenantDbLocator,
        credentials: DbCredentials,
        *,
        max_cached: int = 200,
        **engine_kwargs: Any,
    ) -> None:
        self._registry = registry
        self._locator = locator
        self._credentials = credentials
        self._max_cached = max_cached
        self._engine_kwargs = self.DEFAULT_POOL | engine_kwargs
        self._cache: OrderedDict[UUID, Database] = OrderedDict()
        self._lock = threading.Lock()

    def for_tenant(self, tenant_id: UUID) -> Database:
        with self._lock:
            cached = self._cache.get(tenant_id)
            if cached is not None:
                self._cache.move_to_end(tenant_id)
                return cached
        server, database_name = self._placement(tenant_id)
        url = self._locator.url(server, database_name, self._credentials)
        database = Database(url, **self._engine_kwargs)
        with self._lock:
            existing = self._cache.get(tenant_id)
            if existing is not None:  # another thread won the race
                database.dispose()
                return existing
            self._cache[tenant_id] = database
            while len(self._cache) > self._max_cached:
                _, evicted = self._cache.popitem(last=False)
                evicted.dispose()
        return database

    def active_tenant_ids(self) -> list[UUID]:
        with self._registry.platform_session() as s:
            return TenantRepository(s).active_ids()

    def evict(self, tenant_id: UUID) -> None:
        with self._lock:
            evicted = self._cache.pop(tenant_id, None)
        if evicted is not None:
            evicted.dispose()

    def dispose_all(self) -> None:
        with self._lock:
            databases = list(self._cache.values())
            self._cache.clear()
        for database in databases:
            database.dispose()

    def _placement(self, tenant_id: UUID) -> tuple[str, str]:
        with self._registry.platform_session() as s:
            tenant = TenantRepository(s).get(tenant_id)
        if tenant is None:
            raise NotFoundError("unknown tenant", code="TENANT_NOT_FOUND")
        if tenant.database_status != "ready":
            raise TenantUnavailableError("the tenant database is not available")
        return tenant.database_server, tenant.database_name
