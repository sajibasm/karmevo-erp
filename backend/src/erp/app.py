from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from erp.core.controller import Controller
from erp.core.db import Database
from erp.core.errors import ErrorHandlers
from erp.core.security import TokenVerifier
from erp.modules.platform.controller import CompanyController, MeController
from erp.modules.platform.interface import TenantDatabaseRouter


class HealthController(Controller):
    """Liveness and readiness probes (OPS-04)."""

    def __init__(self, registry: Database | None) -> None:
        self._registry = registry
        super().__init__()

    def register_routes(self) -> None:
        for path, endpoint in (("/healthz", self.healthz), ("/readyz", self.readyz)):
            self.router.add_api_route(path, endpoint, methods=["GET"], include_in_schema=False)

    def healthz(self) -> dict[str, str]:
        return {"status": "ok"}

    def readyz(self) -> JSONResponse:
        if self._registry is None:
            return JSONResponse({"status": "not_configured"}, status_code=503)
        with self._registry.platform_session() as session:
            session.execute(text("select 1"))
        return JSONResponse({"status": "ready"})


class ApplicationFactory:
    """Build the FastAPI application from its collaborators."""

    def __init__(
        self,
        *,
        registry: Database | None = None,
        tenant_router: TenantDatabaseRouter | None = None,
        verifier: TokenVerifier | None = None,
    ) -> None:
        self._registry = registry
        self._tenant_router = tenant_router
        self._verifier = verifier

    def build(self) -> FastAPI:
        app = FastAPI(title="Karmevo ERP API", version="0.1.0")
        app.state.registry = self._registry
        app.state.tenant_router = self._tenant_router
        app.state.verifier = self._verifier
        ErrorHandlers.install(app)
        app.include_router(HealthController(self._registry).router)
        for controller in (MeController(), CompanyController()):
            app.include_router(controller.router)
        return app
