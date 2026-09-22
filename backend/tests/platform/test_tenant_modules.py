from uuid import uuid4

import pytest

from erp.core.modules import ModuleCatalog, ModuleManifest
from erp.modules.platform.module_state import (
    ModuleChangeRejectedError,
    ModuleDisabledError,
    TenantModules,
)
from erp.modules.platform.registry_models import Tenant

CATALOG = ModuleCatalog(
    [
        ModuleManifest("platform", "Platform", core=True),
        ModuleManifest("catalog", "Catalogue", ("platform",)),
        ModuleManifest("inventory", "Inventory", ("catalog",)),
        ModuleManifest("sales", "Sales", ("inventory", "catalog")),
    ]
)


@pytest.fixture
def modules(registry_owner):
    # Enable/disable only ever runs operator-side, as erp_owner (I3):
    # it row-locks Tenants, which needs UPDATE privilege in Postgres.
    return TenantModules(registry_owner, CATALOG)


def _tenant(registry_owner):
    """Insert as erp_owner: erp_app can't write Tenants (I3)."""
    with registry_owner.platform_session() as s:
        tenant = Tenant(
            account_number=f"M{uuid4().hex[:12]}",
            tenant_name="Modules Ltd",
            database_name=f"unprovisioned_{uuid4().hex}",
        )
        s.add(tenant)
        s.flush()
        return tenant.tenant_id


def test_core_modules_are_always_enabled(modules, registry_owner):
    assert modules.enabled(_tenant(registry_owner)) == {"platform"}


def test_enabling_requires_dependencies_first(modules, registry_owner):
    tenant_id = _tenant(registry_owner)

    with pytest.raises(ModuleChangeRejectedError, match="catalog, inventory"):
        modules.enable(tenant_id, "sales")


def test_enabling_with_dependencies_enables_them_in_order(modules, registry_owner):
    tenant_id = _tenant(registry_owner)

    enabled = modules.enable(tenant_id, "sales", with_dependencies=True)

    assert enabled == ["catalog", "inventory", "sales"]
    expected = {"platform", "catalog", "inventory", "sales"}
    assert modules.enabled(tenant_id) == expected


def test_cannot_disable_a_module_enabled_modules_depend_on(modules, registry_owner):
    tenant_id = _tenant(registry_owner)
    modules.enable(tenant_id, "sales", with_dependencies=True)

    with pytest.raises(ModuleChangeRejectedError, match="sales"):
        modules.disable(tenant_id, "inventory")


def test_disable_then_re_enable(modules, registry_owner):
    tenant_id = _tenant(registry_owner)
    modules.enable(tenant_id, "sales", with_dependencies=True)

    modules.disable(tenant_id, "sales")
    assert "sales" not in modules.enabled(tenant_id)
    modules.enable(tenant_id, "sales")
    assert "sales" in modules.enabled(tenant_id)


def test_core_module_cannot_be_disabled(modules, registry_owner):
    with pytest.raises(ModuleChangeRejectedError, match="core"):
        modules.disable(_tenant(registry_owner), "platform")


def test_require_rejects_disabled_modules(modules, registry_owner):
    tenant_id = _tenant(registry_owner)

    with pytest.raises(ModuleDisabledError):
        modules.require(tenant_id, "catalog")
    modules.enable(tenant_id, "catalog")
    modules.require(tenant_id, "catalog")


def test_enablement_is_per_tenant(modules, registry_owner):
    a, b = _tenant(registry_owner), _tenant(registry_owner)

    modules.enable(a, "catalog")

    assert "catalog" in modules.enabled(a)
    assert "catalog" not in modules.enabled(b)
