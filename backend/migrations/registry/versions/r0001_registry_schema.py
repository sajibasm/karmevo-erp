"""registry schema and runtime grants"""

from alembic import op

revision = "r0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA registry")
    op.execute("GRANT USAGE ON SCHEMA registry TO erp_app")
    # No DELETE by default; deletable tables get an explicit grant.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA registry "
        "GRANT SELECT, INSERT, UPDATE ON TABLES TO erp_app"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA registry CASCADE")
