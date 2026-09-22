import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData
from sqlalchemy import text as sql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Constraint names follow ADR-0010,
# e.g. fk_Branches_tenantId_companyId_Companies.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class RegistryBase(DeclarativeBase):
    """Tables in the central registry database (ADR-0002)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class TenantBase(DeclarativeBase):
    """Tables in each tenant's own database (ADR-0002)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class Columns:
    """Mapped-column factories that follow ADR-0010 names."""

    DATABASE_OWNER_FK = "platform.DatabaseOwners.tenantId"

    @staticmethod
    def uuid_pk(column: str) -> Mapped[uuid.UUID]:
        """A uuidv7 primary key with a spelled-out name."""
        return mapped_column(column, primary_key=True, server_default=sql("uuidv7()"))

    @staticmethod
    def timestamp(column: str) -> Mapped[datetime]:
        return mapped_column(column, server_default=sql("now()"))

    @classmethod
    def created_at(cls) -> Mapped[datetime]:
        return cls.timestamp("createdAt")

    @classmethod
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        """The "tenantId" FK carried by every tenant-database table."""
        return mapped_column("tenantId", ForeignKey(cls.DATABASE_OWNER_FK))
