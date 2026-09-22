"""registry: Tenants, Identities, Memberships"""

import sqlalchemy as sa
from alembic import op

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "r0002"
down_revision = "r0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Tenants",
        cols.uuid("tenantId"),
        sa.Column("accountNumber", sa.String(32), nullable=False),
        sa.Column("tenantName", sa.String(200), nullable=False),
        sa.Column("tenantStatus", sa.String(16), nullable=False, server_default="active"),
        sa.Column("databaseServer", sa.String(64), nullable=False, server_default="default"),
        sa.Column("databaseName", sa.String(63), nullable=False),
        sa.Column(
            "databaseStatus",
            sa.String(16),
            nullable=False,
            server_default="provisioning",
        ),
        sa.Column("schemaRevision", sa.String(32), nullable=True),
        sa.Column("lastMigrationError", sa.String(1000), nullable=True),
        cols.created_at(),
        sa.PrimaryKeyConstraint("tenantId", name="pk_Tenants"),
        sa.UniqueConstraint("accountNumber", name="uq_Tenants_accountNumber"),
        sa.UniqueConstraint("databaseName", name="uq_Tenants_databaseName"),
        sa.CheckConstraint(
            "\"tenantStatus\" in ('active', 'suspended')",
            name="ck_Tenants_tenantStatus",
        ),
        sa.CheckConstraint(
            "\"databaseStatus\" in ('provisioning', 'ready', 'failed')",
            name="ck_Tenants_databaseStatus",
        ),
        schema="registry",
    )
    op.create_table(
        "Identities",
        cols.uuid("identityId"),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        cols.created_at(),
        sa.PrimaryKeyConstraint("identityId", name="pk_Identities"),
        sa.UniqueConstraint("issuer", "subject", name="uq_Identities_issuer_subject"),
        schema="registry",
    )
    op.create_table(
        "Memberships",
        cols.uuid("membershipId"),
        cols.registry_tenant_id("Memberships"),
        sa.Column(
            "identityId",
            sa.Uuid(),
            sa.ForeignKey(
                "registry.Identities.identityId",
                name="fk_Memberships_identityId_Identities",
            ),
            nullable=False,
        ),
        sa.Column("membershipKind", sa.String(16), nullable=False, server_default="staff"),
        sa.Column("membershipStatus", sa.String(16), nullable=False, server_default="active"),
        cols.created_at(),
        sa.PrimaryKeyConstraint("membershipId", name="pk_Memberships"),
        sa.UniqueConstraint(
            "tenantId", "membershipId", name="uq_Memberships_tenantId_membershipId"
        ),
        sa.UniqueConstraint(
            "tenantId",
            "identityId",
            "membershipKind",
            name="uq_Memberships_tenantId_identityId_membershipKind",
        ),
        sa.CheckConstraint(
            "\"membershipKind\" in ('staff', 'buyer', 'service')",
            name="ck_Memberships_membershipKind",
        ),
        sa.CheckConstraint(
            "\"membershipStatus\" in ('active', 'suspended')",
            name="ck_Memberships_membershipStatus",
        ),
        schema="registry",
    )
    for statement in RlsSql.tenant_policy("registry", "Memberships"):
        op.execute(statement)
    op.execute(RlsSql.identity_read_policy("registry", "Memberships"))


def downgrade() -> None:
    for table in ("Memberships", "Identities", "Tenants"):
        op.drop_table(table, schema="registry")
