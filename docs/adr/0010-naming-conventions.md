# 0010 — Naming conventions: PEP 8 Python, CamelCase database

**Status:** Accepted 2026-09-22 (owner decision) · **Applies to:** all backend code, migrations and SQL

## Python: PEP 8
- PEP 8 layout and naming, enforced by ruff:
  - `E`, `W`: pycodestyle
  - `N`: pep8-naming
  - `F`: pyflakes
  - `I`: import sorting
  - `B`: bugbear
  - `UP`: pyupgrade
- Line length: code lines ≤ 99 characters (the maximum PEP 8 allows a team to agree on). Comments and docstrings ≤ 72 characters (PEP 8), enforced as `W505` via `max-doc-length = 72`.
- Names:
  - `snake_case`: functions, methods, variables, modules, **ORM attributes**
  - `PascalCase`: classes
  - `UPPER_CASE`: constants
- Imports are grouped stdlib → third-party → first-party, and there are no wildcard imports.
- `ruff format` wraps code. Long string literals, comments and docstrings must be wrapped by hand.

## Database: CamelCase
| Object | Convention | Example |
|---|---|---|
| Schema | lowercase (module key) | `registry`, `platform`, `sales` |
| Table | **PascalCase, plural** | `"Tenants"`, `"SalesOrders"`, `"AuditEvents"` |
| Column | **camelCase** | `"accountNumber"`, `"createdAt"` |
| Primary key | spelled out: `<singular entity>Id` — never bare `id` | `"Tenants"."tenantId"`, `"SalesOrders"."salesOrderId"` |
| Foreign key column | **same name as the referenced column** whenever possible | `"Branches"."companyId"` → `"Companies"."companyId"` |
| FK with a role (two FKs to one table) | role prefix + referenced name | `"actorIdentityId"`, `"approverIdentityId"` |
| Other columns | **unambiguous**: qualify generic words (`name`, `status`, `type`, `code`, `date`, `amount`, `value`) with the entity or meaning | `"companyName"`, `"tenantStatus"`, `"branchCode"`, `"orderDate"` |
| Booleans | `is…` / `has…` | `"isEnabled"`, `"isSingleton"` |
| Timestamps | `…At` (UTC `timestamptz`); dates `…Date` | `"createdAt"`, `"dispatchedAt"`, `"invoiceDate"` |
| Constraints / indexes | `pk_<Table>`, `uq_<Table>_<cols>`, `fk_<Table>_<cols>_<RefTable>`, `ck_<Table>_<name>`, `ix_<Table>_<name>` (≤ 63 bytes) | `fk_Branches_tenantId_companyId_Companies` |
| RLS policies | camelCase | `"tenantIsolation"`, `"identitySelfRead"` |
| Databases, roles, GUC settings | lowercase (not tables or columns) | `erp_t_<hex>`, `erp_app`, `app.tenant_id` |

## Consequences
- **PostgreSQL folds unquoted identifiers to lowercase.** Every table and column name must be **double-quoted** in raw SQL, RLS policies, grants, `psql`, BI/reporting tools and `text()` statements: `SELECT "companyName" FROM platform."Companies"`. An unquoted `companyName` silently becomes `companyname` and fails.
- Prefer ORM or SQLAlchemy Core expressions, which quote automatically. In raw SQL, use `RlsSql.table_ref(schema, table)` (class-based per ADR-0011) for qualified names. Reviews should reject unquoted mixed-case identifiers.
- The ORM keeps PEP 8 attribute names and maps each to its column explicitly, e.g. `company_name: Mapped[str] = mapped_column("companyName", String(200))`. Constraint definitions (`UniqueConstraint`, `CheckConstraint` SQL, `ForeignKey` strings, `index_elements`) use the **database** names.

## API JSON: camelCase (owner decision 2026-09-22)
- Every request/response model inherits `erp.shared.schemas.ApiSchema`, a Pydantic base with `alias_generator=to_camel`, `populate_by_name=True` and `from_attributes=True`. Python fields stay snake_case (PEP 8); JSON is camelCase: `company_name` ↔ `"companyName"`, `next_cursor` ↔ `"nextCursor"`. FastAPI serializes by alias by default (`response_model_by_alias=True`). Don't disable that.
- Multi-word query parameters are camelCase too, declared with an alias: `page_size: Annotated[int, Query(alias="pageSize")]`.
- Error bodies keep the RFC 9457 member names (`type`, `title`, `status`, `detail`). Our extension members are camelCase (`code`, `errors`, and any future `retryAfter`, `requestId`). Validation `errors[].loc` reports the camelCase field names clients sent.
- Enum-like string *values* stay as defined by each API (e.g. `"active"`, `"MODULE_DISABLED"` codes). Casing rules apply to keys, not values.
- HTTP headers keep HTTP conventions (`X-Tenant-Id`, `Idempotency-Key`).
- Generated TypeScript and Dart clients therefore use the JSON names directly (`companyName`), with no mapping layer.
