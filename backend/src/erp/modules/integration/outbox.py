import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy.orm import Session

from erp.core.db import Database
from erp.modules.integration.models import OutboxEvent
from erp.modules.integration.repository import (
    OutboxEventRepository,
    ProcessedEventRepository,
)
from erp.modules.platform.interface import TenantDatabaseRouter


@dataclass(frozen=True)
class OutboxMessage:
    event_id: UUID
    tenant_id: UUID
    topic: str
    payload: dict[str, Any]


Publisher = Callable[[OutboxMessage], None]


class Outbox:
    """Add events to the caller's business transaction (ARC-03)."""

    def __init__(self, session: Session) -> None:
        self._events = OutboxEventRepository(session)

    def enqueue(self, *, tenant_id: UUID, topic: str, payload: dict[str, Any]) -> UUID:
        return self._events.add(
            OutboxEvent(tenant_id=tenant_id, event_topic=topic, event_payload=payload)
        )


class OutboxRelay:
    """Publish one tenant DB's committed outbox rows at least once.

    Must use erp_relay credentials (ADR-0005). If the process dies after
    publishing but before committing, the events are published again;
    EventInbox makes that harmless.
    """

    def __init__(
        self,
        database: Database,
        publish: Publisher,
        *,
        batch_size: int = 100,
        max_attempts: int = 10,
    ) -> None:
        self._db = database
        self._publish = publish
        self._batch_size = batch_size
        self._max_attempts = max_attempts

    def run_once(self) -> int:
        published = 0
        with self._db.platform_session() as session:
            events = OutboxEventRepository(session).claim_pending(
                batch_size=self._batch_size, max_attempts=self._max_attempts
            )
            for event in events:
                if self._dispatch(event):
                    published += 1
        return published

    def _dispatch(self, event: OutboxEvent) -> bool:
        event.attempt_count += 1
        message = OutboxMessage(
            event.outbox_event_id,
            event.tenant_id,
            event.event_topic,
            event.event_payload,
        )
        try:
            self._publish(message)
        except Exception as exc:  # noqa: BLE001 - retried next run
            event.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return False
        event.dispatched_at = datetime.now(UTC)
        return True


class TenantOutboxRelay:
    """One relay pass over every active tenant database.

    An unreachable tenant is logged and skipped so it never blocks the
    others. Pass a router built with erp_relay credentials.
    """

    LOGGER: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(
        self, router: TenantDatabaseRouter, publish: Publisher, **relay_kwargs: Any
    ) -> None:
        self._router = router
        self._publish = publish
        self._relay_kwargs = relay_kwargs

    def run_pass(self) -> int:
        total = 0
        for tenant_id in self._router.active_tenant_ids():
            try:
                database = self._router.for_tenant(tenant_id)
                relay = OutboxRelay(database, self._publish, **self._relay_kwargs)
                total += relay.run_once()
            except Exception:  # noqa: BLE001 - isolate tenant failures
                self.LOGGER.exception("outbox relay failed for %s", tenant_id)
        return total


class EventInbox:
    """Exactly-once consumer effects over at-least-once delivery."""

    def __init__(self, session: Session) -> None:
        self._processed = ProcessedEventRepository(session)

    def consume_once(self, *, consumer: str, message: OutboxMessage) -> bool:
        """Claim (consumer, event) in the caller's transaction.

        Returns False if already processed. Apply the handler's effects
        in the same transaction: if the handler fails, the claim rolls
        back too and a retry can process the event.
        """
        return self._processed.claim(
            consumer=consumer,
            event_id=message.event_id,
            tenant_id=message.tenant_id,
        )
