from uuid import UUID

from erp.shared.schemas import ApiSchema


class TenantChoiceOut(ApiSchema):
    tenant_id: UUID
    account_number: str
    tenant_name: str


class CompanyOut(ApiSchema):
    company_id: UUID
    company_name: str
    country_code: str
    base_currency: str
    time_zone: str


class CompanyPage(ApiSchema):
    items: list[CompanyOut]
    next_cursor: UUID | None
