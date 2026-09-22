from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from erp.core.controller import Controller
from erp.core.deps import Authentication
from erp.core.security import VerifiedToken
from erp.modules.platform.context import TenantContextService
from erp.modules.platform.schemas import CompanyPage, TenantChoiceOut
from erp.modules.platform.service import CompanyService


class MeController(Controller):
    prefix = "/api/v1/me"
    tags = ("platform",)

    def register_routes(self) -> None:
        self.router.add_api_route("/contexts", self.list_contexts, methods=["GET"])

    def list_contexts(
        self,
        token: Annotated[VerifiedToken, Depends(Authentication.current_token)],
        service: Annotated[TenantContextService, Depends(TenantContextService.provide)],
    ) -> list[TenantChoiceOut]:
        return [TenantChoiceOut.model_validate(c) for c in service.choices(token)]


class CompanyController(Controller):
    prefix = "/api/v1/companies"
    tags = ("platform",)

    def register_routes(self) -> None:
        self.router.add_api_route("", self.list_companies, methods=["GET"])

    def list_companies(
        self,
        service: Annotated[CompanyService, Depends(CompanyService.provide)],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        cursor: UUID | None = None,
    ) -> CompanyPage:
        return service.list_page(limit=limit, cursor=cursor)
