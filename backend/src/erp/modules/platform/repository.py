"""Repositories for platform tables in tenant databases."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from erp.modules.platform.models import Company


class CompanyRepository:
    """All queries on platform "Companies"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, company: Company) -> None:
        self._session.add(company)
        self._session.flush()

    def page(self, *, limit: int, after: UUID | None) -> tuple[list[Company], UUID | None]:
        """Keyset page ordered by companyId (uuidv7 is time-ordered)."""
        stmt = select(Company).order_by(Company.company_id).limit(limit + 1)
        if after is not None:
            stmt = stmt.where(Company.company_id > after)
        rows = list(self._session.scalars(stmt))
        items = rows[:limit]
        next_cursor = items[-1].company_id if len(rows) > limit else None
        return items, next_cursor
