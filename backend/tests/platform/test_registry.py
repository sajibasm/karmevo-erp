from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from erp.modules.platform.registry_models import Identity, Membership, Tenant


def _tenant(registry, name):
    """A registry row only (no database), for registry-level rules."""
    with registry.platform_session() as s:
        tenant = Tenant(
            account_number=f"R{uuid4().hex[:12]}",
            tenant_name=name,
            database_name=f"unprovisioned_{uuid4().hex}",
        )
        s.add(tenant)
        s.flush()
        return tenant.tenant_id


def _identity(registry, subject="alice"):
    with registry.platform_session() as s:
        identity = Identity(issuer="https://id.test/realms/staff", subject=subject)
        s.add(identity)
        s.flush()
        return identity.identity_id


def test_new_tenant_starts_in_provisioning_state(registry):
    tenant_id = _tenant(registry, "Alpha Traders")

    with registry.platform_session() as s:
        tenant = s.get(Tenant, tenant_id)
    assert (tenant.tenant_status, tenant.database_status) == ("active", "provisioning")
    assert tenant.database_server == "default"


def test_memberships_are_isolated_by_tenant_context(registry):
    a, b = _tenant(registry, "A"), _tenant(registry, "B")
    identity_id = _identity(registry)
    with registry.tenant_session(a) as s:
        s.add(Membership(tenant_id=a, identity_id=identity_id))

    with registry.tenant_session(a) as s:
        in_a = s.scalars(select(Membership)).all()
    with registry.tenant_session(b) as s:
        in_b = s.scalars(select(Membership)).all()

    assert len(in_a) == 1
    assert in_b == []


def test_cannot_create_membership_for_another_tenant(registry):
    a, b = _tenant(registry, "A"), _tenant(registry, "B")
    identity_id = _identity(registry)

    with pytest.raises(DBAPIError, match="row-level security"):
        with registry.tenant_session(a) as s:
            s.add(Membership(tenant_id=b, identity_id=identity_id))
            s.flush()


def test_identity_lists_own_memberships_without_tenant_context(registry):
    a = _tenant(registry, "A")
    identity_id = _identity(registry)
    with registry.tenant_session(a) as s:
        s.add(Membership(tenant_id=a, identity_id=identity_id))

    with registry.platform_session(identity_id=identity_id) as s:
        own = s.scalars(select(Membership.tenant_id)).all()
    with registry.platform_session() as s:
        anonymous = s.scalars(select(Membership)).all()

    assert own == [a]
    assert anonymous == []


def test_identity_is_unique_per_issuer_and_subject(registry):
    _identity(registry, "alice")

    with pytest.raises(IntegrityError):
        _identity(registry, "alice")
