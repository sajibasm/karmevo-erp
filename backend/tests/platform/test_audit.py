import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from erp.modules.platform.audit import AuditTrail, Redactor
from erp.modules.platform.models import AuditEvent

REDACTED = Redactor.REDACTED


def test_redact_masks_sensitive_keys_recursively():
    value = {
        "user": "alice",
        "password": "pw",
        "nested": {"api_secret": "s", "items": [{"refresh_token": "t", "qty": 2}]},
        "Authorization": "Bearer x",
        "salary": "90000",
    }

    assert Redactor.redact(value) == {
        "user": "alice",
        "password": REDACTED,
        "nested": {
            "api_secret": REDACTED,
            "items": [{"refresh_token": REDACTED, "qty": 2}],
        },
        "Authorization": REDACTED,
        "salary": REDACTED,
    }


def _record(router, tenant_id, **details):
    with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
        return AuditTrail(s).record(
            tenant_id=tenant_id,
            actor_identity_id=None,
            action="platform.company.create",
            target_type="company",
            target_id="c-1",
            outcome="success",
            details=details,
        )


def test_event_is_redacted_and_stays_in_the_tenant_database(router, two_tenants):
    a, b = two_tenants.a, two_tenants.b
    event_id = _record(router, a, name="Alpha", password="pw")

    with router.for_tenant(a).tenant_session(a) as s:
        details = s.get(AuditEvent, event_id).audit_details
    with router.for_tenant(b).tenant_session(b) as s:
        in_b = s.scalars(select(AuditEvent)).all()

    assert details == {"name": "Alpha", "password": REDACTED}
    assert in_b == []


@pytest.mark.parametrize("statement", ["update", "delete"])
def test_runtime_role_cannot_modify_audit_history(router, two_tenants, statement):
    a = two_tenants.a
    event_id = _record(router, a)
    matches = AuditEvent.audit_event_id == event_id
    stmt = (
        update(AuditEvent).where(matches).values(audit_outcome="failure")
        if statement == "update"
        else delete(AuditEvent).where(matches)
    )

    with pytest.raises(DBAPIError, match="permission denied"):
        with router.for_tenant(a).tenant_session(a) as s:
            s.execute(stmt)
