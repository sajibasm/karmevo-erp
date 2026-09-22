from functools import cache
from typing import Self

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration from ERP_* environment variables.

    Defaults match deploy/compose.dev.yml and are for development only.
    """

    model_config = SettingsConfigDict(env_prefix="ERP_")

    registry_database_url: str = (
        "postgresql+psycopg://erp_app:erp_app_dev@localhost:55432/erp_registry"
    )
    registry_migration_database_url: str = (
        "postgresql+psycopg://erp_owner:erp_owner_dev@localhost:55432/erp_registry"
    )
    # Server key -> host:port. Tenants record their server key, so more
    # servers ("cells") can be added later.
    tenant_db_servers: dict[str, str] = {"default": "localhost:55432"}
    tenant_db_prefix: str = "erp_t_"
    tenant_db_app_user: str = "erp_app"
    tenant_db_app_password: str = "erp_app_dev"
    tenant_db_relay_user: str = "erp_relay"
    tenant_db_relay_password: str = "erp_relay_dev"
    tenant_db_owner_user: str = "erp_owner"
    tenant_db_owner_password: str = "erp_owner_dev"

    @classmethod
    @cache
    def load(cls) -> Self:
        """Process-wide settings.

        Tests reset it with Settings.load.cache_clear().
        """
        return cls()
