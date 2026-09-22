"""Alembic environment for ONE tenant database.

The URL is always supplied by the provisioner.
"""

from alembic import context

import erp.model_registry  # noqa: F401
from erp.core.migrations import AlembicEnvironment
from erp.core.models import TenantBase

url = context.config.get_main_option("sqlalchemy.url")
if not url:
    raise RuntimeError(
        "tenant migrations need an explicit database URL; run `python -m erp.cli upgrade-tenants`"
    )
AlembicEnvironment(TenantBase.metadata, url).run()
