from fastapi import FastAPI

from erp.core.controller import Controller


class HealthController(Controller):
    def register_routes(self) -> None:
        self.router.add_api_route(
            "/healthz", self.healthz, methods=["GET"], include_in_schema=False
        )

    def healthz(self) -> dict[str, str]:
        return {"status": "ok"}


class ApplicationFactory:
    """Build the FastAPI application from its collaborators."""

    def build(self) -> FastAPI:
        app = FastAPI(title="Karmevo ERP API", version="0.1.0")
        app.include_router(HealthController().router)
        return app
