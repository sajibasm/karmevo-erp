from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from erp.modules.integration.models import OutboxEvent
from erp.modules.integration.outbox import (
    EventInbox,
    Outbox,
    OutboxMessage,
    OutboxRelay,
    TenantOutboxRelay,
)


def _enqueue(router, tenant_id, n=1):
    with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
        return Outbox(s).enqueue(tenant_id=tenant_id, topic="test.happened", payload={"n": n})


def test_enqueue_rolls_back_with_the_business_transaction(router, relay_router, two_tenants):
    a = two_tenants.a
    with pytest.raises(RuntimeError):
        with router.for_tenant(a).tenant_session(a) as s:
            Outbox(s).enqueue(tenant_id=a, topic="test.happened", payload={})
            raise RuntimeError("business rule failed")

    relay = OutboxRelay(relay_router.for_tenant(a), lambda m: None)
    assert relay.run_once() == 0


def test_relay_pass_publishes_every_tenant_database_once(router, relay_router, two_tenants):
    _enqueue(router, two_tenants.a)
    _enqueue(router, two_tenants.b)
    published: list[OutboxMessage] = []
    relay = TenantOutboxRelay(relay_router, published.append)

    assert relay.run_pass() == 2
    assert relay.run_pass() == 0
    tenants = {m.tenant_id for m in published}
    assert tenants == {two_tenants.a, two_tenants.b}


def test_relay_pass_skips_an_unreachable_tenant(router, relay_router, two_tenants):
    _enqueue(router, two_tenants.a)
    broken = uuid4()

    class RouterWithBrokenTenant:
        def active_tenant_ids(self):
            return [broken, *relay_router.active_tenant_ids()]

        def for_tenant(self, tenant_id):
            if tenant_id == broken:
                raise ConnectionError("tenant database down")
            return relay_router.for_tenant(tenant_id)

    published: list[OutboxMessage] = []
    relay = TenantOutboxRelay(RouterWithBrokenTenant(), published.append)

    assert relay.run_pass() == 1


def test_failed_publish_is_retried_on_next_run(router, relay_router, two_tenants):
    _enqueue(router, two_tenants.a)
    calls: list[OutboxMessage] = []

    def flaky(message: OutboxMessage) -> None:
        calls.append(message)
        if len(calls) == 1:
            raise ConnectionError("broker unavailable")

    relay = OutboxRelay(relay_router.for_tenant(two_tenants.a), flaky)

    assert relay.run_once() == 0
    assert relay.run_once() == 1
    assert len(calls) == 2


def test_events_past_max_attempts_stop_being_retried(router, relay_router, two_tenants):
    _enqueue(router, two_tenants.a)
    calls = []

    def always_fails(message: OutboxMessage) -> None:
        calls.append(message)
        raise ConnectionError("broker unavailable")

    relay = OutboxRelay(relay_router.for_tenant(two_tenants.a), always_fails, max_attempts=2)
    for _ in range(3):
        relay.run_once()

    assert len(calls) == 2


def test_wrong_context_cannot_read_a_tenants_outbox(router, two_tenants):
    _enqueue(router, two_tenants.a)

    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.b) as s:
        assert s.scalars(select(OutboxEvent)).all() == []


def test_relay_role_cannot_read_business_tables(relay_router, two_tenants):
    database = relay_router.for_tenant(two_tenants.a)
    with pytest.raises(DBAPIError, match="permission denied"):
        with database.platform_session() as s:
            s.execute(text('select * from platform."Companies"'))


def test_redelivered_event_has_a_single_effect(router, relay_router, two_tenants):
    """E2E-12 seed: the relay's commit is lost after publishing."""
    event_id = _enqueue(router, two_tenants.a)
    published: list[OutboxMessage] = []
    relay_db = relay_router.for_tenant(two_tenants.a)
    OutboxRelay(relay_db, published.append).run_once()
    with relay_db.platform_session() as s:
        s.execute(
            update(OutboxEvent)
            .where(OutboxEvent.outbox_event_id == event_id)
            .values(dispatched_at=None)
        )
    OutboxRelay(relay_db, published.append).run_once()

    effects = []
    for message in published:
        database = router.for_tenant(message.tenant_id)
        with database.tenant_session(message.tenant_id) as s:
            inbox = EventInbox(s)
            if inbox.consume_once(consumer="test-consumer", message=message):
                effects.append(message.event_id)

    assert len(published) == 2
    assert effects == [event_id]


def test_consumer_failure_releases_the_dedup_record(router, two_tenants):
    a = two_tenants.a
    message = OutboxMessage(uuid4(), a, "test.happened", {})
    tenant_db = router.for_tenant(a)

    with pytest.raises(RuntimeError):
        with tenant_db.tenant_session(a) as s:
            assert EventInbox(s).consume_once(consumer="c", message=message)
            raise RuntimeError("handler crashed")
    with tenant_db.tenant_session(a) as s:
        assert EventInbox(s).consume_once(consumer="c", message=message)
