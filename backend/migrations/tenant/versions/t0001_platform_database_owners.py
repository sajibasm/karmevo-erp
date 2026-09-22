"""tenant DB: module schemas, runtime grants, DatabaseOwners"""

import sqlalchemy as sa
from alembic import op

from erp.core.rls import RlsSql

revision = "t0001"
down_revision = None
branch_labels = None
depends_on = None

# Later module schemas are created by the slice that introduces the
# module. Every installed module's tables exist in every tenant DB,
# whether or not the tenant enabled the module (ADR-0009).
SCHEMAS = ("platform", "integration")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA {schema}")
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO erp_app")
        op.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            "GRANT SELECT, INSERT, UPDATE ON TABLES TO erp_app"
        )
    op.execute("GRANT USAGE ON SCHEMA integration TO erp_relay")
    op.create_table(
        "DatabaseOwners",
        sa.Column(
            "isSingleton",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("tenantId", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("isSingleton", name="pk_DatabaseOwners"),
        sa.UniqueConstraint("tenantId", name="uq_DatabaseOwners_tenantId"),
        sa.CheckConstraint('"isSingleton"', name="ck_DatabaseOwners_isSingleton"),
        schema="platform",
    )
    # Bound once by the provisioner (erp_owner); the runtime only reads.
    owners = RlsSql.table_ref("platform", "DatabaseOwners")
    op.execute(f"REVOKE INSERT, UPDATE ON {owners} FROM erp_app")


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA {schema} CASCADE")
