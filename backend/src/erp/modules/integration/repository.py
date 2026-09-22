from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from erp.modules.integration.models import OutboxEvent, ProcessedEvent


class OutboxEventRepository:
    """All queries on integration "OutboxEvents"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: OutboxEvent) -> UUID:
        self._session.add(event)
        self._session.flush()
        return event.outbox_event_id

    def claim_pending(self, *, batch_size: int, max_attempts: int) -> list[OutboxEvent]:
        """Lock the oldest undispatched events, skipping locked rows."""
        return list(
            self._session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.dispatched_at.is_(None),
                    OutboxEvent.attempt_count < max_attempts,
                )
                .order_by(OutboxEvent.occurred_at, OutboxEvent.outbox_event_id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )


class ProcessedEventRepository:
    """All queries on integration "ProcessedEvents"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(self, *, consumer: str, event_id: UUID, tenant_id: UUID) -> bool:
        """Insert the (consumer, event) key; False if it exists."""
        statement = (
            insert(ProcessedEvent)
            .values(
                {
                    ProcessedEvent.consumer_name: consumer,
                    ProcessedEvent.event_id: event_id,
                    ProcessedEvent.tenant_id: tenant_id,
                }
            )
            .on_conflict_do_nothing(index_elements=["consumerName", "eventId"])
            .returning(ProcessedEvent.event_id)
        )
        return self._session.execute(statement).first() is not None
