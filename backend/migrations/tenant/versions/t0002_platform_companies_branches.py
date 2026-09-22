"""tenant DB: platform Companies and Branches"""

import sqlalchemy as sa
from alembic import op

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "t0002"
down_revision = "t0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Companies",
        cols.uuid("companyId"),
        cols.owner_tenant_id("Companies"),
        sa.Column("companyName", sa.String(200), nullable=False),
        sa.Column("countryCode", sa.String(2), nullable=False),
        sa.Column("baseCurrency", sa.String(3), nullable=False),
        sa.Column("timeZone", sa.String(64), nullable=False),
        cols.created_at(),
        sa.PrimaryKeyConstraint("companyId", name="pk_Companies"),
        sa.UniqueConstraint("tenantId", "companyId", name="uq_Companies_tenantId_companyId"),
        schema="platform",
    )
    op.create_table(
        "Branches",
        cols.uuid("branchId"),
        cols.owner_tenant_id("Branches"),
        sa.Column("companyId", sa.Uuid(), nullable=False),
        sa.Column("branchCode", sa.String(32), nullable=False),
        sa.Column("branchName", sa.String(200), nullable=False),
        cols.created_at(),
        sa.PrimaryKeyConstraint("branchId", name="pk_Branches"),
        sa.UniqueConstraint("tenantId", "branchId", name="uq_Branches_tenantId_branchId"),
        sa.UniqueConstraint(
            "tenantId",
            "companyId",
            "branchCode",
            name="uq_Branches_tenantId_companyId_branchCode",
        ),
        sa.ForeignKeyConstraint(
            ["tenantId", "companyId"],
            ["platform.Companies.tenantId", "platform.Companies.companyId"],
            name="fk_Branches_tenantId_companyId_Companies",
        ),
        schema="platform",
    )
    for table in ("Companies", "Branches"):
        for statement in RlsSql.tenant_policy("platform", table):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("Branches", schema="platform")
    op.drop_table("Companies", schema="platform")
