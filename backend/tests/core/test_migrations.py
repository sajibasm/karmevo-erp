from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import erp.model_registry  # noqa: F401
from erp.core.models import RegistryBase


def test_registry_models_match_migrations(registry_owner_engine):
    with registry_owner_engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"include_schemas": True})
        assert compare_metadata(context, RegistryBase.metadata) == []
