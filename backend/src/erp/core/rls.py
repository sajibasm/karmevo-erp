class RlsSql:
    """Row-level security SQL for both migration trees (ADR-0002)."""

    # nullif(): after a transaction-local set_config() the setting reads
    # back as '' rather than NULL, so both mean "no context".
    TENANT_EXPR = "nullif(current_setting('app.tenant_id', true), '')::uuid"
    IDENTITY_EXPR = "nullif(current_setting('app.identity_id', true), '')::uuid"

    @staticmethod
    def table_ref(schema: str, table: str) -> str:
        """Quote a CamelCase table name for raw SQL (ADR-0010)."""
        return f'{schema}."{table}"'

    @classmethod
    def tenant_policy(cls, schema: str, table: str) -> list[str]:
        """Force RLS on a tenant table, limited to its tenant."""
        ref = cls.table_ref(schema, table)
        condition = f'"tenantId" = {cls.TENANT_EXPR}'
        return [
            f"ALTER TABLE {ref} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {ref} FORCE ROW LEVEL SECURITY",
            f'CREATE POLICY "tenantIsolation" ON {ref} '
            f"USING ({condition}) WITH CHECK ({condition})",
        ]

    @classmethod
    def identity_read_policy(cls, schema: str, table: str) -> str:
        """Let an identity read its own rows without tenant context."""
        return (
            f'CREATE POLICY "identitySelfRead" ON {cls.table_ref(schema, table)} '
            f'FOR SELECT USING ("identityId" = {cls.IDENTITY_EXPR})'
        )
