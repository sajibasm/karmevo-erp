from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from support import OWNER

import erp.model_registry  # noqa: F401
from erp.core.models import RegistryBase, TenantBase


def test_registry_models_match_migrations(registry_owner_engine):
    with registry_owner_engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"include_schemas": True})
        assert compare_metadata(context, RegistryBase.metadata) == []


def test_tenant_models_match_migrations(provisioned, locator):
    url = locator.url("default", locator.database_name(provisioned[0]), OWNER)
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts={"include_schemas": True})
            assert compare_metadata(context, TenantBase.metadata) == []
    finally:
        engine.dispose()
