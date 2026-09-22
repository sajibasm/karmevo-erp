"""registry: per-tenant module enablement (TenantModules)"""

import sqlalchemy as sa
from alembic import op

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "r0003"
down_revision = "r0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TenantModules",
        cols.registry_tenant_id("TenantModules"),
        sa.Column("moduleKey", sa.String(64), nullable=False),
        sa.Column("isEnabled", sa.Boolean(), nullable=False),
        cols.timestamp("changedAt"),
        sa.PrimaryKeyConstraint("tenantId", "moduleKey", name="pk_TenantModules"),
        schema="registry",
    )
    for statement in RlsSql.tenant_policy("registry", "TenantModules"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("TenantModules", schema="registry")
