from typing import Annotated, Self
from uuid import UUID

from fastapi import Depends

from erp.core.db import Database
from erp.modules.platform.context import RequestContext
from erp.modules.platform.dependencies import (
    TenantContextProvider,
    TenantDatabaseProvider,
)
from erp.modules.platform.repository import CompanyRepository
from erp.modules.platform.schemas import CompanyOut, CompanyPage


class CompanyService:
    """Company use cases within the request's tenant."""

    def __init__(self, database: Database, context: RequestContext) -> None:
        self._database = database
        self._context = context

    @classmethod
    def provide(
        cls,
        context: Annotated[RequestContext, Depends(TenantContextProvider.resolve)],
        database: Annotated[Database, Depends(TenantDatabaseProvider.resolve)],
    ) -> Self:
        return cls(database, context)

    def list_page(self, *, limit: int, cursor: UUID | None) -> CompanyPage:
        with self._database.tenant_session(self._context.tenant_id) as s:
            companies, next_cursor = CompanyRepository(s).page(limit=limit, after=cursor)
            items = [CompanyOut.model_validate(c) for c in companies]
        return CompanyPage(items=items, next_cursor=next_cursor)
