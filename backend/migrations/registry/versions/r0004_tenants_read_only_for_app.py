"""registry: erp_app loses write access to Tenants (I3)"""

from alembic import op

from erp.core.rls import RlsSql

revision = "r0004"
down_revision = "r0003"
branch_labels = None
depends_on = None

TENANTS = RlsSql.table_ref("registry", "Tenants")


def upgrade() -> None:
    # Only the operator CLI (erp_owner) places a tenant's database; the
    # API only ever reads registry."Tenants".
    op.execute(f"REVOKE INSERT, UPDATE ON {TENANTS} FROM erp_app")


def downgrade() -> None:
    op.execute(f"GRANT INSERT, UPDATE ON {TENANTS} TO erp_app")
