"""tenant DB: append-only platform AuditEvents"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "t0003"
down_revision = "t0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "AuditEvents",
        cols.uuid("auditEventId"),
        cols.owner_tenant_id("AuditEvents"),
        cols.timestamp("occurredAt"),
        sa.Column("actorIdentityId", sa.Uuid(), nullable=True),
        sa.Column("auditAction", sa.String(100), nullable=False),
        sa.Column("targetType", sa.String(100), nullable=False),
        sa.Column("targetId", sa.String(100), nullable=True),
        sa.Column("auditOutcome", sa.String(16), nullable=False),
        sa.Column("auditReason", sa.Text(), nullable=True),
        sa.Column(
            "auditDetails",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("auditEventId", name="pk_AuditEvents"),
        sa.UniqueConstraint(
            "tenantId", "auditEventId", name="uq_AuditEvents_tenantId_auditEventId"
        ),
        sa.CheckConstraint(
            "\"auditOutcome\" in ('success', 'denied', 'failure')",
            name="ck_AuditEvents_auditOutcome",
        ),
        schema="platform",
    )
    for statement in RlsSql.tenant_policy("platform", "AuditEvents"):
        op.execute(statement)
    audit_events = RlsSql.table_ref("platform", "AuditEvents")
    op.execute(f"REVOKE UPDATE ON {audit_events} FROM erp_app")


def downgrade() -> None:
    op.drop_table("AuditEvents", schema="platform")
