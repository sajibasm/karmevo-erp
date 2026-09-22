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

    @classmethod
    @cache
    def load(cls) -> Self:
        """Process-wide settings.

        Tests reset it with Settings.load.cache_clear().
        """
        return cls()
