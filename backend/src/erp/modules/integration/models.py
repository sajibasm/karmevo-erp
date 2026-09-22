import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import Columns, TenantBase

SCHEMA = {"schema": "integration"}


class OutboxEvent(TenantBase):
    __tablename__ = "OutboxEvents"
    __table_args__ = (
        UniqueConstraint("tenantId", "outboxEventId"),
        Index(
            "ix_OutboxEvents_pending",
            "occurredAt",
            postgresql_where=sql('"dispatchedAt" IS NULL'),
        ),
        SCHEMA,
    )

    outbox_event_id: Mapped[uuid.UUID] = Columns.uuid_pk("outboxEventId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    event_topic: Mapped[str] = mapped_column("eventTopic", String(200))
    event_payload: Mapped[dict[str, Any]] = mapped_column("eventPayload", JSONB)
    occurred_at: Mapped[datetime] = Columns.timestamp("occurredAt")
    dispatched_at: Mapped[datetime | None] = mapped_column("dispatchedAt")
    attempt_count: Mapped[int] = mapped_column("attemptCount", server_default=sql("0"))
    last_error: Mapped[str | None] = mapped_column("lastError", String(500))


class ProcessedEvent(TenantBase):
    """One row per (consumer, event) handled.

    Written inside the consumer's business transaction.
    """

    __tablename__ = "ProcessedEvents"
    __table_args__ = (SCHEMA,)

    consumer_name: Mapped[str] = mapped_column("consumerName", String(100), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column("eventId", primary_key=True)
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    processed_at: Mapped[datetime] = Columns.timestamp("processedAt")
