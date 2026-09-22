"""tenant DB: integration OutboxEvents and ProcessedEvents"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "t0004"
down_revision = "t0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "OutboxEvents",
        cols.uuid("outboxEventId"),
        cols.owner_tenant_id("OutboxEvents"),
        sa.Column("eventTopic", sa.String(200), nullable=False),
        sa.Column("eventPayload", JSONB(), nullable=False),
        cols.timestamp("occurredAt"),
        sa.Column("dispatchedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attemptCount", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lastError", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("outboxEventId", name="pk_OutboxEvents"),
        sa.UniqueConstraint(
            "tenantId",
            "outboxEventId",
            name="uq_OutboxEvents_tenantId_outboxEventId",
        ),
        schema="integration",
    )
    op.create_index(
        "ix_OutboxEvents_pending",
        "OutboxEvents",
        ["occurredAt"],
        schema="integration",
        postgresql_where=sa.text('"dispatchedAt" IS NULL'),
    )
    op.create_table(
        "ProcessedEvents",
        sa.Column("consumerName", sa.String(100), nullable=False),
        sa.Column("eventId", sa.Uuid(), nullable=False),
        cols.owner_tenant_id("ProcessedEvents"),
        cols.timestamp("processedAt"),
        sa.PrimaryKeyConstraint("consumerName", "eventId", name="pk_ProcessedEvents"),
        schema="integration",
    )
    for table in ("OutboxEvents", "ProcessedEvents"):
        for statement in RlsSql.tenant_policy("integration", table):
            op.execute(statement)
    # The relay reads and marks this database's outbox without
    # BYPASSRLS, and can touch nothing else (ADR-0005).
    outbox = RlsSql.table_ref("integration", "OutboxEvents")
    op.execute(f"GRANT SELECT, UPDATE ON {outbox} TO erp_relay")
    op.execute(
        f'CREATE POLICY "relayDispatch" ON {outbox} TO erp_relay USING (true) WITH CHECK (true)'
    )


def downgrade() -> None:
    op.drop_table("ProcessedEvents", schema="integration")
    op.drop_index("ix_OutboxEvents_pending", "OutboxEvents", schema="integration")
    op.drop_table("OutboxEvents", schema="integration")
