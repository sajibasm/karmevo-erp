from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from erp.modules.platform.provisioning import (
    MissingTenantDatabaseError,
    TenantDatabaseAdmin,
)
from erp.modules.platform.registry_models import Tenant

BOUND_TENANT = text('SELECT "tenantId" FROM platform."DatabaseOwners"')


def _number():
    return f"P{uuid4().hex[:12]}"


def _tenant_row(registry, **where):
    with registry.platform_session() as s:
        return s.scalars(select(Tenant).filter_by(**where)).one()


def test_provision_creates_a_migrated_database_bound_to_the_tenant(
    provisioner, registry, locator, owner_connect
):
    tenant_id = provisioner.provision(account_number=_number(), tenant_name="Gamma Ltd")

    tenant = _tenant_row(registry, tenant_id=tenant_id)
    assert tenant.database_name == locator.database_name(tenant_id)
    assert tenant.database_status == "ready"
    assert tenant.schema_revision == provisioner.head_revision()
    assert tenant.last_migration_error is None
    with owner_connect(tenant.database_name) as conn:
        assert conn.scalar(BOUND_TENANT) == tenant_id


def test_complete_is_idempotent(provisioner):
    tenant_id = provisioner.provision(account_number=_number(), tenant_name="Delta Ltd")

    assert provisioner.complete(tenant_id) == provisioner.head_revision()


def test_failed_step_is_recorded_and_retry_completes(provisioner, registry, monkeypatch):
    number = _number()

    def fail(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(TenantDatabaseAdmin, "bind_owner", fail)
    with pytest.raises(RuntimeError, match="disk full"):
        provisioner.provision(account_number=number, tenant_name="Epsilon Ltd")
    failed = _tenant_row(registry, account_number=number)
    monkeypatch.undo()

    provisioner.complete(failed.tenant_id)

    assert failed.database_status == "failed"
    assert "disk full" in failed.last_migration_error
    recovered = _tenant_row(registry, tenant_id=failed.tenant_id)
    assert recovered.database_status == "ready"


def test_upgrade_all_continues_past_a_missing_database(
    provisioner, registry, locator, drop_database
):
    healthy = provisioner.provision(account_number=_number(), tenant_name="Zeta")
    broken = provisioner.provision(account_number=_number(), tenant_name="Eta")
    drop_database(locator.database_name(broken))

    outcomes = {o.tenant_id: o for o in provisioner.upgrade_all()}

    assert outcomes[healthy].error is None
    assert outcomes[healthy].revision == provisioner.head_revision()
    assert outcomes[broken].revision is None
    assert "does not exist" in outcomes[broken].error
    broken_row = _tenant_row(registry, tenant_id=broken)
    assert broken_row.database_status == "failed"


def test_a_previously_migrated_database_is_never_recreated(provisioner, locator, drop_database):
    tenant_id = provisioner.provision(account_number=_number(), tenant_name="Theta Ltd")
    drop_database(locator.database_name(tenant_id))

    with pytest.raises(MissingTenantDatabaseError):
        provisioner.complete(tenant_id)


def test_duplicate_account_number_fails_before_any_database_is_created(
    provisioner,
):
    number = _number()
    provisioner.provision(account_number=number, tenant_name="Iota Ltd")

    with pytest.raises(IntegrityError):
        provisioner.provision(account_number=number, tenant_name="Iota Copy")
