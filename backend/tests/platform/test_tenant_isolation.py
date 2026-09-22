"""Per-tenant databases plus in-database defence (E2E-01 seed)."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from support import APP

from erp.core.errors import NotFoundError
from erp.modules.platform.models import Company, DatabaseOwner
from erp.modules.platform.registry_models import Tenant
from erp.modules.platform.tenant_db import TenantDatabaseRouter, TenantUnavailableError


def _company(tenant_id, name="Injected Ltd"):
    return Company(
        tenant_id=tenant_id,
        company_name=name,
        country_code="BD",
        base_currency="BDT",
        time_zone="Asia/Dhaka",
    )


def test_each_tenant_is_routed_to_its_own_database(router, locator, two_tenants):
    for tenant_id in (two_tenants.a, two_tenants.b):
        with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
            current = s.scalar(text("select current_database()"))
        assert current == locator.database_name(tenant_id)


def test_tenant_database_contains_only_its_own_data(router, two_tenants):
    a = two_tenants.a
    with router.for_tenant(a).tenant_session(a) as s:
        names = s.scalars(select(Company.company_name)).all()
    assert names == ["Alpha Traders Ltd"]


def test_wrong_context_in_a_tenant_database_sees_nothing(router, two_tenants):
    """A's database opened with B's context: RLS returns no rows."""
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.b) as s:
        assert s.scalars(select(Company)).all() == []


def test_tenant_database_cannot_store_another_tenants_rows(router, two_tenants):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises(IntegrityError):
        with database.tenant_session(two_tenants.b) as s:
            s.add(_company(two_tenants.b))
            s.flush()


def test_rls_rejects_rows_outside_the_current_context(router, two_tenants):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises(DBAPIError, match="row-level security"):
        with database.tenant_session(two_tenants.a) as s:
            s.add(_company(two_tenants.b))
            s.flush()


def test_missing_context_returns_no_rows(router, two_tenants):
    with router.for_tenant(two_tenants.a).platform_session() as s:
        assert s.scalars(select(Company)).all() == []


def test_runtime_role_cannot_rebind_a_tenant_database(router, two_tenants):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises(DBAPIError, match="permission denied"):
        with database.tenant_session(two_tenants.a) as s:
            s.execute(update(DatabaseOwner).values(tenant_id=two_tenants.b))


def test_router_reuses_one_pool_per_tenant(router, two_tenants):
    assert router.for_tenant(two_tenants.a) is router.for_tenant(two_tenants.a)
    assert router.for_tenant(two_tenants.a) is not router.for_tenant(two_tenants.b)


def test_router_evicts_least_recently_used_pools(registry, locator, provisioned):
    a, b = provisioned
    small = TenantDatabaseRouter(registry, locator, APP, max_cached=1)
    try:
        first = small.for_tenant(a)
        small.for_tenant(b)
        assert small.for_tenant(a) is not first
    finally:
        small.dispose_all()


def test_unknown_tenant_is_not_found(router):
    with pytest.raises(NotFoundError):
        router.for_tenant(uuid4())


def test_tenant_without_ready_database_is_unavailable(router, registry):
    with registry.platform_session() as s:
        tenant = Tenant(
            account_number=f"U{uuid4().hex[:12]}",
            tenant_name="Pending Ltd",
            database_name=f"unprovisioned_{uuid4().hex}",
        )
        s.add(tenant)
        s.flush()
        tenant_id = tenant.tenant_id

    with pytest.raises(TenantUnavailableError):
        router.for_tenant(tenant_id)
