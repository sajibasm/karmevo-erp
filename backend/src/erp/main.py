"""Process entry point.

Run with: uvicorn --factory erp.main:ProductionApp.build
"""

from fastapi import FastAPI

from erp.app import ApplicationFactory
from erp.core.config import Settings
from erp.core.db import Database, DbCredentials, TenantDbLocator
from erp.core.security import JwksKeyResolver, TokenVerifier
from erp.modules.platform.interface import TenantDatabaseRouter


class ProductionApp:
    """Wire the application from environment settings."""

    @staticmethod
    def build() -> FastAPI:
        settings = Settings.load()
        registry = Database(settings.registry_database_url)
        locator = TenantDbLocator(
            settings.tenant_db_servers, database_prefix=settings.tenant_db_prefix
        )
        tenant_router = TenantDatabaseRouter(
            registry,
            locator,
            DbCredentials(settings.tenant_db_app_user, settings.tenant_db_app_password),
        )
        verifier = TokenVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            algorithms=settings.oidc_algorithms,
            key_resolver=JwksKeyResolver(settings.oidc_jwks_url),
        )
        return ApplicationFactory(
            registry=registry, tenant_router=tenant_router, verifier=verifier
        ).build()
