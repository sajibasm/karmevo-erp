"""Alembic environment for the central registry database."""

from alembic import context

from erp.core.config import Settings
from erp.core.migrations import AlembicEnvironment
from erp.core.models import RegistryBase

url = (
    context.config.get_main_option("sqlalchemy.url")
    or Settings.load().registry_migration_database_url
)
AlembicEnvironment(RegistryBase.metadata, url).run()
