# P1.1a Foundation Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running FastAPI ERP skeleton where **each tenant has its own PostgreSQL database**. A central registry decides who belongs to which tenant, a router sends each request to that tenant's database, and a **module system** lets each tenant enable or disable apps according to their declared dependencies. Everything is covered by tests:
- idempotent tenant-database provisioning, plus an upgrade runner that survives one broken tenant
- defence-in-depth isolation inside each tenant DB
- Keycloak-compatible token verification and tenant selection from verified membership
- stable problem+json errors, camelCase JSON and decimal conventions
- append-only audit
- a per-tenant outbox with exactly-once consumer effects
- per-tenant module enablement enforced on every module endpoint

**Architecture:**
- **Databases** (ADR-0002). The **registry DB** (`erp_registry`, schema `registry`) holds tenants and their placement, identities, memberships and enabled modules. Each **tenant DB** (`erp_t_<uuid hex>`) holds business data in module schemas; every tenant table keeps `"tenantId"` + `FORCE ROW LEVEL SECURITY` + an FK to the single-row `platform."DatabaseOwners"`.
- **Modules** (ADR-0009). Each module is a package with a manifest that declares its dependencies and controllers. `erp/core` holds framework infrastructure and `erp/shared` holds cross-module building blocks.
- **Code structure** (ADR-0011). Everything is a class. Requests flow Controller → Service → Repository → Model, and collaborators arrive through `__init__`.
- **Naming** (ADR-0010). Python is PEP 8 (snake_case attributes). The database is CamelCase: plural PascalCase tables, camelCase columns. API JSON is camelCase through `ApiSchema`.
- **Tooling.** Two Alembic trees. Sync SQLAlchemy 2 + psycopg 3 (ADR-0003).
- **Roles:**
  - runtime `erp_app`: NOBYPASSRLS, no DDL
  - migrations and provisioning `erp_owner`: CREATEDB, operator tool only
  - outbox relay `erp_relay`

**Tech Stack:** Python 3.13 (via uv), FastAPI, Pydantic ≥ 2.11, SQLAlchemy 2, psycopg 3, Alembic, pydantic-settings, PyJWT[crypto], pytest, httpx, ruff, import-linter; Docker Compose with `postgres:18` and Keycloak.

**Spec:** `ERP_Coding_Agent_Requirements.md` (v2.3), `docs/plan/00-implementation-plan.md`, `docs/adr/0001`–`0011` (0002, 0004, 0010, 0011 accepted; 0009 proposed), `docs/plan/module-dependencies.md` (proposal; not encoded in this slice).

## Global Constraints

- **Class-based code (ADR-0011).** There are no module-level functions in `backend/src/erp/`; helpers are `@staticmethod`/`@classmethod` on a named class. Module-level *constants*, type aliases and manifest objects are allowed. Allowed exceptions:
  - Alembic `upgrade()`/`downgrade()`
  - the `if __name__ == "__main__":` line
  - pytest test functions and fixtures

  Layers are Controller (HTTP only) → Service (rules and transactions) → Repository (every query) → Model. Services never build queries.
- **Python follows PEP 8** (ADR-0010), enforced by ruff rules `E`, `W`, `N`, `F`, `I`, `B`, `UP`. Code lines are ≤ 99 characters; comments and docstrings ≤ 72 (`W505`). Before every commit run `cd backend && uv run ruff format . && uv run ruff check .`. `ruff format` wraps code; strings, comments and docstrings must be wrapped by hand.
- **Database naming is CamelCase** (ADR-0010):
  - tables are plural PascalCase (`"Tenants"`)
  - columns are camelCase (`"tenantName"`)
  - primary keys are spelled out (`"tenantId"`)
  - FK columns have the same name as the column they reference
  - generic words are qualified (`"companyName"`)
  - schemas, databases and roles are lowercase

  **Every table and column must be double-quoted in raw SQL.** ORM attributes are snake_case and map explicitly: `mapped_column("companyName", …)`.
- **API JSON is camelCase** (ADR-0010). All API models inherit `erp.shared.schemas.ApiSchema`, so Python fields stay snake_case and JSON keys are camelCase (`nextCursor`). Headers keep HTTP style (`X-Tenant-Id`).
- Tenant context comes from verified identity + membership, never a freely trusted header (TEN-03). `X-Tenant-Id` is only a *selection* validated against active memberships in the registry.
- Each tenant's business data lives only in its own database. Cross-tenant data lives only in the registry DB.
- A tenant database that was ever migrated is never silently re-created. If it is missing, it must be restored from backup.
- "Module dependencies and entitlements must be enforced server-side. Disabling a module preserves historical data" (PLT-05). Modules import other modules only through `erp.modules.<other>.interface`.
- "Do not use floating point for authoritative monetary calculations" (PLT-06). Decimals are sent as JSON strings, and floats are rejected.
- "Validate issuer, signature, audience, expiry and appropriate token claims; support key rotation" (IAM-02).
- "Store an outbox record in the same transaction when external work must follow… consumers deduplicate and retry safely" (ARC-03).
- "Financial and stock records are never casually hard-deleted" (§20). `erp_app` gets no DELETE by default.
- Dependencies are added with `uv add` so `uv.lock` pins current versions (OPS-07). Never hand-write exact versions. Lower bounds (e.g. `pydantic>=2.11`) are allowed where a feature needs them.
- The Keycloak image tag is pinned in `deploy/.env` from the official release page. Never use `latest`.
- Dev credentials in `deploy/` are development-only. All commands run from the repo root unless a step says `cd backend`.

## Schema produced by this slice

```
registry DB (erp_registry)          schema registry
  "Tenants"        tenantId PK, accountNumber UQ, tenantName, tenantStatus, databaseServer,
                   databaseName UQ, databaseStatus, schemaRevision, lastMigrationError, createdAt
  "Identities"     identityId PK, issuer, subject (UQ issuer+subject), createdAt
  "Memberships"    membershipId PK, tenantId FK, identityId FK, membershipKind, membershipStatus,
                   createdAt
  "TenantModules"  tenantId FK + moduleKey PK, isEnabled, changedAt
tenant DB (erp_t_<hex>)             schemas platform, integration
  platform."DatabaseOwners"      isSingleton PK, tenantId UQ         (exactly one row)
  platform."Companies"           companyId PK, tenantId FK, companyName, countryCode,
                                 baseCurrency, timeZone, createdAt
  platform."Branches"            branchId PK, tenantId FK, companyId FK, branchCode, branchName,
                                 createdAt
  platform."AuditEvents"         auditEventId PK, tenantId FK, occurredAt, actorIdentityId,
                                 auditAction, targetType, targetId, auditOutcome, auditReason,
                                 auditDetails
  integration."OutboxEvents"     outboxEventId PK, tenantId FK, eventTopic, eventPayload,
                                 occurredAt, dispatchedAt, attemptCount, lastError
  integration."ProcessedEvents"  consumerName + eventId PK, tenantId FK, processedAt
```

## Class map

```
erp/app.py                     HealthController, ApplicationFactory
erp/main.py                    ProductionApp                       (uvicorn factory)
erp/cli.py                     Cli                                 (operator commands)
erp/model_registry.py          imports every model module          (no code)
erp/module_catalog.py          InstalledModules
erp/core/controller.py         Controller                          (base class)
erp/core/errors.py             DomainError + subclasses, Problem, ErrorHandlers
erp/core/config.py             Settings                            (Settings.load())
erp/core/db.py                 Database, SqlIdentifier, DbCredentials, TenantDbLocator
erp/core/models.py             RegistryBase, TenantBase, Columns
erp/core/migrations.py         AlembicEnvironment, MigrationColumns
erp/core/rls.py                RlsSql
erp/core/security.py           VerifiedToken, TokenVerifier, JwksKeyResolver
erp/core/deps.py               RequestState, Authentication
erp/core/modules.py            ModuleManifest, ModuleCatalog, ModuleCatalogError
erp/shared/money.py            Money, DecimalStr (type alias)
erp/shared/schemas.py          ApiSchema
erp/modules/platform/
  registry_models.py           Tenant, Identity, Membership, TenantModule
  registry_repository.py       TenantRepository, IdentityRepository, MembershipRepository,
                               TenantModuleRepository
  models.py                    DatabaseOwner, Company, Branch, AuditEvent
  repository.py                CompanyRepository, AuditEventRepository
  schemas.py                   TenantChoiceOut, CompanyOut, CompanyPage
  provisioning.py              TenantDatabaseAdmin, TenantMigrator, TenantProvisioner, …
  tenant_db.py                 TenantDatabaseRouter, TenantUnavailableError
  context.py                   RequestContext, TenantChoice, TenantContextService
  dependencies.py              TenantContextProvider, TenantDatabaseProvider, ModuleGuard
  service.py                   CompanyService
  controller.py                MeController, CompanyController
  audit.py                     Redactor, AuditTrail
  module_state.py              TenantModules, ModuleDisabledError, ModuleChangeRejectedError
  module.py / interface.py     MODULE manifest / public surface
erp/modules/integration/
  models.py                    OutboxEvent, ProcessedEvent
  repository.py                OutboxEventRepository, ProcessedEventRepository
  outbox.py                    OutboxMessage, Outbox, OutboxRelay, TenantOutboxRelay, EventInbox
  module.py                    MODULE manifest
```

---

### Task 1: Repository scaffold, controller base, application factory

**Files:**
- Create: `.gitignore`, `backend/pyproject.toml` (via `uv init`), `backend/src/erp/__init__.py`, `backend/src/erp/core/__init__.py`, `backend/src/erp/core/controller.py`, `backend/src/erp/app.py`
- Test: `backend/tests/core/test_health.py`

**Interfaces:**
- Produces:
  - `Controller`: class attributes `prefix`, `tags`; `self.router: APIRouter`; subclasses implement `register_routes()`.
  - `ApplicationFactory().build() -> FastAPI` with `GET /healthz`. Constructor arguments are added in Tasks 8 and 11.

- [ ] **Step 1: Initialise git and ignore rules**

```bash
git init
cat > .gitignore <<'EOF'
.DS_Store
.idea/workspace.xml
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
deploy/.env
EOF
```

- [ ] **Step 2: Install uv and create the backend project**

```bash
brew install uv
mkdir -p backend && cd backend
uv init --lib --name erp --python 3.13 .
uv add fastapi "pydantic>=2.11" "uvicorn[standard]" sqlalchemy "psycopg[binary]" alembic pydantic-settings "pyjwt[crypto]"
uv add --dev pytest httpx ruff
```

Expected: `backend/pyproject.toml`, `backend/uv.lock`, `backend/src/erp/__init__.py`, `backend/.python-version` exist.

- [ ] **Step 3: Configure pytest and ruff (PEP 8)**

Append to `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["tests"]
addopts = "-ra --import-mode=importlib"

[tool.ruff]
# PEP 8: up to 99 characters for code (the maximum a team may agree on).
line-length = 99
target-version = "py313"

[tool.ruff.lint]
# PEP 8 via pycodestyle (E, W) and pep8-naming (N); plus pyflakes (F),
# import grouping (I), bugbear (B) and pyupgrade (UP).
select = ["E", "W", "N", "F", "I", "B", "UP"]

[tool.ruff.lint.pycodestyle]
max-doc-length = 72  # PEP 8: comments and docstrings wrap at 72

[tool.ruff.lint.per-file-ignores]
# Migrations alias MigrationColumns as `cols` for readable column lists.
"migrations/**" = ["N813"]
```

Replace the generated `backend/src/erp/__init__.py` with:

```python
"""Karmevo ERP backend."""
```

`backend/src/erp/core/__init__.py`:

```python
"""Framework infrastructure (ADR-0009)."""
```

- [ ] **Step 4: Write the failing test**

`backend/tests/core/test_health.py`:

```python
from fastapi.testclient import TestClient

from erp.app import ApplicationFactory


def test_healthz_returns_ok():
    client = TestClient(ApplicationFactory().build())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.app'`

- [ ] **Step 6: Implement the controller base and the factory**

`backend/src/erp/core/controller.py`:

```python
from typing import ClassVar

from fastapi import APIRouter


class Controller:
    """Base for class-based controllers (ADR-0011).

    Subclasses set `prefix` and `tags` and register their bound methods
    as routes in `register_routes()`.
    """

    prefix: ClassVar[str] = ""
    tags: ClassVar[tuple[str, ...]] = ()

    def __init__(self) -> None:
        self.router = APIRouter(prefix=self.prefix, tags=list(self.tags))
        self.register_routes()

    def register_routes(self) -> None:
        raise NotImplementedError
```

`backend/src/erp/app.py`:

```python
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
```

- [ ] **Step 7: Run tests and lint**

Run: `cd backend && uv run pytest -v && uv run ruff format . && uv run ruff check .`
Expected: `1 passed`; ruff reports no errors.

- [ ] **Step 8: Commit**

```bash
git add .gitignore CLAUDE.md ERP_Coding_Agent_Requirements.md docs backend
git commit -m "chore: scaffold backend with controller base and app factory"
```

---

### Task 2: Problem+json errors, camelCase API schemas, decimal conventions

**Files:**
- Create: `backend/src/erp/core/errors.py`, `backend/src/erp/shared/__init__.py`, `backend/src/erp/shared/money.py`, `backend/src/erp/shared/schemas.py`
- Modify: `backend/src/erp/app.py`
- Test: `backend/tests/core/test_errors.py`, `backend/tests/shared/test_money.py`, `backend/tests/shared/test_schemas.py`

**Interfaces:**
- Produces:
  - `DomainError(detail, *, code=None)` with subclasses `UnauthenticatedError` (401), `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409), `ServiceUnavailableError` (503).
  - `Problem.response(...)` and `ErrorHandlers.install(app)`.
  - `Money.quantize(amount, currency, rounding=ROUND_HALF_UP)`, `Money.MINOR_UNITS`, `DecimalStr`.
  - `ApiSchema` (snake_case fields ↔ camelCase JSON).

- [ ] **Step 1: Write the failing tests**

`backend/tests/core/test_errors.py`:

```python
from fastapi.testclient import TestClient

from erp.app import ApplicationFactory
from erp.core.errors import ConflictError
from erp.shared.money import DecimalStr
from erp.shared.schemas import ApiSchema


class PricePayload(ApiSchema):
    unit_price: DecimalStr


def _client():
    app = ApplicationFactory().build()

    @app.get("/_test/conflict")
    def conflict() -> None:
        raise ConflictError("version mismatch", code="VERSION_CONFLICT")

    @app.post("/_test/echo")
    def echo(payload: PricePayload) -> PricePayload:
        return payload

    return TestClient(app)


def test_domain_error_is_rendered_as_problem_json():
    response = _client().get("/_test/conflict")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "code": "VERSION_CONFLICT",
        "detail": "version mismatch",
    }


def test_decimal_round_trips_as_string_with_camel_case_key():
    response = _client().post("/_test/echo", json={"unitPrice": "10.50"})

    assert response.status_code == 200
    assert response.json() == {"unitPrice": "10.50"}


def test_float_amount_is_rejected_with_validation_code():
    response = _client().post("/_test/echo", json={"unitPrice": 10.5})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert body["errors"][0]["loc"] == ["body", "unitPrice"]
```

`backend/tests/shared/test_money.py`:

```python
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from erp.shared.money import Money


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        ("10.005", "BDT", "10.01"),
        ("10.004", "BDT", "10.00"),
        ("1234.5", "JPY", "1235"),
        ("1.0005", "KWD", "1.001"),
    ],
)
def test_quantize_uses_currency_minor_units(amount, currency, expected):
    assert Money.quantize(Decimal(amount), currency) == Decimal(expected)


def test_rounding_mode_is_explicit():
    rounded = Money.quantize(Decimal("10.005"), "BDT", ROUND_HALF_EVEN)

    assert rounded == Decimal("10.00")


def test_unknown_currency_is_rejected():
    with pytest.raises(ValueError, match="unsupported currency"):
        Money.quantize(Decimal("1"), "XYZ")
```

`backend/tests/shared/test_schemas.py`:

```python
from erp.shared.schemas import ApiSchema


class Sample(ApiSchema):
    company_name: str
    next_cursor: str | None = None


def test_dumps_camel_case_keys():
    dumped = Sample(company_name="Alpha").model_dump(mode="json")

    assert dumped == {"companyName": "Alpha", "nextCursor": None}


def test_accepts_camel_case_and_snake_case_input():
    assert Sample.model_validate({"companyName": "A"}).company_name == "A"
    assert Sample.model_validate({"company_name": "A"}).company_name == "A"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/test_errors.py tests/shared -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.core.errors'`

- [ ] **Step 3: Implement**

`backend/src/erp/core/errors.py`:

```python
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Error with a stable API `code` (ADR-0006)."""

    status: int = 400
    code: str = "BAD_REQUEST"
    title: str = "Bad request"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class UnauthenticatedError(DomainError):
    status, code, title = 401, "UNAUTHENTICATED", "Authentication required"


class ForbiddenError(DomainError):
    status, code, title = 403, "FORBIDDEN", "Forbidden"


class NotFoundError(DomainError):
    status, code, title = 404, "NOT_FOUND", "Not found"


class ConflictError(DomainError):
    status, code, title = 409, "CONFLICT", "Conflict"


class ServiceUnavailableError(DomainError):
    status, code, title = 503, "SERVICE_UNAVAILABLE", "Service unavailable"


class Problem:
    """RFC 9457 problem+json responses (ADR-0006)."""

    MEDIA_TYPE = "application/problem+json"

    @classmethod
    def response(
        cls,
        status: int,
        code: str,
        title: str,
        detail: str,
        errors: list[dict[str, Any]] | None = None,
    ) -> JSONResponse:
        body: dict[str, Any] = {
            "type": "about:blank",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
        }
        if errors is not None:
            body["errors"] = errors
        return JSONResponse(body, status_code=status, media_type=cls.MEDIA_TYPE)


class ErrorHandlers:
    """Register the problem+json exception handlers on an app."""

    @classmethod
    def install(cls, app: FastAPI) -> None:
        app.add_exception_handler(DomainError, cls.domain_error)
        app.add_exception_handler(RequestValidationError, cls.validation_error)

    @staticmethod
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        response = Problem.response(exc.status, exc.code, exc.title, exc.detail)
        if exc.status == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @staticmethod
    async def validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return Problem.response(
            422, "VALIDATION_FAILED", "Validation failed", "Request is invalid", errors
        )
```

`backend/src/erp/shared/__init__.py`:

```python
"""Cross-module building blocks; never imports erp.modules."""
```

`backend/src/erp/shared/money.py`:

```python
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, ClassVar

from pydantic import BeforeValidator, PlainSerializer


class Money:
    """Decimal money helpers (PLT-06)."""

    # ISO 4217 minor units for the currencies enabled so far.
    # Add currencies deliberately; never guess.
    MINOR_UNITS: ClassVar[dict[str, int]] = {
        "BDT": 2,
        "USD": 2,
        "EUR": 2,
        "JPY": 0,
        "KWD": 3,
    }

    @classmethod
    def quantize(
        cls, amount: Decimal, currency: str, rounding: str = ROUND_HALF_UP
    ) -> Decimal:
        """Round to the currency's minor unit.

        Callers pass the rounding mode from the applicable tax or
        pricing policy; the default only keeps the policy visible at
        call sites.
        """
        try:
            places = cls.MINOR_UNITS[currency]
        except KeyError:
            raise ValueError(f"unsupported currency {currency!r}") from None
        return amount.quantize(Decimal(1).scaleb(-places), rounding=rounding)

    @staticmethod
    def reject_float(value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("decimal values must be sent as strings")
        return value


DecimalStr = Annotated[
    Decimal,
    BeforeValidator(Money.reject_float),
    PlainSerializer(str, return_type=str, when_used="json"),
]
```

`backend/src/erp/shared/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    """Base for API models: snake_case fields, camelCase JSON."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        from_attributes=True,
    )
```

Replace `backend/src/erp/app.py` with:

```python
from fastapi import FastAPI

from erp.core.controller import Controller
from erp.core.errors import ErrorHandlers


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
        ErrorHandlers.install(app)
        app.include_router(HealthController().router)
        return app
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: `12 passed` (1 health + 3 errors + 6 money + 2 schemas).

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat(core): problem+json errors, camelCase ApiSchema, Money"
```

---

### Task 3: Dev PostgreSQL, role model, `Database` and the registry migration tree

**Files:**
- Create: `deploy/compose.dev.yml`, `deploy/postgres/init/01-roles.sql`, `backend/src/erp/core/config.py`, `backend/src/erp/core/db.py`, `backend/src/erp/core/models.py`, `backend/src/erp/core/migrations.py`, `backend/alembic.ini`, `backend/migrations/registry/env.py`, `backend/migrations/registry/versions/r0001_registry_schema.py`, `backend/migrations/tenant/versions/` + `script.py.mako` copy, `backend/tests/conftest.py`, `backend/tests/support.py` (empty)
- Test: `backend/tests/core/test_db_roles.py`

**Interfaces:**
- Produces:
  - `Settings` with `Settings.load()` (cached; `Settings.load.cache_clear()`).
  - `Database(url, **engine_kwargs)` with `tenant_session(tenant_id)`, `platform_session(*, identity_id=None)`, `.engine`, `.dispose()`.
  - `RegistryBase`, `TenantBase`, and `Columns.uuid_pk(column)` / `timestamp(column)` / `created_at()` / `tenant_id()`.
  - `AlembicEnvironment(metadata, url).run()` and `MigrationColumns.uuid(column)` / `timestamp(column)` / `created_at()` / `registry_tenant_id(table)` / `owner_tenant_id(table)`.
  - Fixtures `registry_owner_engine`, `registry`, `single_connection_registry`, and helper `truncate_tables(engine, exclude)`.

- [ ] **Step 1: PostgreSQL service and roles**

`deploy/compose.dev.yml`:

```yaml
name: karmevo-dev
services:
  postgres:
    image: postgres:18
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres_dev
    ports: ["55432:5432"]
    volumes:
      - ./postgres/init:/docker-entrypoint-initdb.d:ro
      - pgdata:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 2s
      timeout: 3s
      retries: 30
volumes:
  pgdata:
```

`deploy/postgres/init/01-roles.sql`:

```sql
-- DEVELOPMENT-ONLY credentials. Deployment profiles provision their own roles and secrets.
-- erp_owner creates tenant databases (CREATEDB) and runs migrations; services never use it.
CREATE ROLE erp_owner LOGIN PASSWORD 'erp_owner_dev' NOSUPERUSER NOBYPASSRLS NOCREATEROLE CREATEDB;
CREATE ROLE erp_app   LOGIN PASSWORD 'erp_app_dev'   NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
CREATE ROLE erp_relay LOGIN PASSWORD 'erp_relay_dev' NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;

CREATE DATABASE erp_registry OWNER erp_owner;
CREATE DATABASE erp_registry_test OWNER erp_owner;

REVOKE CONNECT ON DATABASE erp_registry, erp_registry_test FROM PUBLIC;
GRANT CONNECT ON DATABASE erp_registry, erp_registry_test TO erp_app;
```

Run: `docker compose -f deploy/compose.dev.yml up -d --wait`
Expected: `Container karmevo-dev-postgres-1  Healthy`. Init scripts only run on an empty volume. If one exists from an earlier layout, run `docker compose -f deploy/compose.dev.yml down -v` first.

- [ ] **Step 2: Settings, bases, `Database`, migration helpers**

`backend/src/erp/core/config.py`:

```python
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
```

`backend/src/erp/core/models.py`:

```python
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
        return mapped_column(
            column, primary_key=True, server_default=sql("uuidv7()")
        )

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
```

`backend/src/erp/core/db.py`:

```python
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """One engine (one physical database) with explicit transactions.

    Tenant and identity context are transaction-local, so a pooled
    connection never carries one request's context into the next; this
    also works with PgBouncer transaction pooling (ADR-0002).
    """

    SET_LOCAL = text("select set_config(:name, :value, true)")

    def __init__(self, url: str | URL, **engine_kwargs: Any) -> None:
        self.engine = create_engine(url, pool_pre_ping=True, **engine_kwargs)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def tenant_session(self, tenant_id: UUID) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._set_local(session, "app.tenant_id", str(tenant_id))
            yield session

    @contextmanager
    def platform_session(
        self, *, identity_id: UUID | None = None
    ) -> Iterator[Session]:
        """A transaction without tenant context.

        Tenant-owned tables return no rows in it.
        """
        with self._sessions() as session, session.begin():
            if identity_id is not None:
                self._set_local(session, "app.identity_id", str(identity_id))
            yield session

    def dispose(self) -> None:
        self.engine.dispose()

    @classmethod
    def _set_local(cls, session: Session, name: str, value: str) -> None:
        session.execute(cls.SET_LOCAL, {"name": name, "value": value})
```

`backend/src/erp/core/migrations.py`:

```python
import sqlalchemy as sa
from alembic import context
from sqlalchemy import MetaData, create_engine, pool


class AlembicEnvironment:
    """Run one Alembic environment for a metadata set and URL."""

    def __init__(self, metadata: MetaData, url: str) -> None:
        self._metadata = metadata
        self._url = url

    def run(self) -> None:
        if context.is_offline_mode():
            self._run_offline()
        else:
            self._run_online()

    def _run_offline(self) -> None:
        context.configure(
            url=self._url,
            target_metadata=self._metadata,
            literal_binds=True,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    def _run_online(self) -> None:
        engine = create_engine(self._url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=self._metadata,
                include_schemas=True,
            )
            with context.begin_transaction():
                context.run_migrations()


class MigrationColumns:
    """sa.Column factories for migrations, named per ADR-0010."""

    @staticmethod
    def uuid(column: str) -> sa.Column:
        return sa.Column(
            column, sa.Uuid(), nullable=False, server_default=sa.text("uuidv7()")
        )

    @staticmethod
    def timestamp(column: str) -> sa.Column:
        return sa.Column(
            column,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )

    @classmethod
    def created_at(cls) -> sa.Column:
        return cls.timestamp("createdAt")

    @staticmethod
    def registry_tenant_id(table: str) -> sa.Column:
        """FK column "tenantId" to registry "Tenants"."""
        return sa.Column(
            "tenantId",
            sa.Uuid(),
            sa.ForeignKey(
                "registry.Tenants.tenantId", name=f"fk_{table}_tenantId_Tenants"
            ),
            nullable=False,
        )

    @staticmethod
    def owner_tenant_id(table: str) -> sa.Column:
        """FK column "tenantId" to platform "DatabaseOwners"."""
        return sa.Column(
            "tenantId",
            sa.Uuid(),
            sa.ForeignKey(
                "platform.DatabaseOwners.tenantId",
                name=f"fk_{table}_tenantId_DatabaseOwners",
            ),
            nullable=False,
        )
```

- [ ] **Step 3: Two Alembic trees, registry schema migration**

```bash
cd backend
uv run alembic init --template generic migrations/registry
mkdir -p migrations/tenant/versions
cp migrations/registry/script.py.mako migrations/tenant/
rm -f migrations/registry/README
touch tests/support.py
```

Replace the generated `backend/alembic.ini` entirely with:

```ini
# Two migration trees (ADR-0002):
#   registry: uv run alembic -n registry upgrade head
#   tenant:   applied to every tenant database by
#             `python -m erp.cli upgrade-tenants`
[registry]
script_location = %(here)s/migrations/registry
sqlalchemy.url =

[tenant]
script_location = %(here)s/migrations/tenant
sqlalchemy.url =
```

Replace `backend/migrations/registry/env.py` with:

```python
"""Alembic environment for the central registry database."""

from alembic import context

from erp.core.config import Settings
from erp.core.migrations import AlembicEnvironment
from erp.core.models import RegistryBase

url = (
    context.config.get_main_option("sqlalchemy.url")
    or Settings.load().registry_migration_database_url
)
AlembicEnvironment(RegistryBase.metadata, url).run()
```

`backend/migrations/registry/versions/r0001_registry_schema.py`:

```python
"""registry schema and runtime grants"""

from alembic import op

revision = "r0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA registry")
    op.execute("GRANT USAGE ON SCHEMA registry TO erp_app")
    # No DELETE by default; deletable tables get an explicit grant.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA registry "
        "GRANT SELECT, INSERT, UPDATE ON TABLES TO erp_app"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA registry CASCADE")
```

- [ ] **Step 4: Test fixtures**

`backend/tests/conftest.py`:

```python
"""Shared fixtures.

Database tests need the dev stack:
docker compose -f deploy/compose.dev.yml up -d --wait
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from erp.core.db import Database

BACKEND_DIR = Path(__file__).resolve().parents[1]
REGISTRY_APP_URL = os.environ.get(
    "ERP_TEST_REGISTRY_URL",
    "postgresql+psycopg://erp_app:erp_app_dev@localhost:55432/erp_registry_test",
)
REGISTRY_OWNER_URL = os.environ.get(
    "ERP_TEST_REGISTRY_MIGRATION_URL",
    "postgresql+psycopg://erp_owner:erp_owner_dev@localhost:55432/erp_registry_test",
)


def truncate_tables(
    engine: Engine, *, exclude: frozenset[str] = frozenset()
) -> None:
    """Empty every application table except `exclude`.

    Names in `exclude` are quoted, e.g. 'registry."Tenants"'.
    """
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "select quote_ident(schemaname) || '.' || quote_ident(tablename) "
                "from pg_tables where schemaname not in "
                "('pg_catalog', 'information_schema', 'public')"
            )
        ).scalars().all()
        targets = [t for t in tables if t not in exclude]
        if targets:
            conn.execute(
                text(f"TRUNCATE {', '.join(targets)} RESTART IDENTITY CASCADE")
            )


@pytest.fixture(scope="session")
def registry_owner_engine() -> Iterator[Engine]:
    """Migrate erp_registry_test from scratch once per run.

    Starting with a downgrade also exercises every downgrade path.
    """
    cfg = Config(str(BACKEND_DIR / "alembic.ini"), ini_section="registry")
    cfg.set_main_option("sqlalchemy.url", REGISTRY_OWNER_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(REGISTRY_OWNER_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def _registry(registry_owner_engine: Engine) -> Iterator[Database]:
    database = Database(REGISTRY_APP_URL)
    yield database
    database.dispose()


@pytest.fixture
def registry(
    _registry: Database, registry_owner_engine: Engine
) -> Iterator[Database]:
    """Registry DB as erp_app; emptied after each test.

    "Tenants" rows are kept because session fixtures provision tenant
    databases for them.
    """
    yield _registry
    truncate_tables(
        registry_owner_engine, exclude=frozenset({'registry."Tenants"'})
    )


@pytest.fixture
def single_connection_registry(
    registry_owner_engine: Engine,
) -> Iterator[Database]:
    """A one-connection pool, to prove context never leaks."""
    database = Database(REGISTRY_APP_URL, pool_size=1, max_overflow=0)
    yield database
    database.dispose()
```

- [ ] **Step 5: Write the tests**

`backend/tests/core/test_db_roles.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

LEAK_CHECK = (
    "select pg_backend_pid(), "
    "nullif(current_setting('{name}', true), '')"
)


def test_runtime_role_is_not_superuser_and_cannot_bypass_rls(registry):
    with registry.platform_session() as s:
        row = s.execute(
            text(
                "select rolsuper, rolbypassrls from pg_roles "
                "where rolname = current_user"
            )
        ).one()
    assert (row.rolsuper, row.rolbypassrls) == (False, False)


def test_runtime_role_cannot_run_ddl(registry):
    with pytest.raises(DBAPIError, match="permission denied"):
        with registry.platform_session() as s:
            s.execute(text('create table registry."ShouldNotExist" ("value" int)'))


def test_tenant_context_is_visible_inside_its_transaction(registry):
    tenant_id = uuid4()
    with registry.tenant_session(tenant_id) as s:
        value = s.execute(text("select current_setting('app.tenant_id')")).scalar_one()
    assert value == str(tenant_id)


def test_tenant_context_does_not_leak_on_the_same_connection(
    single_connection_registry,
):
    with single_connection_registry.tenant_session(uuid4()) as s:
        first_pid = s.execute(text("select pg_backend_pid()")).scalar_one()
    with single_connection_registry.platform_session() as s:
        check = text(LEAK_CHECK.format(name="app.tenant_id"))
        pid, leaked = s.execute(check).one()
    assert pid == first_pid
    assert leaked is None


def test_tenant_context_is_cleared_after_rollback(single_connection_registry):
    with pytest.raises(RuntimeError):
        with single_connection_registry.tenant_session(uuid4()):
            raise RuntimeError("business rule failed")
    with single_connection_registry.platform_session() as s:
        check = text(LEAK_CHECK.format(name="app.tenant_id"))
        _, leaked = s.execute(check).one()
    assert leaked is None


def test_identity_context_is_transaction_local(single_connection_registry):
    identity_id = uuid4()
    database = single_connection_registry
    with database.platform_session(identity_id=identity_id) as s:
        inside = s.execute(
            text("select current_setting('app.identity_id')")
        ).scalar_one()
    with database.platform_session() as s:
        check = text(LEAK_CHECK.format(name="app.identity_id"))
        _, leaked = s.execute(check).one()
    assert inside == str(identity_id)
    assert leaked is None
```

- [ ] **Step 6: Run the tests**

Run: `cd backend && uv run pytest tests/core/test_db_roles.py -v`
Expected: `6 passed`. For strict test-first, write Step 5 before Step 2 and confirm `ModuleNotFoundError: No module named 'erp.core.db'` first.

- [ ] **Step 7: Commit**

```bash
git add deploy backend
git commit -m "feat(core): role model, transaction-local context, registry migrations"
```

---

### Task 4: Registry tables — "Tenants", "Identities", "Memberships"

**Files:**
- Create: `backend/src/erp/core/rls.py`, `backend/src/erp/modules/__init__.py`, `backend/src/erp/modules/platform/__init__.py` (both empty), `backend/src/erp/modules/platform/registry_models.py`, `backend/src/erp/model_registry.py`, `backend/migrations/registry/versions/r0002_registry_tenancy.py`
- Modify: `backend/migrations/registry/env.py`
- Test: `backend/tests/platform/test_registry.py`, `backend/tests/core/test_migrations.py`

**Interfaces:**
- Produces:
  - Registry models `Tenant` (`tenant_id, account_number, tenant_name, tenant_status, database_server, database_name, database_status, schema_revision, last_migration_error, created_at`), `Identity` (`identity_id, issuer, subject`) and `Membership` (`membership_id, tenant_id, identity_id, membership_kind, membership_status`).
  - `RlsSql.TENANT_EXPR`, `RlsSql.IDENTITY_EXPR`, `RlsSql.table_ref(schema, table)`, `RlsSql.tenant_policy(schema, table) -> list[str]`, `RlsSql.identity_read_policy(schema, table) -> str`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/platform/test_registry.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from erp.modules.platform.registry_models import Identity, Membership, Tenant


def _tenant(registry, name):
    """A registry row only (no database), for registry-level rules."""
    with registry.platform_session() as s:
        tenant = Tenant(
            account_number=f"R{uuid4().hex[:12]}",
            tenant_name=name,
            database_name=f"unprovisioned_{uuid4().hex}",
        )
        s.add(tenant)
        s.flush()
        return tenant.tenant_id


def _identity(registry, subject="alice"):
    with registry.platform_session() as s:
        identity = Identity(issuer="https://id.test/realms/staff", subject=subject)
        s.add(identity)
        s.flush()
        return identity.identity_id


def test_new_tenant_starts_in_provisioning_state(registry):
    tenant_id = _tenant(registry, "Alpha Traders")

    with registry.platform_session() as s:
        tenant = s.get(Tenant, tenant_id)
    assert (tenant.tenant_status, tenant.database_status) == ("active", "provisioning")
    assert tenant.database_server == "default"


def test_memberships_are_isolated_by_tenant_context(registry):
    a, b = _tenant(registry, "A"), _tenant(registry, "B")
    identity_id = _identity(registry)
    with registry.tenant_session(a) as s:
        s.add(Membership(tenant_id=a, identity_id=identity_id))

    with registry.tenant_session(a) as s:
        in_a = s.scalars(select(Membership)).all()
    with registry.tenant_session(b) as s:
        in_b = s.scalars(select(Membership)).all()

    assert len(in_a) == 1
    assert in_b == []


def test_cannot_create_membership_for_another_tenant(registry):
    a, b = _tenant(registry, "A"), _tenant(registry, "B")
    identity_id = _identity(registry)

    with pytest.raises(DBAPIError, match="row-level security"):
        with registry.tenant_session(a) as s:
            s.add(Membership(tenant_id=b, identity_id=identity_id))
            s.flush()


def test_identity_lists_own_memberships_without_tenant_context(registry):
    a = _tenant(registry, "A")
    identity_id = _identity(registry)
    with registry.tenant_session(a) as s:
        s.add(Membership(tenant_id=a, identity_id=identity_id))

    with registry.platform_session(identity_id=identity_id) as s:
        own = s.scalars(select(Membership.tenant_id)).all()
    with registry.platform_session() as s:
        anonymous = s.scalars(select(Membership)).all()

    assert own == [a]
    assert anonymous == []


def test_identity_is_unique_per_issuer_and_subject(registry):
    _identity(registry, "alice")

    with pytest.raises(IntegrityError):
        _identity(registry, "alice")
```

`backend/tests/core/test_migrations.py`:

```python
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import erp.model_registry  # noqa: F401
from erp.core.models import RegistryBase


def test_registry_models_match_migrations(registry_owner_engine):
    with registry_owner_engine.connect() as conn:
        context = MigrationContext.configure(
            conn, opts={"include_schemas": True}
        )
        assert compare_metadata(context, RegistryBase.metadata) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/platform/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.modules'`

- [ ] **Step 3: RLS SQL and registry models**

`backend/src/erp/core/rls.py`:

```python
class RlsSql:
    """Row-level security SQL for both migration trees (ADR-0002)."""

    # nullif(): after a transaction-local set_config() the setting reads
    # back as '' rather than NULL, so both mean "no context".
    TENANT_EXPR = "nullif(current_setting('app.tenant_id', true), '')::uuid"
    IDENTITY_EXPR = "nullif(current_setting('app.identity_id', true), '')::uuid"

    @staticmethod
    def table_ref(schema: str, table: str) -> str:
        """Quote a CamelCase table name for raw SQL (ADR-0010)."""
        return f'{schema}."{table}"'

    @classmethod
    def tenant_policy(cls, schema: str, table: str) -> list[str]:
        """Force RLS on a tenant table, limited to its tenant."""
        ref = cls.table_ref(schema, table)
        condition = f'"tenantId" = {cls.TENANT_EXPR}'
        return [
            f"ALTER TABLE {ref} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {ref} FORCE ROW LEVEL SECURITY",
            f'CREATE POLICY "tenantIsolation" ON {ref} '
            f"USING ({condition}) WITH CHECK ({condition})",
        ]

    @classmethod
    def identity_read_policy(cls, schema: str, table: str) -> str:
        """Let an identity read its own rows without tenant context."""
        return (
            f'CREATE POLICY "identitySelfRead" ON {cls.table_ref(schema, table)} '
            f'FOR SELECT USING ("identityId" = {cls.IDENTITY_EXPR})'
        )
```

`backend/src/erp/modules/platform/registry_models.py`:

```python
"""Registry database tables: cross-tenant data only (ADR-0002)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import Columns, RegistryBase

SCHEMA = {"schema": "registry"}


class Tenant(RegistryBase):
    """A client business account and where its database lives."""

    __tablename__ = "Tenants"
    __table_args__ = (
        CheckConstraint(
            "\"tenantStatus\" in ('active', 'suspended')", name="tenantStatus"
        ),
        CheckConstraint(
            "\"databaseStatus\" in ('provisioning', 'ready', 'failed')",
            name="databaseStatus",
        ),
        SCHEMA,
    )

    tenant_id: Mapped[uuid.UUID] = Columns.uuid_pk("tenantId")
    account_number: Mapped[str] = mapped_column(
        "accountNumber", String(32), unique=True
    )
    tenant_name: Mapped[str] = mapped_column("tenantName", String(200))
    tenant_status: Mapped[str] = mapped_column(
        "tenantStatus", String(16), server_default="active"
    )
    database_server: Mapped[str] = mapped_column(
        "databaseServer", String(64), server_default="default"
    )
    database_name: Mapped[str] = mapped_column(
        "databaseName", String(63), unique=True
    )
    database_status: Mapped[str] = mapped_column(
        "databaseStatus", String(16), server_default="provisioning"
    )
    schema_revision: Mapped[str | None] = mapped_column(
        "schemaRevision", String(32)
    )
    last_migration_error: Mapped[str | None] = mapped_column(
        "lastMigrationError", String(1000)
    )
    created_at: Mapped[datetime] = Columns.created_at()


class Identity(RegistryBase):
    """A signed-in person or client, keyed by issuer + subject."""

    __tablename__ = "Identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"), SCHEMA)

    identity_id: Mapped[uuid.UUID] = Columns.uuid_pk("identityId")
    issuer: Mapped[str] = mapped_column("issuer", String(500))
    subject: Mapped[str] = mapped_column("subject", String(255))
    created_at: Mapped[datetime] = Columns.created_at()


class Membership(RegistryBase):
    __tablename__ = "Memberships"
    __table_args__ = (
        UniqueConstraint("tenantId", "membershipId"),
        UniqueConstraint("tenantId", "identityId", "membershipKind"),
        CheckConstraint(
            "\"membershipKind\" in ('staff', 'buyer', 'service')",
            name="membershipKind",
        ),
        CheckConstraint(
            "\"membershipStatus\" in ('active', 'suspended')",
            name="membershipStatus",
        ),
        SCHEMA,
    )

    membership_id: Mapped[uuid.UUID] = Columns.uuid_pk("membershipId")
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        "tenantId", ForeignKey("registry.Tenants.tenantId")
    )
    identity_id: Mapped[uuid.UUID] = mapped_column(
        "identityId", ForeignKey("registry.Identities.identityId")
    )
    membership_kind: Mapped[str] = mapped_column(
        "membershipKind", String(16), server_default="staff"
    )
    membership_status: Mapped[str] = mapped_column(
        "membershipStatus", String(16), server_default="active"
    )
    created_at: Mapped[datetime] = Columns.created_at()
```

`backend/src/erp/model_registry.py`:

```python
"""Import every module's models so both metadata sets are complete."""

from erp.modules.platform import registry_models  # noqa: F401
```

In `backend/migrations/registry/env.py`, add below the existing imports:

```python
import erp.model_registry  # noqa: F401
```

- [ ] **Step 4: Migration**

`backend/migrations/registry/versions/r0002_registry_tenancy.py`:

```python
"""registry: Tenants, Identities, Memberships"""

import sqlalchemy as sa
from alembic import op

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "r0002"
down_revision = "r0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Tenants",
        cols.uuid("tenantId"),
        sa.Column("accountNumber", sa.String(32), nullable=False),
        sa.Column("tenantName", sa.String(200), nullable=False),
        sa.Column(
            "tenantStatus", sa.String(16), nullable=False, server_default="active"
        ),
        sa.Column(
            "databaseServer", sa.String(64), nullable=False, server_default="default"
        ),
        sa.Column("databaseName", sa.String(63), nullable=False),
        sa.Column(
            "databaseStatus",
            sa.String(16),
            nullable=False,
            server_default="provisioning",
        ),
        sa.Column("schemaRevision", sa.String(32), nullable=True),
        sa.Column("lastMigrationError", sa.String(1000), nullable=True),
        cols.created_at(),
        sa.PrimaryKeyConstraint("tenantId", name="pk_Tenants"),
        sa.UniqueConstraint("accountNumber", name="uq_Tenants_accountNumber"),
        sa.UniqueConstraint("databaseName", name="uq_Tenants_databaseName"),
        sa.CheckConstraint(
            "\"tenantStatus\" in ('active', 'suspended')",
            name="ck_Tenants_tenantStatus",
        ),
        sa.CheckConstraint(
            "\"databaseStatus\" in ('provisioning', 'ready', 'failed')",
            name="ck_Tenants_databaseStatus",
        ),
        schema="registry",
    )
    op.create_table(
        "Identities",
        cols.uuid("identityId"),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        cols.created_at(),
        sa.PrimaryKeyConstraint("identityId", name="pk_Identities"),
        sa.UniqueConstraint(
            "issuer", "subject", name="uq_Identities_issuer_subject"
        ),
        schema="registry",
    )
    op.create_table(
        "Memberships",
        cols.uuid("membershipId"),
        cols.registry_tenant_id("Memberships"),
        sa.Column(
            "identityId",
            sa.Uuid(),
            sa.ForeignKey(
                "registry.Identities.identityId",
                name="fk_Memberships_identityId_Identities",
            ),
            nullable=False,
        ),
        sa.Column(
            "membershipKind", sa.String(16), nullable=False, server_default="staff"
        ),
        sa.Column(
            "membershipStatus", sa.String(16), nullable=False, server_default="active"
        ),
        cols.created_at(),
        sa.PrimaryKeyConstraint("membershipId", name="pk_Memberships"),
        sa.UniqueConstraint(
            "tenantId", "membershipId", name="uq_Memberships_tenantId_membershipId"
        ),
        sa.UniqueConstraint(
            "tenantId",
            "identityId",
            "membershipKind",
            name="uq_Memberships_tenantId_identityId_membershipKind",
        ),
        sa.CheckConstraint(
            "\"membershipKind\" in ('staff', 'buyer', 'service')",
            name="ck_Memberships_membershipKind",
        ),
        sa.CheckConstraint(
            "\"membershipStatus\" in ('active', 'suspended')",
            name="ck_Memberships_membershipStatus",
        ),
        schema="registry",
    )
    for statement in RlsSql.tenant_policy("registry", "Memberships"):
        op.execute(statement)
    op.execute(RlsSql.identity_read_policy("registry", "Memberships"))


def downgrade() -> None:
    for table in ("Memberships", "Identities", "Tenants"):
        op.drop_table(table, schema="registry")
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass, including 5 in `test_registry.py` and `test_registry_models_match_migrations`. If the drift test fails, its assertion lists each difference; fix whichever side is wrong.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat(platform): registry Tenants, Identities, Memberships"
```

---

### Task 5: Tenant database tree and provisioning

**Files:**
- Modify: `backend/src/erp/core/db.py`, `backend/src/erp/core/config.py`, `backend/src/erp/model_registry.py`, `backend/tests/conftest.py`, `backend/tests/support.py`
- Create: `backend/src/erp/modules/platform/models.py`, `backend/src/erp/modules/platform/registry_repository.py`, `backend/src/erp/modules/platform/provisioning.py`, `backend/migrations/tenant/env.py`, `backend/migrations/tenant/versions/t0001_platform_database_owners.py`, `backend/migrations/tenant/versions/t0002_platform_companies_branches.py`
- Test: `backend/tests/core/test_locator.py`, `backend/tests/platform/test_provisioning.py`

**Interfaces:**
- Produces:
  - `SqlIdentifier.safe(value)`, `DbCredentials(user, password)`, and `TenantDbLocator(servers, *, database_prefix)` with `.database_name(tenant_id)` / `.url(server, database, credentials)`.
  - Tenant models `DatabaseOwner`, `Company`, `Branch`.
  - `TenantRepository(session)` with `new_id()`, `add(tenant)`, `get(tenant_id)`, `lock(tenant_id)`, `with_database_status(status)`, `active_ids()`, `record_database_state(tenant_id, *, status, revision=None, error=None)`.
  - `TenantDatabaseAdmin(locator, *, owner, runtime_roles)` with `url`, `exists`, `create`, `grant_connect`, `bind_owner`.
  - `TenantMigrator(alembic_ini)` with `head_revision()` and `upgrade(url) -> str`.
  - `TenantProvisioner.create(registry, locator, *, owner, runtime_roles, alembic_ini, server="default")` with `.provision(*, account_number, tenant_name) -> UUID`, `.complete(tenant_id) -> str`, `.upgrade_all() -> list[MigrationOutcome]`, `.head_revision()`.
  - `MigrationOutcome`, `MissingTenantDatabaseError`.
  - In `tests/support.py`: `OWNER`, `APP`, `RELAY`.
  - Fixtures `locator`, `provisioner`, `owner_connect(database)`, `drop_database(name)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/core/test_locator.py`:

```python
from uuid import UUID

import pytest

from erp.core.db import DbCredentials, TenantDbLocator

LOCATOR = TenantDbLocator(
    {"default": "db.internal:6432"}, database_prefix="erp_t_"
)


def test_database_name_is_prefix_plus_uuid_hex():
    tenant_id = UUID("0190f1c2-0000-7000-8000-000000000001")

    expected = "erp_t_0190f1c2000070008000000000000001"
    assert LOCATOR.database_name(tenant_id) == expected


def test_url_uses_server_address_and_escapes_credentials():
    credentials = DbCredentials("erp_app", "p@ss:w/rd")

    url = LOCATOR.url("default", "erp_t_x", credentials)

    assert (url.host, url.port, url.database) == ("db.internal", 6432, "erp_t_x")
    assert url.password == "p@ss:w/rd"
    assert "p%40ss" in url.render_as_string(hide_password=False)


def test_unknown_server_is_rejected():
    with pytest.raises(ValueError, match="unknown tenant database server"):
        LOCATOR.url("eu-2", "erp_t_x", DbCredentials("erp_app", "x"))


@pytest.mark.parametrize("prefix", ["", "Erp_", "erp-t-", "x;drop"])
def test_unsafe_prefixes_are_rejected(prefix):
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        TenantDbLocator({"default": "db:5432"}, database_prefix=prefix)
```

`backend/tests/platform/test_provisioning.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from erp.modules.platform.provisioning import (
    MissingTenantDatabaseError,
    TenantDatabaseAdmin,
)
from erp.modules.platform.registry_models import Tenant

BOUND_TENANT = text('SELECT "tenantId" FROM platform."DatabaseOwners"')


def _number():
    return f"P{uuid4().hex[:12]}"


def _tenant_row(registry, **where):
    with registry.platform_session() as s:
        return s.scalars(select(Tenant).filter_by(**where)).one()


def test_provision_creates_a_migrated_database_bound_to_the_tenant(
    provisioner, registry, locator, owner_connect
):
    tenant_id = provisioner.provision(
        account_number=_number(), tenant_name="Gamma Ltd"
    )

    tenant = _tenant_row(registry, tenant_id=tenant_id)
    assert tenant.database_name == locator.database_name(tenant_id)
    assert tenant.database_status == "ready"
    assert tenant.schema_revision == provisioner.head_revision()
    assert tenant.last_migration_error is None
    with owner_connect(tenant.database_name) as conn:
        assert conn.scalar(BOUND_TENANT) == tenant_id


def test_complete_is_idempotent(provisioner):
    tenant_id = provisioner.provision(
        account_number=_number(), tenant_name="Delta Ltd"
    )

    assert provisioner.complete(tenant_id) == provisioner.head_revision()


def test_failed_step_is_recorded_and_retry_completes(
    provisioner, registry, monkeypatch
):
    number = _number()

    def fail(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(TenantDatabaseAdmin, "bind_owner", fail)
    with pytest.raises(RuntimeError, match="disk full"):
        provisioner.provision(account_number=number, tenant_name="Epsilon Ltd")
    failed = _tenant_row(registry, account_number=number)
    monkeypatch.undo()

    provisioner.complete(failed.tenant_id)

    assert failed.database_status == "failed"
    assert "disk full" in failed.last_migration_error
    recovered = _tenant_row(registry, tenant_id=failed.tenant_id)
    assert recovered.database_status == "ready"


def test_upgrade_all_continues_past_a_missing_database(
    provisioner, registry, locator, drop_database
):
    healthy = provisioner.provision(account_number=_number(), tenant_name="Zeta")
    broken = provisioner.provision(account_number=_number(), tenant_name="Eta")
    drop_database(locator.database_name(broken))

    outcomes = {o.tenant_id: o for o in provisioner.upgrade_all()}

    assert outcomes[healthy].error is None
    assert outcomes[healthy].revision == provisioner.head_revision()
    assert outcomes[broken].revision is None
    assert "does not exist" in outcomes[broken].error
    broken_row = _tenant_row(registry, tenant_id=broken)
    assert broken_row.database_status == "failed"


def test_a_previously_migrated_database_is_never_recreated(
    provisioner, locator, drop_database
):
    tenant_id = provisioner.provision(
        account_number=_number(), tenant_name="Theta Ltd"
    )
    drop_database(locator.database_name(tenant_id))

    with pytest.raises(MissingTenantDatabaseError):
        provisioner.complete(tenant_id)


def test_duplicate_account_number_fails_before_any_database_is_created(
    provisioner,
):
    number = _number()
    provisioner.provision(account_number=number, tenant_name="Iota Ltd")

    with pytest.raises(IntegrityError):
        provisioner.provision(account_number=number, tenant_name="Iota Copy")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/test_locator.py tests/platform/test_provisioning.py -v`
Expected: FAIL with `ImportError: cannot import name 'DbCredentials' from 'erp.core.db'`

- [ ] **Step 3: Locator, identifiers and settings**

Append to `backend/src/erp/core/db.py` (merge imports at the top: `import re`, `from collections.abc import Mapping`, `from dataclasses import dataclass, field`, `from typing import ClassVar`):

```python
class SqlIdentifier:
    """Validate identifiers that cannot be bound as parameters."""

    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]{0,62}")

    @classmethod
    def safe(cls, value: str) -> str:
        """Allow only lowercase names (databases, roles, prefixes)."""
        if not cls.PATTERN.fullmatch(value):
            raise ValueError(f"unsafe SQL identifier {value!r}")
        return value


@dataclass(frozen=True)
class DbCredentials:
    user: str
    password: str = field(repr=False)


class TenantDbLocator:
    """Name tenant databases and build their URLs (ADR-0002)."""

    def __init__(
        self, servers: Mapping[str, str], *, database_prefix: str
    ) -> None:
        self._servers = dict(servers)
        self._prefix = SqlIdentifier.safe(database_prefix)

    def database_name(self, tenant_id: UUID) -> str:
        return SqlIdentifier.safe(f"{self._prefix}{tenant_id.hex}")

    def url(
        self, server: str, database: str, credentials: DbCredentials
    ) -> URL:
        try:
            address = self._servers[server]
        except KeyError:
            raise ValueError(
                f"unknown tenant database server {server!r}"
            ) from None
        host, _, port = address.partition(":")
        return URL.create(
            "postgresql+psycopg",
            username=credentials.user,
            password=credentials.password,
            host=host,
            port=int(port) if port else 5432,
            database=database,
        )
```

Add these fields to `Settings` in `backend/src/erp/core/config.py`, after `registry_migration_database_url`:

```python
    # Server key -> host:port. Tenants record their server key, so more
    # servers ("cells") can be added later.
    tenant_db_servers: dict[str, str] = {"default": "localhost:55432"}
    tenant_db_prefix: str = "erp_t_"
    tenant_db_app_user: str = "erp_app"
    tenant_db_app_password: str = "erp_app_dev"
    tenant_db_relay_user: str = "erp_relay"
    tenant_db_relay_password: str = "erp_relay_dev"
    tenant_db_owner_user: str = "erp_owner"
    tenant_db_owner_password: str = "erp_owner_dev"
```

Replace `backend/tests/support.py` with:

```python
"""Test-only constants and helpers (on pytest's pythonpath)."""

from erp.core.db import DbCredentials

OWNER = DbCredentials("erp_owner", "erp_owner_dev")
APP = DbCredentials("erp_app", "erp_app_dev")
RELAY = DbCredentials("erp_relay", "erp_relay_dev")
```

- [ ] **Step 4: Tenant models and migration tree**

`backend/src/erp/modules/platform/models.py`:

```python
"""Platform tables inside each tenant database."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import Columns, TenantBase

SCHEMA = {"schema": "platform"}


class DatabaseOwner(TenantBase):
    """Exactly one row: the tenant this database belongs to.

    Every "tenantId" column references it, so another tenant's rows
    cannot be stored here, even under a wrong context.
    """

    __tablename__ = "DatabaseOwners"
    __table_args__ = (CheckConstraint('"isSingleton"', name="isSingleton"), SCHEMA)

    is_singleton: Mapped[bool] = mapped_column(
        "isSingleton", primary_key=True, server_default=sql("true")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column("tenantId", unique=True)


class Company(TenantBase):
    __tablename__ = "Companies"
    __table_args__ = (UniqueConstraint("tenantId", "companyId"), SCHEMA)

    company_id: Mapped[uuid.UUID] = Columns.uuid_pk("companyId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    company_name: Mapped[str] = mapped_column("companyName", String(200))
    country_code: Mapped[str] = mapped_column("countryCode", String(2))
    base_currency: Mapped[str] = mapped_column("baseCurrency", String(3))
    time_zone: Mapped[str] = mapped_column("timeZone", String(64))
    created_at: Mapped[datetime] = Columns.created_at()


class Branch(TenantBase):
    __tablename__ = "Branches"
    __table_args__ = (
        UniqueConstraint("tenantId", "branchId"),
        UniqueConstraint("tenantId", "companyId", "branchCode"),
        ForeignKeyConstraint(
            ["tenantId", "companyId"],
            ["platform.Companies.tenantId", "platform.Companies.companyId"],
        ),
        SCHEMA,
    )

    branch_id: Mapped[uuid.UUID] = Columns.uuid_pk("branchId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    company_id: Mapped[uuid.UUID] = mapped_column("companyId")
    branch_code: Mapped[str] = mapped_column("branchCode", String(32))
    branch_name: Mapped[str] = mapped_column("branchName", String(200))
    created_at: Mapped[datetime] = Columns.created_at()
```

Append to `backend/src/erp/model_registry.py`:

```python
from erp.modules.platform import models as platform_models  # noqa: F401
```

`backend/migrations/tenant/env.py`:

```python
"""Alembic environment for ONE tenant database.

The URL is always supplied by the provisioner.
"""

from alembic import context

import erp.model_registry  # noqa: F401
from erp.core.migrations import AlembicEnvironment
from erp.core.models import TenantBase

url = context.config.get_main_option("sqlalchemy.url")
if not url:
    raise RuntimeError(
        "tenant migrations need an explicit database URL; "
        "run `python -m erp.cli upgrade-tenants`"
    )
AlembicEnvironment(TenantBase.metadata, url).run()
```

`backend/migrations/tenant/versions/t0001_platform_database_owners.py`:

```python
"""tenant DB: module schemas, runtime grants, DatabaseOwners"""

import sqlalchemy as sa
from alembic import op

from erp.core.rls import RlsSql

revision = "t0001"
down_revision = None
branch_labels = None
depends_on = None

# Later module schemas are created by the slice that introduces the
# module. Every installed module's tables exist in every tenant DB,
# whether or not the tenant enabled the module (ADR-0009).
SCHEMAS = ("platform", "integration")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA {schema}")
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO erp_app")
        op.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            "GRANT SELECT, INSERT, UPDATE ON TABLES TO erp_app"
        )
    op.execute("GRANT USAGE ON SCHEMA integration TO erp_relay")
    op.create_table(
        "DatabaseOwners",
        sa.Column(
            "isSingleton",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("tenantId", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("isSingleton", name="pk_DatabaseOwners"),
        sa.UniqueConstraint("tenantId", name="uq_DatabaseOwners_tenantId"),
        sa.CheckConstraint('"isSingleton"', name="ck_DatabaseOwners_isSingleton"),
        schema="platform",
    )
    # Bound once by the provisioner (erp_owner); the runtime only reads.
    owners = RlsSql.table_ref("platform", "DatabaseOwners")
    op.execute(f"REVOKE INSERT, UPDATE ON {owners} FROM erp_app")


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA {schema} CASCADE")
```

`backend/migrations/tenant/versions/t0002_platform_companies_branches.py`:

```python
"""tenant DB: platform Companies and Branches"""

import sqlalchemy as sa
from alembic import op

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "t0002"
down_revision = "t0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Companies",
        cols.uuid("companyId"),
        cols.owner_tenant_id("Companies"),
        sa.Column("companyName", sa.String(200), nullable=False),
        sa.Column("countryCode", sa.String(2), nullable=False),
        sa.Column("baseCurrency", sa.String(3), nullable=False),
        sa.Column("timeZone", sa.String(64), nullable=False),
        cols.created_at(),
        sa.PrimaryKeyConstraint("companyId", name="pk_Companies"),
        sa.UniqueConstraint(
            "tenantId", "companyId", name="uq_Companies_tenantId_companyId"
        ),
        schema="platform",
    )
    op.create_table(
        "Branches",
        cols.uuid("branchId"),
        cols.owner_tenant_id("Branches"),
        sa.Column("companyId", sa.Uuid(), nullable=False),
        sa.Column("branchCode", sa.String(32), nullable=False),
        sa.Column("branchName", sa.String(200), nullable=False),
        cols.created_at(),
        sa.PrimaryKeyConstraint("branchId", name="pk_Branches"),
        sa.UniqueConstraint(
            "tenantId", "branchId", name="uq_Branches_tenantId_branchId"
        ),
        sa.UniqueConstraint(
            "tenantId",
            "companyId",
            "branchCode",
            name="uq_Branches_tenantId_companyId_branchCode",
        ),
        sa.ForeignKeyConstraint(
            ["tenantId", "companyId"],
            ["platform.Companies.tenantId", "platform.Companies.companyId"],
            name="fk_Branches_tenantId_companyId_Companies",
        ),
        schema="platform",
    )
    for table in ("Companies", "Branches"):
        for statement in RlsSql.tenant_policy("platform", table):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("Branches", schema="platform")
    op.drop_table("Companies", schema="platform")
```

- [ ] **Step 5: Registry repository and provisioner**

`backend/src/erp/modules/platform/registry_repository.py`:

```python
"""Repositories for registry tables (ADR-0011)."""

from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from erp.modules.platform.registry_models import Tenant


class TenantRepository:
    """All queries on registry "Tenants"."""

    NEW_ID = text("select uuidv7()")

    def __init__(self, session: Session) -> None:
        self._session = session

    def new_id(self) -> UUID:
        return self._session.scalar(self.NEW_ID)

    def add(self, tenant: Tenant) -> None:
        self._session.add(tenant)
        self._session.flush()

    def get(self, tenant_id: UUID) -> Tenant | None:
        return self._session.get(Tenant, tenant_id)

    def lock(self, tenant_id: UUID) -> bool:
        """Row-lock a tenant until the transaction ends."""
        row = self._session.execute(
            select(Tenant.tenant_id)
            .where(Tenant.tenant_id == tenant_id)
            .with_for_update()
        ).first()
        return row is not None

    def with_database_status(self, status: str) -> list[Tenant]:
        return list(
            self._session.scalars(
                select(Tenant)
                .where(Tenant.database_status == status)
                .order_by(Tenant.tenant_id)
            )
        )

    def active_ids(self) -> list[UUID]:
        return list(
            self._session.scalars(
                select(Tenant.tenant_id)
                .where(
                    Tenant.tenant_status == "active",
                    Tenant.database_status == "ready",
                )
                .order_by(Tenant.tenant_id)
            )
        )

    def record_database_state(
        self,
        tenant_id: UUID,
        *,
        status: str,
        revision: str | None = None,
        error: str | None = None,
    ) -> None:
        values: dict[object, object] = {
            Tenant.database_status: status,
            Tenant.last_migration_error: error,
        }
        if revision is not None:
            values[Tenant.schema_revision] = revision
        self._session.execute(
            update(Tenant).where(Tenant.tenant_id == tenant_id).values(values)
        )
```

`backend/src/erp/modules/platform/provisioning.py`:

```python
"""Create, migrate and upgrade tenant databases (ADR-0002).

Operator tooling (python -m erp.cli) that runs as erp_owner. The API
never uses it.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self
from uuid import UUID

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Connection, create_engine, text
from sqlalchemy.pool import NullPool

from erp.core.db import Database, DbCredentials, SqlIdentifier, TenantDbLocator
from erp.core.errors import NotFoundError
from erp.modules.platform.registry_models import Tenant
from erp.modules.platform.registry_repository import TenantRepository


class MissingTenantDatabaseError(RuntimeError):
    """A previously migrated tenant database is gone.

    Restore it from backup; never re-create it empty.
    """


@dataclass(frozen=True)
class MigrationOutcome:
    tenant_id: UUID
    revision: str | None
    error: str | None


class TenantDatabaseAdmin:
    """Server-level operations on tenant databases, as erp_owner."""

    DATABASE_EXISTS = text("select 1 from pg_database where datname = :name")
    BIND_OWNER = text(
        'INSERT INTO platform."DatabaseOwners" ("tenantId") '
        'VALUES (:tenant_id) ON CONFLICT ("isSingleton") DO NOTHING'
    )
    BOUND_OWNER = text('SELECT "tenantId" FROM platform."DatabaseOwners"')

    def __init__(
        self,
        locator: TenantDbLocator,
        *,
        owner: DbCredentials,
        runtime_roles: Sequence[str],
    ) -> None:
        self._locator = locator
        self._owner = DbCredentials(SqlIdentifier.safe(owner.user), owner.password)
        self._runtime_roles = [SqlIdentifier.safe(r) for r in runtime_roles]

    def url(self, server: str, database: str) -> URL:
        name = SqlIdentifier.safe(database)
        return self._locator.url(server, name, self._owner)

    def exists(self, server: str, database: str) -> bool:
        with self._server_connection(server) as conn:
            found = conn.scalar(self.DATABASE_EXISTS, {"name": database})
        return found is not None

    def create(self, server: str, database: str) -> None:
        name = SqlIdentifier.safe(database)
        with self._server_connection(server) as conn:
            conn.execute(
                text(f'CREATE DATABASE "{name}" OWNER "{self._owner.user}"')
            )

    def grant_connect(self, server: str, database: str) -> None:
        name = SqlIdentifier.safe(database)
        with self._server_connection(server) as conn:
            conn.execute(text(f'REVOKE CONNECT ON DATABASE "{name}" FROM PUBLIC'))
            for role in self._runtime_roles:
                conn.execute(
                    text(f'GRANT CONNECT ON DATABASE "{name}" TO "{role}"')
                )

    def bind_owner(self, server: str, database: str, tenant_id: UUID) -> None:
        """Record the owning tenant in the database's DatabaseOwners."""
        engine = create_engine(self.url(server, database), poolclass=NullPool)
        try:
            with engine.begin() as conn:
                conn.execute(self.BIND_OWNER, {"tenant_id": tenant_id})
                bound_to = conn.scalar(self.BOUND_OWNER)
        finally:
            engine.dispose()
        if bound_to != tenant_id:
            raise RuntimeError(f"{database} already belongs to {bound_to}")

    @contextmanager
    def _server_connection(self, server: str) -> Iterator[Connection]:
        engine = create_engine(
            self._locator.url(server, "postgres", self._owner),
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )
        try:
            with engine.connect() as conn:
                yield conn
        finally:
            engine.dispose()


class TenantMigrator:
    """Run the tenant Alembic tree against one database."""

    def __init__(self, alembic_ini: Path) -> None:
        self._alembic_ini = alembic_ini

    def head_revision(self) -> str:
        return ScriptDirectory.from_config(self._config()).get_current_head()

    def upgrade(self, url: URL) -> str:
        config = self._config()
        # configparser treats % as interpolation; escaped passwords may
        # contain it.
        rendered = url.render_as_string(hide_password=False)
        config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))
        command.upgrade(config, "head")
        return self.current_revision(url)

    @staticmethod
    def current_revision(url: URL) -> str:
        engine = create_engine(url, poolclass=NullPool)
        try:
            with engine.connect() as conn:
                return MigrationContext.configure(conn).get_current_revision()
        finally:
            engine.dispose()

    def _config(self) -> Config:
        return Config(str(self._alembic_ini), ini_section="tenant")


class TenantProvisioner:
    """Provision tenant databases and keep them migrated."""

    def __init__(
        self,
        registry: Database,
        locator: TenantDbLocator,
        admin: TenantDatabaseAdmin,
        migrator: TenantMigrator,
        *,
        server: str = "default",
    ) -> None:
        self._registry = registry
        self._locator = locator
        self._admin = admin
        self._migrator = migrator
        self._server = server

    @classmethod
    def create(
        cls,
        registry: Database,
        locator: TenantDbLocator,
        *,
        owner: DbCredentials,
        runtime_roles: Sequence[str],
        alembic_ini: Path,
        server: str = "default",
    ) -> Self:
        admin = TenantDatabaseAdmin(
            locator, owner=owner, runtime_roles=runtime_roles
        )
        migrator = TenantMigrator(alembic_ini)
        return cls(registry, locator, admin, migrator, server=server)

    def head_revision(self) -> str:
        return self._migrator.head_revision()

    def provision(self, *, account_number: str, tenant_name: str) -> UUID:
        with self._registry.platform_session() as s:
            tenants = TenantRepository(s)
            tenant_id = tenants.new_id()
            tenants.add(
                Tenant(
                    tenant_id=tenant_id,
                    account_number=account_number,
                    tenant_name=tenant_name,
                    database_server=self._server,
                    database_name=self._locator.database_name(tenant_id),
                )
            )
        self.complete(tenant_id)
        return tenant_id

    def complete(self, tenant_id: UUID) -> str:
        """Create, migrate and bind the database; safe to re-run."""
        with self._registry.platform_session() as s:
            tenant = TenantRepository(s).get(tenant_id)
        if tenant is None:
            raise NotFoundError("unknown tenant", code="TENANT_NOT_FOUND")
        server, database = tenant.database_server, tenant.database_name
        try:
            if not self._admin.exists(server, database):
                if tenant.schema_revision is not None:
                    raise MissingTenantDatabaseError(
                        f"{database} is missing; restore it from backup "
                        "instead of re-creating it"
                    )
                self._admin.create(server, database)
            self._admin.grant_connect(server, database)
            revision = self._migrator.upgrade(self._admin.url(server, database))
            self._admin.bind_owner(server, database, tenant_id)
        except Exception as exc:
            self._record(tenant_id, status="failed", error=exc)
            raise
        self._record(tenant_id, status="ready", revision=revision)
        return revision

    def upgrade_all(self) -> list[MigrationOutcome]:
        """Upgrade every ready tenant DB; failures don't stop others."""
        with self._registry.platform_session() as s:
            tenants = TenantRepository(s).with_database_status("ready")
        outcomes = []
        for tenant in tenants:
            url = self._admin.url(tenant.database_server, tenant.database_name)
            try:
                revision = self._migrator.upgrade(url)
            except Exception as exc:
                self._record(tenant.tenant_id, status="failed", error=exc)
                outcomes.append(
                    MigrationOutcome(tenant.tenant_id, None, self._describe(exc))
                )
            else:
                self._record(tenant.tenant_id, status="ready", revision=revision)
                outcomes.append(MigrationOutcome(tenant.tenant_id, revision, None))
        return outcomes

    def _record(
        self,
        tenant_id: UUID,
        *,
        status: str,
        revision: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        message = self._describe(error) if error else None
        with self._registry.platform_session() as s:
            TenantRepository(s).record_database_state(
                tenant_id, status=status, revision=revision, error=message
            )

    @staticmethod
    def _describe(exc: BaseException) -> str:
        return f"{type(exc).__name__}: {exc}"[:1000]
```

- [ ] **Step 6: Fixtures**

Append to `backend/tests/conftest.py`. Merge these imports at the top:
- `from contextlib import contextmanager`
- `from sqlalchemy import Connection`
- `from sqlalchemy.pool import NullPool`
- `from erp.core.db import TenantDbLocator`
- `from erp.modules.platform.provisioning import TenantProvisioner`
- `from support import OWNER`

```python
TENANT_DB_SERVERS = {
    "default": os.environ.get("ERP_TEST_TENANT_DB_SERVER", "localhost:55432")
}
TENANT_DB_PREFIX = "erp_test_t_"


@pytest.fixture(scope="session")
def locator() -> TenantDbLocator:
    return TenantDbLocator(TENANT_DB_SERVERS, database_prefix=TENANT_DB_PREFIX)


def _server_admin(locator: TenantDbLocator) -> Engine:
    return create_engine(
        locator.url("default", "postgres", OWNER),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )


def _drop_test_tenant_databases(locator: TenantDbLocator) -> None:
    engine = _server_admin(locator)
    pattern = TENANT_DB_PREFIX.replace("_", r"\_") + "%"
    with engine.connect() as conn:
        names = conn.execute(
            text("select datname from pg_database where datname like :pattern"),
            {"pattern": pattern},
        ).scalars().all()
        for name in names:
            conn.execute(text(f'DROP DATABASE "{name}"'))
    engine.dispose()


@pytest.fixture(scope="session")
def provisioner(
    _registry: Database, locator: TenantDbLocator
) -> Iterator[TenantProvisioner]:
    """Provision real erp_test_t_* databases; dropped at session end."""
    _drop_test_tenant_databases(locator)  # leftovers from aborted runs
    yield TenantProvisioner.create(
        _registry,
        locator,
        owner=OWNER,
        runtime_roles=["erp_app", "erp_relay"],
        alembic_ini=BACKEND_DIR / "alembic.ini",
    )
    _drop_test_tenant_databases(locator)


@pytest.fixture(scope="session")
def owner_connect(locator: TenantDbLocator):
    @contextmanager
    def _connect(database: str) -> Iterator[Connection]:
        url = locator.url("default", database, OWNER)
        engine = create_engine(url, poolclass=NullPool)
        try:
            with engine.begin() as conn:
                yield conn
        finally:
            engine.dispose()

    return _connect


@pytest.fixture(scope="session")
def drop_database(locator: TenantDbLocator):
    def _drop(name: str) -> None:
        engine = _server_admin(locator)
        with engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}"'))
        engine.dispose()

    return _drop
```

- [ ] **Step 7: Run tests**

Run: `cd backend && uv run pytest tests/core/test_locator.py tests/platform/test_provisioning.py -v`
Expected: `7 passed` and `6 passed`. Then `uv run pytest -v`: everything green.

- [ ] **Step 8: Commit**

```bash
git add backend
git commit -m "feat(platform): per-tenant database provisioning and upgrade runner"
```

---

### Task 6: Tenant database router and isolation guarantees

**Files:**
- Create: `backend/src/erp/modules/platform/tenant_db.py`, `backend/src/erp/modules/platform/interface.py`
- Modify: `backend/tests/conftest.py`, `backend/tests/core/test_migrations.py`
- Test: `backend/tests/platform/test_tenant_isolation.py`

**Interfaces:**
- Consumes: `Database`, `TenantDbLocator`, `DbCredentials`, `TenantRepository`, `NotFoundError`, `ServiceUnavailableError`.
- Produces:
  - `TenantDatabaseRouter(registry, locator, credentials, *, max_cached=200, **engine_kwargs)` with:
    - `.for_tenant(tenant_id) -> Database`, which raises `NotFoundError` (`TENANT_NOT_FOUND`) or `TenantUnavailableError` (503)
    - `.active_tenant_ids()`
    - `.evict(tenant_id)`
    - `.dispose_all()`
  - Fixtures `router`, `provisioned -> (a, b)`, `two_tenants -> SeededTenants(a, b, company_a, company_b)`.

- [ ] **Step 1: Fixtures**

Append to `backend/tests/conftest.py`. Merge these imports:
- `from dataclasses import dataclass`
- `from uuid import UUID`
- `from erp.modules.platform.models import Company`
- `from erp.modules.platform.tenant_db import TenantDatabaseRouter`
- `APP`, added to the `support` import

```python
@pytest.fixture(scope="session")
def router(
    _registry: Database,
    locator: TenantDbLocator,
    provisioner: TenantProvisioner,
) -> Iterator[TenantDatabaseRouter]:
    tenant_router = TenantDatabaseRouter(_registry, locator, APP)
    yield tenant_router
    tenant_router.dispose_all()  # before the databases are dropped


@pytest.fixture(scope="session")
def provisioned(provisioner: TenantProvisioner) -> tuple[UUID, UUID]:
    """Tenants A (100001) and B (100002), each with its own database."""
    a = provisioner.provision(account_number="100001", tenant_name="Alpha Traders")
    b = provisioner.provision(account_number="100002", tenant_name="Beta Foods")
    return a, b


@dataclass(frozen=True)
class SeededTenants:
    a: UUID
    b: UUID
    company_a: UUID
    company_b: UUID


@pytest.fixture
def two_tenants(provisioned, router, locator, registry) -> Iterator[SeededTenants]:
    """One company per tenant, written as erp_app; emptied after."""
    a, b = provisioned
    names = ("Alpha Traders Ltd", "Beta Foods Ltd")
    company_ids = []
    for tenant_id, name in zip((a, b), names, strict=True):
        with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
            company = Company(
                tenant_id=tenant_id,
                company_name=name,
                country_code="BD",
                base_currency="BDT",
                time_zone="Asia/Dhaka",
            )
            s.add(company)
            s.flush()
            company_ids.append(company.company_id)
    yield SeededTenants(a, b, company_ids[0], company_ids[1])
    for tenant_id in (a, b):
        url = locator.url("default", locator.database_name(tenant_id), OWNER)
        engine = create_engine(url, poolclass=NullPool)
        truncate_tables(
            engine, exclude=frozenset({'platform."DatabaseOwners"'})
        )
        engine.dispose()
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/platform/test_tenant_isolation.py`:

```python
"""Per-tenant databases plus in-database defence (E2E-01 seed)."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from erp.core.errors import NotFoundError
from erp.modules.platform.models import Company, DatabaseOwner
from erp.modules.platform.registry_models import Tenant
from erp.modules.platform.tenant_db import TenantDatabaseRouter, TenantUnavailableError
from support import APP


def _company(tenant_id, name="Injected Ltd"):
    return Company(
        tenant_id=tenant_id,
        company_name=name,
        country_code="BD",
        base_currency="BDT",
        time_zone="Asia/Dhaka",
    )


def test_each_tenant_is_routed_to_its_own_database(router, locator, two_tenants):
    for tenant_id in (two_tenants.a, two_tenants.b):
        with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
            current = s.scalar(text("select current_database()"))
        assert current == locator.database_name(tenant_id)


def test_tenant_database_contains_only_its_own_data(router, two_tenants):
    a = two_tenants.a
    with router.for_tenant(a).tenant_session(a) as s:
        names = s.scalars(select(Company.company_name)).all()
    assert names == ["Alpha Traders Ltd"]


def test_wrong_context_in_a_tenant_database_sees_nothing(router, two_tenants):
    """A's database opened with B's context: RLS returns no rows."""
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.b) as s:
        assert s.scalars(select(Company)).all() == []


def test_tenant_database_cannot_store_another_tenants_rows(router, two_tenants):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises(IntegrityError):
        with database.tenant_session(two_tenants.b) as s:
            s.add(_company(two_tenants.b))
            s.flush()


def test_rls_rejects_rows_outside_the_current_context(router, two_tenants):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises(DBAPIError, match="row-level security"):
        with database.tenant_session(two_tenants.a) as s:
            s.add(_company(two_tenants.b))
            s.flush()


def test_missing_context_returns_no_rows(router, two_tenants):
    with router.for_tenant(two_tenants.a).platform_session() as s:
        assert s.scalars(select(Company)).all() == []


def test_runtime_role_cannot_rebind_a_tenant_database(router, two_tenants):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises(DBAPIError, match="permission denied"):
        with database.tenant_session(two_tenants.a) as s:
            s.execute(update(DatabaseOwner).values(tenant_id=two_tenants.b))


def test_router_reuses_one_pool_per_tenant(router, two_tenants):
    assert router.for_tenant(two_tenants.a) is router.for_tenant(two_tenants.a)
    assert router.for_tenant(two_tenants.a) is not router.for_tenant(two_tenants.b)


def test_router_evicts_least_recently_used_pools(registry, locator, provisioned):
    a, b = provisioned
    small = TenantDatabaseRouter(registry, locator, APP, max_cached=1)
    try:
        first = small.for_tenant(a)
        small.for_tenant(b)
        assert small.for_tenant(a) is not first
    finally:
        small.dispose_all()


def test_unknown_tenant_is_not_found(router):
    with pytest.raises(NotFoundError):
        router.for_tenant(uuid4())


def test_tenant_without_ready_database_is_unavailable(router, registry):
    with registry.platform_session() as s:
        tenant = Tenant(
            account_number=f"U{uuid4().hex[:12]}",
            tenant_name="Pending Ltd",
            database_name=f"unprovisioned_{uuid4().hex}",
        )
        s.add(tenant)
        s.flush()
        tenant_id = tenant.tenant_id

    with pytest.raises(TenantUnavailableError):
        router.for_tenant(tenant_id)
```

Append to `backend/tests/core/test_migrations.py`. Merge these imports:
- `from sqlalchemy import create_engine`
- `from sqlalchemy.pool import NullPool`
- `from erp.core.models import TenantBase`
- `from support import OWNER`

```python
def test_tenant_models_match_migrations(provisioned, locator):
    url = locator.url(
        "default", locator.database_name(provisioned[0]), OWNER
    )
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(
                conn, opts={"include_schemas": True}
            )
            assert compare_metadata(context, TenantBase.metadata) == []
    finally:
        engine.dispose()
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend && uv run pytest tests/platform/test_tenant_isolation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.modules.platform.tenant_db'`

- [ ] **Step 4: Implement the router**

`backend/src/erp/modules/platform/tenant_db.py`:

```python
"""Route each tenant to its own database (ADR-0002)."""

import threading
from collections import OrderedDict
from typing import Any, ClassVar
from uuid import UUID

from erp.core.db import Database, DbCredentials, TenantDbLocator
from erp.core.errors import NotFoundError, ServiceUnavailableError
from erp.modules.platform.registry_repository import TenantRepository


class TenantUnavailableError(ServiceUnavailableError):
    code = "TENANT_UNAVAILABLE"


class TenantDatabaseRouter:
    """One small pool per recently used tenant database (LRU-bounded).

    Build one router per runtime role: erp_app for the API and workers,
    erp_relay for the outbox relay. Call evict() after moving or
    restoring a tenant database.
    """

    DEFAULT_POOL: ClassVar[dict[str, int]] = {
        "pool_size": 2,
        "max_overflow": 3,
        "pool_recycle": 1800,
    }

    def __init__(
        self,
        registry: Database,
        locator: TenantDbLocator,
        credentials: DbCredentials,
        *,
        max_cached: int = 200,
        **engine_kwargs: Any,
    ) -> None:
        self._registry = registry
        self._locator = locator
        self._credentials = credentials
        self._max_cached = max_cached
        self._engine_kwargs = self.DEFAULT_POOL | engine_kwargs
        self._cache: OrderedDict[UUID, Database] = OrderedDict()
        self._lock = threading.Lock()

    def for_tenant(self, tenant_id: UUID) -> Database:
        with self._lock:
            cached = self._cache.get(tenant_id)
            if cached is not None:
                self._cache.move_to_end(tenant_id)
                return cached
        server, database_name = self._placement(tenant_id)
        url = self._locator.url(server, database_name, self._credentials)
        database = Database(url, **self._engine_kwargs)
        with self._lock:
            existing = self._cache.get(tenant_id)
            if existing is not None:  # another thread won the race
                database.dispose()
                return existing
            self._cache[tenant_id] = database
            while len(self._cache) > self._max_cached:
                _, evicted = self._cache.popitem(last=False)
                evicted.dispose()
        return database

    def active_tenant_ids(self) -> list[UUID]:
        with self._registry.platform_session() as s:
            return TenantRepository(s).active_ids()

    def evict(self, tenant_id: UUID) -> None:
        with self._lock:
            evicted = self._cache.pop(tenant_id, None)
        if evicted is not None:
            evicted.dispose()

    def dispose_all(self) -> None:
        with self._lock:
            databases = list(self._cache.values())
            self._cache.clear()
        for database in databases:
            database.dispose()

    def _placement(self, tenant_id: UUID) -> tuple[str, str]:
        with self._registry.platform_session() as s:
            tenant = TenantRepository(s).get(tenant_id)
        if tenant is None:
            raise NotFoundError("unknown tenant", code="TENANT_NOT_FOUND")
        if tenant.database_status != "ready":
            raise TenantUnavailableError("the tenant database is not available")
        return tenant.database_server, tenant.database_name
```

`backend/src/erp/modules/platform/interface.py`:

```python
"""Public surface of the platform module; import only from here."""

from erp.modules.platform.tenant_db import TenantDatabaseRouter, TenantUnavailableError

__all__ = ["TenantDatabaseRouter", "TenantUnavailable"]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass, including 11 in `test_tenant_isolation.py` and `test_tenant_models_match_migrations`.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat(platform): tenant database router with in-database isolation"
```

---

### Task 7: Access-token verification

**Files:**
- Create: `backend/src/erp/core/security.py`
- Modify: `backend/src/erp/core/config.py`, `backend/tests/support.py`, `backend/tests/conftest.py`
- Test: `backend/tests/core/test_security.py`

**Interfaces:**
- Produces:
  - `VerifiedToken(issuer, subject, claims)`.
  - `TokenVerifier(*, issuer, audience, algorithms, key_resolver, leeway_seconds=30)` with `.verify(token)`.
  - `JwksKeyResolver(jwks_url)`, a callable token → key.
  - `KeyResolver` type alias.
  - `TEST_ISSUER`, `TEST_AUDIENCE`, `bearer(token)`, and fixtures `signing_key`, `verifier`, `make_token`.

- [ ] **Step 1: Test support and fixtures**

Append to `backend/tests/support.py`:

```python
TEST_ISSUER = "https://id.test/realms/staff"
TEST_AUDIENCE = "erp-api"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
```

Append to `backend/tests/conftest.py`. Merge these imports:
- `import time`
- `from collections.abc import Callable`
- `import jwt`
- `from cryptography.hazmat.primitives.asymmetric import rsa`
- `from erp.core.security import TokenVerifier`
- `TEST_AUDIENCE, TEST_ISSUER`, added to the `support` import

```python
@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def verifier(signing_key: rsa.RSAPrivateKey) -> TokenVerifier:
    public_key = signing_key.public_key()
    return TokenVerifier(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        algorithms=["RS256"],
        key_resolver=lambda _token: public_key,
    )


@pytest.fixture(scope="session")
def make_token(signing_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    def _make(
        subject: str | None = "alice",
        *,
        issuer: str = TEST_ISSUER,
        audience: str = TEST_AUDIENCE,
        expires_in: int = 300,
        algorithm: str = "RS256",
        key: object | None = None,
        **extra: object,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": now,
            "exp": now + expires_in,
            **extra,
        }
        if subject is None:
            del claims["sub"]
        return jwt.encode(claims, key or signing_key, algorithm=algorithm)

    return _make
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/core/test_security.py`:

```python
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from erp.core.errors import UnauthenticatedError
from erp.core.security import TokenVerifier
from support import TEST_ISSUER

FOREIGN_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_valid_token_is_accepted(verifier, make_token):
    verified = verifier.verify(make_token("alice"))

    assert (verified.issuer, verified.subject) == (TEST_ISSUER, "alice")


@pytest.mark.parametrize(
    "overrides",
    [
        {"issuer": "https://evil.test/realms/staff"},
        {"audience": "some-other-api"},
        {"expires_in": -120},
        {"subject": None},
        {"algorithm": "HS256", "key": "k" * 64},
        {"key": FOREIGN_KEY},
    ],
    ids=[
        "wrong-issuer",
        "wrong-audience",
        "expired",
        "missing-sub",
        "hmac-alg",
        "foreign-key",
    ],
)
def test_invalid_tokens_are_rejected(verifier, make_token, overrides):
    with pytest.raises(UnauthenticatedError):
        verifier.verify(make_token(**overrides))


def test_garbage_is_rejected(verifier):
    with pytest.raises(UnauthenticatedError):
        verifier.verify("not-a-jwt")


@pytest.mark.parametrize("algorithms", [["HS256"], ["none"], []])
def test_verifier_refuses_symmetric_or_empty_algorithms(algorithms):
    with pytest.raises(ValueError):
        TokenVerifier(
            issuer=TEST_ISSUER,
            audience="erp-api",
            algorithms=algorithms,
            key_resolver=lambda _t: None,
        )
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/test_security.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'erp.core.security'`

- [ ] **Step 4: Implement**

`backend/src/erp/core/security.py`:

```python
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

import jwt

from erp.core.errors import UnauthenticatedError

KeyResolver = Callable[[str], Any]


@dataclass(frozen=True)
class VerifiedToken:
    issuer: str
    subject: str
    claims: dict[str, Any] = field(repr=False)


class TokenVerifier:
    """Validate Keycloak access tokens (IAM-02).

    Checks signature, pinned issuer, audience and expiry. In production
    the key resolver reads the realm JWKS by `kid`, so signing-key
    rotation needs no restart.
    """

    REQUIRED_CLAIMS: ClassVar[list[str]] = ["exp", "iat", "iss", "aud", "sub"]

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: list[str],
        key_resolver: KeyResolver,
        leeway_seconds: int = 30,
    ) -> None:
        if not algorithms or any(
            a.lower() == "none" or a.startswith("HS") for a in algorithms
        ):
            raise ValueError("only asymmetric signing algorithms are allowed")
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)
        self._key_resolver = key_resolver
        self._leeway = leeway_seconds

    def verify(self, token: str) -> VerifiedToken:
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
            if algorithm not in self._algorithms:
                raise UnauthenticatedError("token algorithm is not allowed")
            claims = jwt.decode(
                token,
                self._key_resolver(token),
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": self.REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError("invalid access token") from exc
        return VerifiedToken(
            issuer=claims["iss"], subject=claims["sub"], claims=claims
        )


class JwksKeyResolver:
    """Resolve a token's verification key from a JWKS URL by `kid`."""

    def __init__(self, jwks_url: str) -> None:
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def __call__(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key
```

Add these fields to `Settings` in `backend/src/erp/core/config.py`, after `tenant_db_owner_password`:

```python
    oidc_issuer: str = "http://localhost:8180/realms/staff"
    oidc_audience: str = "erp-api"
    oidc_jwks_url: str = (
        "http://localhost:8180/realms/staff/protocol/openid-connect/certs"
    )
    oidc_algorithms: list[str] = ["RS256"]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/core/test_security.py -v`
Expected: `11 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat(core): OIDC token verification with pinned issuer and audience"
```

---

### Task 8: Tenant context, company service, controllers and the first tenant-scoped API

**Files:**
- Create: `backend/src/erp/core/deps.py`, `backend/src/erp/modules/platform/context.py`, `backend/src/erp/modules/platform/dependencies.py`, `backend/src/erp/modules/platform/repository.py`, `backend/src/erp/modules/platform/schemas.py`, `backend/src/erp/modules/platform/service.py`, `backend/src/erp/modules/platform/controller.py`
- Modify: `backend/src/erp/modules/platform/registry_repository.py` (add `IdentityRepository`, `MembershipRepository`), `backend/src/erp/modules/platform/interface.py`, `backend/src/erp/app.py`, `backend/tests/core/test_health.py`
- Test: `backend/tests/platform/test_context_api.py`

**Interfaces:**
- Produces:
  - `RequestState.registry(request)`, `RequestState.verifier(request)` and `Authentication.current_token(...)`.
  - `RequestContext(tenant_id, membership_id, identity_id)`, `TenantChoice`, and `TenantContextService(registry)` with `.provide`, `.choices(token)`, `.resolve(token, requested_tenant_id)`.
  - `TenantContextProvider.resolve` and `TenantDatabaseProvider.resolve` (FastAPI dependencies).
  - `CompanyRepository(session)` with `.add(company)` and `.page(*, limit, after) -> (items, next_cursor)`.
  - `CompanyService(database, context)` with `.provide` and `.list_page(*, limit, cursor)`.
  - `MeController` (`GET /api/v1/me/contexts`) and `CompanyController` (`GET /api/v1/companies?limit&cursor`).
  - `ApplicationFactory(*, registry=None, tenant_router=None, verifier=None).build()` with `/readyz`.
  - JSON is camelCase: `{"items": [{"companyId", "companyName", …}], "nextCursor": …}`.
  - Error codes: `IDENTITY_NOT_PROVISIONED`, `TENANT_ACCESS_DENIED`, `TENANT_SELECTION_REQUIRED`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/platform/test_context_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from erp.app import ApplicationFactory
from erp.modules.platform.models import Company
from erp.modules.platform.registry_models import Identity, Membership
from support import TEST_ISSUER, bearer


@pytest.fixture
def client(registry, router, verifier):
    factory = ApplicationFactory(
        registry=registry, tenant_router=router, verifier=verifier
    )
    return TestClient(factory.build())


@pytest.fixture
def people(registry, two_tenants):
    """alice: A · bob: A and B · carol: none · dave: suspended in A."""
    ids = {}
    for name in ("alice", "bob", "carol", "dave"):
        with registry.platform_session() as s:
            identity = Identity(issuer=TEST_ISSUER, subject=name)
            s.add(identity)
            s.flush()
            ids[name] = identity.identity_id

    def member(tenant_id, name, status="active"):
        with registry.tenant_session(tenant_id) as s:
            s.add(
                Membership(
                    tenant_id=tenant_id,
                    identity_id=ids[name],
                    membership_status=status,
                )
            )

    member(two_tenants.a, "alice")
    member(two_tenants.a, "bob")
    member(two_tenants.b, "bob")
    member(two_tenants.a, "dave", status="suspended")
    return ids


def _companies(client, token, tenant_id=None, query=""):
    headers = bearer(token)
    if tenant_id is not None:
        headers["X-Tenant-Id"] = str(tenant_id)
    return client.get(f"/api/v1/companies{query}", headers=headers)


def _names(response):
    return [c["companyName"] for c in response.json()["items"]]


def test_missing_token_is_401_problem(client):
    response = client.get("/api/v1/companies")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401(client):
    response = client.get("/api/v1/companies", headers=bearer("garbage"))

    assert response.status_code == 401


def test_unprovisioned_identity_is_403(client, make_token, people):
    response = _companies(client, make_token("mallory"))

    assert response.status_code == 403
    assert response.json()["code"] == "IDENTITY_NOT_PROVISIONED"


def test_single_membership_selects_tenant_automatically(client, make_token, people):
    response = _companies(client, make_token("alice"))

    assert response.status_code == 200
    assert _names(response) == ["Alpha Traders Ltd"]
    assert response.json()["nextCursor"] is None


def test_response_keys_are_camel_case(client, make_token, people):
    company = _companies(client, make_token("alice")).json()["items"][0]

    expected = {"companyId", "companyName", "countryCode", "baseCurrency", "timeZone"}
    assert set(company) == expected


def test_selecting_a_tenant_without_membership_is_denied(
    client, make_token, people, two_tenants
):
    response = _companies(client, make_token("alice"), tenant_id=two_tenants.b)

    assert response.status_code == 403
    assert response.json()["code"] == "TENANT_ACCESS_DENIED"


def test_multi_tenant_user_must_select_then_reads_that_database(
    client, make_token, people, two_tenants
):
    token = make_token("bob")

    unselected = _companies(client, token)
    selected = _companies(client, token, tenant_id=two_tenants.b)

    assert unselected.status_code == 400
    assert unselected.json()["code"] == "TENANT_SELECTION_REQUIRED"
    assert _names(selected) == ["Beta Foods Ltd"]


@pytest.mark.parametrize(
    "subject", ["carol", "dave"], ids=["no-membership", "suspended"]
)
def test_users_without_active_membership_are_denied(
    client, make_token, people, subject
):
    response = _companies(client, make_token(subject))

    assert response.status_code == 403
    assert response.json()["code"] == "TENANT_ACCESS_DENIED"


def test_me_contexts_lists_only_active_memberships(client, make_token, people):
    headers = bearer(make_token("bob"))

    response = client.get("/api/v1/me/contexts", headers=headers)

    assert response.status_code == 200
    numbers = [c["accountNumber"] for c in response.json()]
    assert numbers == ["100001", "100002"]


def test_companies_pagination_uses_cursor(
    client, make_token, people, router, two_tenants
):
    a = two_tenants.a
    with router.for_tenant(a).tenant_session(a) as s:
        s.add(
            Company(
                tenant_id=a,
                company_name="Alpha Retail Ltd",
                country_code="BD",
                base_currency="BDT",
                time_zone="Asia/Dhaka",
            )
        )
    token = make_token("alice")

    first = _companies(client, token, query="?limit=1").json()
    cursor = first["nextCursor"]
    second = _companies(client, token, query=f"?limit=1&cursor={cursor}").json()

    assert len(first["items"]) == 1 and cursor is not None
    assert len(second["items"]) == 1 and second["nextCursor"] is None
    first_id = first["items"][0]["companyId"]
    assert first_id != second["items"][0]["companyId"]
```

Append to `backend/tests/core/test_health.py`:

```python
def test_readyz_checks_the_registry(registry):
    app = ApplicationFactory(registry=registry).build()

    response = TestClient(app).get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_without_registry_is_503():
    response = TestClient(ApplicationFactory().build()).get("/readyz")

    assert response.status_code == 503
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/platform/test_context_api.py tests/core/test_health.py -v`
Expected: FAIL with `TypeError: ApplicationFactory() takes no arguments`

- [ ] **Step 3: Request dependencies and repositories**

`backend/src/erp/core/deps.py`:

```python
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from erp.core.db import Database
from erp.core.errors import UnauthenticatedError
from erp.core.security import TokenVerifier, VerifiedToken

BEARER = HTTPBearer(auto_error=False)


class RequestState:
    """Accessors for objects the app factory put on app.state."""

    @staticmethod
    def registry(request: Request) -> Database:
        return request.app.state.registry

    @staticmethod
    def verifier(request: Request) -> TokenVerifier:
        return request.app.state.verifier


class Authentication:
    """Bearer-token authentication (IAM-02)."""

    @staticmethod
    def current_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)],
        verifier: Annotated[TokenVerifier, Depends(RequestState.verifier)],
    ) -> VerifiedToken:
        if credentials is None:
            raise UnauthenticatedError("missing bearer token")
        return verifier.verify(credentials.credentials)
```

Append to `backend/src/erp/modules/platform/registry_repository.py` (merge imports: `from sqlalchemy.engine import Row`, `Identity` and `Membership` into the registry_models import):

```python
class IdentityRepository:
    """All queries on registry "Identities"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_id(self, issuer: str, subject: str) -> UUID | None:
        return self._session.scalar(
            select(Identity.identity_id).where(
                Identity.issuer == issuer, Identity.subject == subject
            )
        )


class MembershipRepository:
    """All queries on registry "Memberships".

    Reads rely on the identity context of the session (RLS).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_staff_tenants(self) -> list[Row]:
        """Active staff memberships with their tenant's name/number."""
        return list(
            self._session.execute(
                select(
                    Membership.membership_id,
                    Tenant.tenant_id,
                    Tenant.account_number,
                    Tenant.tenant_name,
                )
                .join(Tenant, Tenant.tenant_id == Membership.tenant_id)
                .where(
                    Membership.membership_kind == "staff",
                    Membership.membership_status == "active",
                    Tenant.tenant_status == "active",
                )
                .order_by(Tenant.account_number)
            )
        )
```

`backend/src/erp/modules/platform/repository.py`:

```python
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

    def page(
        self, *, limit: int, after: UUID | None
    ) -> tuple[list[Company], UUID | None]:
        """Keyset page ordered by companyId (uuidv7 is time-ordered)."""
        stmt = select(Company).order_by(Company.company_id).limit(limit + 1)
        if after is not None:
            stmt = stmt.where(Company.company_id > after)
        rows = list(self._session.scalars(stmt))
        items = rows[:limit]
        next_cursor = items[-1].company_id if len(rows) > limit else None
        return items, next_cursor
```

- [ ] **Step 4: Context service and tenant dependencies**

`backend/src/erp/modules/platform/context.py`:

```python
from dataclasses import dataclass
from typing import Annotated, Self
from uuid import UUID

from fastapi import Depends

from erp.core.db import Database
from erp.core.deps import RequestState
from erp.core.errors import DomainError, ForbiddenError
from erp.core.security import VerifiedToken
from erp.modules.platform.registry_repository import (
    IdentityRepository,
    MembershipRepository,
)


@dataclass(frozen=True)
class RequestContext:
    tenant_id: UUID
    membership_id: UUID
    identity_id: UUID


@dataclass(frozen=True)
class TenantChoice:
    tenant_id: UUID
    account_number: str
    tenant_name: str


@dataclass(frozen=True)
class ActiveMembership:
    membership_id: UUID
    tenant: TenantChoice


class TenantSelectionRequiredError(DomainError):
    status = 400
    code = "TENANT_SELECTION_REQUIRED"
    title = "Tenant selection required"


class TenantContextService:
    """Select a request's tenant from verified memberships (TEN-03)."""

    def __init__(self, registry: Database) -> None:
        self._registry = registry

    @classmethod
    def provide(
        cls, registry: Annotated[Database, Depends(RequestState.registry)]
    ) -> Self:
        return cls(registry)

    def choices(self, token: VerifiedToken) -> list[TenantChoice]:
        _, memberships = self._active_memberships(token)
        return [m.tenant for m in memberships]

    def resolve(
        self, token: VerifiedToken, requested_tenant_id: UUID | None
    ) -> RequestContext:
        identity_id, memberships = self._active_memberships(token)
        chosen = self._choose(memberships, requested_tenant_id)
        return RequestContext(
            chosen.tenant.tenant_id, chosen.membership_id, identity_id
        )

    @staticmethod
    def _choose(
        memberships: list[ActiveMembership], requested: UUID | None
    ) -> ActiveMembership:
        if requested is None:
            if not memberships:
                raise ForbiddenError(
                    "no active membership", code="TENANT_ACCESS_DENIED"
                )
            if len(memberships) > 1:
                raise TenantSelectionRequiredError(
                    "select a tenant with the X-Tenant-Id header"
                )
            return memberships[0]
        for membership in memberships:
            if membership.tenant.tenant_id == requested:
                return membership
        raise ForbiddenError(
            "no active membership for the requested tenant",
            code="TENANT_ACCESS_DENIED",
        )

    def _active_memberships(
        self, token: VerifiedToken
    ) -> tuple[UUID, list[ActiveMembership]]:
        with self._registry.platform_session() as s:
            identity_id = IdentityRepository(s).find_id(
                token.issuer, token.subject
            )
        if identity_id is None:
            raise ForbiddenError(
                "identity is not provisioned", code="IDENTITY_NOT_PROVISIONED"
            )
        with self._registry.platform_session(identity_id=identity_id) as s:
            rows = MembershipRepository(s).active_staff_tenants()
        memberships = [
            ActiveMembership(
                row.membership_id,
                TenantChoice(row.tenant_id, row.account_number, row.tenant_name),
            )
            for row in rows
        ]
        return identity_id, memberships
```

`backend/src/erp/modules/platform/dependencies.py`:

```python
"""FastAPI dependencies for tenant-scoped requests (class-based)."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from erp.core.db import Database
from erp.core.deps import Authentication, RequestState
from erp.core.security import VerifiedToken
from erp.modules.platform.context import RequestContext, TenantContextService
from erp.modules.platform.tenant_db import TenantDatabaseRouter


class TenantContextProvider:
    """Dependency: the verified tenant context of the request."""

    @staticmethod
    def resolve(
        token: Annotated[VerifiedToken, Depends(Authentication.current_token)],
        registry: Annotated[Database, Depends(RequestState.registry)],
        x_tenant_id: Annotated[UUID | None, Header()] = None,
    ) -> RequestContext:
        return TenantContextService(registry).resolve(token, x_tenant_id)


class TenantDatabaseProvider:
    """Dependency: the selected tenant's own database."""

    @staticmethod
    def resolve(
        context: Annotated[RequestContext, Depends(TenantContextProvider.resolve)],
        request: Request,
    ) -> Database:
        tenant_router: TenantDatabaseRouter = request.app.state.tenant_router
        return tenant_router.for_tenant(context.tenant_id)
```

- [ ] **Step 5: Schemas, service, controllers**

`backend/src/erp/modules/platform/schemas.py`:

```python
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
```

`backend/src/erp/modules/platform/service.py`:

```python
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
            companies, next_cursor = CompanyRepository(s).page(
                limit=limit, after=cursor
            )
            items = [CompanyOut.model_validate(c) for c in companies]
        return CompanyPage(items=items, next_cursor=next_cursor)
```

`backend/src/erp/modules/platform/controller.py`:

```python
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
        service: Annotated[
            TenantContextService, Depends(TenantContextService.provide)
        ],
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
```

Replace `backend/src/erp/modules/platform/interface.py` with:

```python
"""Public surface of the platform module; import only from here."""

from erp.modules.platform.context import RequestContext, TenantContextService
from erp.modules.platform.dependencies import (
    TenantContextProvider,
    TenantDatabaseProvider,
)
from erp.modules.platform.tenant_db import TenantDatabaseRouter, TenantUnavailableError

__all__ = [
    "RequestContext",
    "TenantContextProvider",
    "TenantContextService",
    "TenantDatabaseProvider",
    "TenantDatabaseRouter",
    "TenantUnavailable",
]
```

Replace `backend/src/erp/app.py` with:

```python
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
            self.router.add_api_route(
                path, endpoint, methods=["GET"], include_in_schema=False
            )

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
```

- [ ] **Step 6: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass, including 11 in `test_context_api.py` and 3 in `test_health.py`.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat(platform): tenant context, CompanyService and controllers"
```

---

### Task 9: Append-only audit events

**Files:**
- Create: `backend/src/erp/modules/platform/audit.py`, `backend/migrations/tenant/versions/t0003_platform_audit_events.py`
- Modify: `backend/src/erp/modules/platform/models.py` (add `AuditEvent`), `backend/src/erp/modules/platform/repository.py` (add `AuditEventRepository`)
- Test: `backend/tests/platform/test_audit.py`

**Interfaces:**
- Produces:
  - Model `AuditEvent` (`audit_event_id, tenant_id, occurred_at, actor_identity_id, audit_action, target_type, target_id, audit_outcome, audit_reason, audit_details`).
  - `AuditEventRepository(session).add(event) -> UUID`.
  - `Redactor.REDACTED` and `Redactor.redact(value)`.
  - `AuditTrail(session).record(*, tenant_id, actor_identity_id, action, target_type, target_id, outcome, reason=None, details=None) -> UUID`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/platform/test_audit.py`:

```python
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from erp.modules.platform.audit import AuditTrail, Redactor
from erp.modules.platform.models import AuditEvent

REDACTED = Redactor.REDACTED


def test_redact_masks_sensitive_keys_recursively():
    value = {
        "user": "alice",
        "password": "pw",
        "nested": {"api_secret": "s", "items": [{"refresh_token": "t", "qty": 2}]},
        "Authorization": "Bearer x",
        "salary": "90000",
    }

    assert Redactor.redact(value) == {
        "user": "alice",
        "password": REDACTED,
        "nested": {
            "api_secret": REDACTED,
            "items": [{"refresh_token": REDACTED, "qty": 2}],
        },
        "Authorization": REDACTED,
        "salary": REDACTED,
    }


def _record(router, tenant_id, **details):
    with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
        return AuditTrail(s).record(
            tenant_id=tenant_id,
            actor_identity_id=None,
            action="platform.company.create",
            target_type="company",
            target_id="c-1",
            outcome="success",
            details=details,
        )


def test_event_is_redacted_and_stays_in_the_tenant_database(router, two_tenants):
    a, b = two_tenants.a, two_tenants.b
    event_id = _record(router, a, name="Alpha", password="pw")

    with router.for_tenant(a).tenant_session(a) as s:
        details = s.get(AuditEvent, event_id).audit_details
    with router.for_tenant(b).tenant_session(b) as s:
        in_b = s.scalars(select(AuditEvent)).all()

    assert details == {"name": "Alpha", "password": REDACTED}
    assert in_b == []


@pytest.mark.parametrize("statement", ["update", "delete"])
def test_runtime_role_cannot_modify_audit_history(router, two_tenants, statement):
    a = two_tenants.a
    event_id = _record(router, a)
    matches = AuditEvent.audit_event_id == event_id
    stmt = (
        update(AuditEvent).where(matches).values(audit_outcome="failure")
        if statement == "update"
        else delete(AuditEvent).where(matches)
    )

    with pytest.raises(DBAPIError, match="permission denied"):
        with router.for_tenant(a).tenant_session(a) as s:
            s.execute(stmt)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/platform/test_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.modules.platform.audit'`

- [ ] **Step 3: Model, migration, repository, service**

Append to `backend/src/erp/modules/platform/models.py` (merge imports: `from typing import Any`, `Text` into the sqlalchemy import, `from sqlalchemy.dialects.postgresql import JSONB`):

```python
class AuditEvent(TenantBase):
    """Append-only record of sensitive actions (IAM-04).

    The runtime role may only INSERT and SELECT. actorIdentityId points
    to registry "Identities" in another database, so it has no FK.
    """

    __tablename__ = "AuditEvents"
    __table_args__ = (
        UniqueConstraint("tenantId", "auditEventId"),
        CheckConstraint(
            "\"auditOutcome\" in ('success', 'denied', 'failure')",
            name="auditOutcome",
        ),
        SCHEMA,
    )

    audit_event_id: Mapped[uuid.UUID] = Columns.uuid_pk("auditEventId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    occurred_at: Mapped[datetime] = Columns.timestamp("occurredAt")
    actor_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        "actorIdentityId"
    )
    audit_action: Mapped[str] = mapped_column("auditAction", String(100))
    target_type: Mapped[str] = mapped_column("targetType", String(100))
    target_id: Mapped[str | None] = mapped_column("targetId", String(100))
    audit_outcome: Mapped[str] = mapped_column("auditOutcome", String(16))
    audit_reason: Mapped[str | None] = mapped_column("auditReason", Text)
    audit_details: Mapped[dict[str, Any]] = mapped_column(
        "auditDetails", JSONB, server_default=sql("'{}'::jsonb")
    )
```

`backend/migrations/tenant/versions/t0003_platform_audit_events.py`:

```python
"""tenant DB: append-only platform AuditEvents"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "t0003"
down_revision = "t0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "AuditEvents",
        cols.uuid("auditEventId"),
        cols.owner_tenant_id("AuditEvents"),
        cols.timestamp("occurredAt"),
        sa.Column("actorIdentityId", sa.Uuid(), nullable=True),
        sa.Column("auditAction", sa.String(100), nullable=False),
        sa.Column("targetType", sa.String(100), nullable=False),
        sa.Column("targetId", sa.String(100), nullable=True),
        sa.Column("auditOutcome", sa.String(16), nullable=False),
        sa.Column("auditReason", sa.Text(), nullable=True),
        sa.Column(
            "auditDetails",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("auditEventId", name="pk_AuditEvents"),
        sa.UniqueConstraint(
            "tenantId", "auditEventId", name="uq_AuditEvents_tenantId_auditEventId"
        ),
        sa.CheckConstraint(
            "\"auditOutcome\" in ('success', 'denied', 'failure')",
            name="ck_AuditEvents_auditOutcome",
        ),
        schema="platform",
    )
    for statement in RlsSql.tenant_policy("platform", "AuditEvents"):
        op.execute(statement)
    audit_events = RlsSql.table_ref("platform", "AuditEvents")
    op.execute(f"REVOKE UPDATE ON {audit_events} FROM erp_app")


def downgrade() -> None:
    op.drop_table("AuditEvents", schema="platform")
```

Append to `backend/src/erp/modules/platform/repository.py` (add `AuditEvent` to the models import):

```python
class AuditEventRepository:
    """Inserts into platform "AuditEvents" (append-only)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: AuditEvent) -> UUID:
        self._session.add(event)
        self._session.flush()
        return event.audit_event_id
```

`backend/src/erp/modules/platform/audit.py`:

```python
from collections.abc import Mapping
from typing import Any, ClassVar, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from erp.modules.platform.models import AuditEvent
from erp.modules.platform.repository import AuditEventRepository


class Redactor:
    """Mask secrets and sensitive payroll values in audit details."""

    REDACTED = "[REDACTED]"
    MARKERS: ClassVar[tuple[str, ...]] = (
        "password",
        "secret",
        "token",
        "authorization",
        "salary",
        "bank_account",
        "card_number",
    )

    @classmethod
    def is_sensitive(cls, key: str) -> bool:
        lowered = key.lower()
        return any(marker in lowered for marker in cls.MARKERS)

    @classmethod
    def redact(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                k: cls.REDACTED if cls.is_sensitive(str(k)) else cls.redact(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [cls.redact(v) for v in value]
        return value


class AuditTrail:
    """Record audit events inside the caller's transaction.

    Events commit or roll back together with the audited change.
    """

    def __init__(self, session: Session) -> None:
        self._events = AuditEventRepository(session)

    def record(
        self,
        *,
        tenant_id: UUID,
        actor_identity_id: UUID | None,
        action: str,
        target_type: str,
        target_id: str | None,
        outcome: Literal["success", "denied", "failure"],
        reason: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> UUID:
        return self._events.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_identity_id=actor_identity_id,
                audit_action=action,
                target_type=target_type,
                target_id=target_id,
                audit_outcome=outcome,
                audit_reason=reason,
                audit_details=Redactor.redact(dict(details or {})),
            )
        )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass, including 4 in `test_audit.py` and both drift tests.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat(platform): append-only redacted AuditEvents per tenant database"
```

---

### Task 10: Per-tenant outbox, relay pass over all tenant databases, consumer deduplication

**Files:**
- Create: `backend/src/erp/modules/integration/__init__.py` (empty), `backend/src/erp/modules/integration/models.py`, `backend/src/erp/modules/integration/repository.py`, `backend/src/erp/modules/integration/outbox.py`, `backend/migrations/tenant/versions/t0004_integration_outbox.py`
- Modify: `backend/src/erp/model_registry.py`, `backend/tests/conftest.py`
- Test: `backend/tests/outbox/test_outbox.py`

**Interfaces:**
- Consumes: `TenantDatabaseRouter` (via `erp.modules.platform.interface`), `Database`, `Columns`, `MigrationColumns`, `RlsSql`.
- Produces:
  - Models `OutboxEvent` (`outbox_event_id, tenant_id, event_topic, event_payload, occurred_at, dispatched_at, attempt_count, last_error`) and `ProcessedEvent` (`consumer_name, event_id, tenant_id, processed_at`).
  - `OutboxEventRepository(session)` with `.add(event)` and `.claim_pending(*, batch_size, max_attempts)`.
  - `ProcessedEventRepository(session)` with `.claim(*, consumer, event_id, tenant_id) -> bool`.
  - `OutboxMessage(event_id, tenant_id, topic, payload)`.
  - `Outbox(session).enqueue(*, tenant_id, topic, payload) -> UUID`.
  - `OutboxRelay(database, publish, *, batch_size=100, max_attempts=10).run_once() -> int`.
  - `TenantOutboxRelay(router, publish, **relay_kwargs).run_pass() -> int`.
  - `EventInbox(session).consume_once(*, consumer, message) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/conftest.py` (add `RELAY` to the `support` import):

```python
@pytest.fixture(scope="session")
def relay_router(
    _registry: Database,
    locator: TenantDbLocator,
    provisioner: TenantProvisioner,
) -> Iterator[TenantDatabaseRouter]:
    """Tenant DBs as erp_relay: access to "OutboxEvents" only."""
    relay = TenantDatabaseRouter(_registry, locator, RELAY)
    yield relay
    relay.dispose_all()
```

`backend/tests/outbox/test_outbox.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from erp.modules.integration.models import OutboxEvent
from erp.modules.integration.outbox import (
    EventInbox,
    Outbox,
    OutboxMessage,
    OutboxRelay,
    TenantOutboxRelay,
)


def _enqueue(router, tenant_id, n=1):
    with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
        return Outbox(s).enqueue(
            tenant_id=tenant_id, topic="test.happened", payload={"n": n}
        )


def test_enqueue_rolls_back_with_the_business_transaction(
    router, relay_router, two_tenants
):
    a = two_tenants.a
    with pytest.raises(RuntimeError):
        with router.for_tenant(a).tenant_session(a) as s:
            Outbox(s).enqueue(tenant_id=a, topic="test.happened", payload={})
            raise RuntimeError("business rule failed")

    relay = OutboxRelay(relay_router.for_tenant(a), lambda m: None)
    assert relay.run_once() == 0


def test_relay_pass_publishes_every_tenant_database_once(
    router, relay_router, two_tenants
):
    _enqueue(router, two_tenants.a)
    _enqueue(router, two_tenants.b)
    published: list[OutboxMessage] = []
    relay = TenantOutboxRelay(relay_router, published.append)

    assert relay.run_pass() == 2
    assert relay.run_pass() == 0
    tenants = {m.tenant_id for m in published}
    assert tenants == {two_tenants.a, two_tenants.b}


def test_relay_pass_skips_an_unreachable_tenant(router, relay_router, two_tenants):
    _enqueue(router, two_tenants.a)
    broken = uuid4()

    class RouterWithBrokenTenant:
        def active_tenant_ids(self):
            return [broken, *relay_router.active_tenant_ids()]

        def for_tenant(self, tenant_id):
            if tenant_id == broken:
                raise ConnectionError("tenant database down")
            return relay_router.for_tenant(tenant_id)

    published: list[OutboxMessage] = []
    relay = TenantOutboxRelay(RouterWithBrokenTenant(), published.append)

    assert relay.run_pass() == 1


def test_failed_publish_is_retried_on_next_run(router, relay_router, two_tenants):
    _enqueue(router, two_tenants.a)
    calls: list[OutboxMessage] = []

    def flaky(message: OutboxMessage) -> None:
        calls.append(message)
        if len(calls) == 1:
            raise ConnectionError("broker unavailable")

    relay = OutboxRelay(relay_router.for_tenant(two_tenants.a), flaky)

    assert relay.run_once() == 0
    assert relay.run_once() == 1
    assert len(calls) == 2


def test_events_past_max_attempts_stop_being_retried(
    router, relay_router, two_tenants
):
    _enqueue(router, two_tenants.a)
    calls = []

    def always_fails(message: OutboxMessage) -> None:
        calls.append(message)
        raise ConnectionError("broker unavailable")

    relay = OutboxRelay(
        relay_router.for_tenant(two_tenants.a), always_fails, max_attempts=2
    )
    for _ in range(3):
        relay.run_once()

    assert len(calls) == 2


def test_wrong_context_cannot_read_a_tenants_outbox(router, two_tenants):
    _enqueue(router, two_tenants.a)

    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.b) as s:
        assert s.scalars(select(OutboxEvent)).all() == []


def test_relay_role_cannot_read_business_tables(relay_router, two_tenants):
    database = relay_router.for_tenant(two_tenants.a)
    with pytest.raises(DBAPIError, match="permission denied"):
        with database.platform_session() as s:
            s.execute(text('select * from platform."Companies"'))


def test_redelivered_event_has_a_single_effect(router, relay_router, two_tenants):
    """E2E-12 seed: the relay's commit is lost after publishing."""
    event_id = _enqueue(router, two_tenants.a)
    published: list[OutboxMessage] = []
    relay_db = relay_router.for_tenant(two_tenants.a)
    OutboxRelay(relay_db, published.append).run_once()
    with relay_db.platform_session() as s:
        s.execute(
            update(OutboxEvent)
            .where(OutboxEvent.outbox_event_id == event_id)
            .values(dispatched_at=None)
        )
    OutboxRelay(relay_db, published.append).run_once()

    effects = []
    for message in published:
        database = router.for_tenant(message.tenant_id)
        with database.tenant_session(message.tenant_id) as s:
            inbox = EventInbox(s)
            if inbox.consume_once(consumer="test-consumer", message=message):
                effects.append(message.event_id)

    assert len(published) == 2
    assert effects == [event_id]


def test_consumer_failure_releases_the_dedup_record(router, two_tenants):
    a = two_tenants.a
    message = OutboxMessage(uuid4(), a, "test.happened", {})
    tenant_db = router.for_tenant(a)

    with pytest.raises(RuntimeError):
        with tenant_db.tenant_session(a) as s:
            assert EventInbox(s).consume_once(consumer="c", message=message)
            raise RuntimeError("handler crashed")
    with tenant_db.tenant_session(a) as s:
        assert EventInbox(s).consume_once(consumer="c", message=message)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/outbox -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.modules.integration'`

- [ ] **Step 3: Models, repository and migration**

`backend/src/erp/modules/integration/models.py`:

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import Columns, TenantBase

SCHEMA = {"schema": "integration"}


class OutboxEvent(TenantBase):
    __tablename__ = "OutboxEvents"
    __table_args__ = (
        UniqueConstraint("tenantId", "outboxEventId"),
        Index(
            "ix_OutboxEvents_pending",
            "occurredAt",
            postgresql_where=sql('"dispatchedAt" IS NULL'),
        ),
        SCHEMA,
    )

    outbox_event_id: Mapped[uuid.UUID] = Columns.uuid_pk("outboxEventId")
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    event_topic: Mapped[str] = mapped_column("eventTopic", String(200))
    event_payload: Mapped[dict[str, Any]] = mapped_column("eventPayload", JSONB)
    occurred_at: Mapped[datetime] = Columns.timestamp("occurredAt")
    dispatched_at: Mapped[datetime | None] = mapped_column("dispatchedAt")
    attempt_count: Mapped[int] = mapped_column(
        "attemptCount", server_default=sql("0")
    )
    last_error: Mapped[str | None] = mapped_column("lastError", String(500))


class ProcessedEvent(TenantBase):
    """One row per (consumer, event) handled.

    Written inside the consumer's business transaction.
    """

    __tablename__ = "ProcessedEvents"
    __table_args__ = (SCHEMA,)

    consumer_name: Mapped[str] = mapped_column(
        "consumerName", String(100), primary_key=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column("eventId", primary_key=True)
    tenant_id: Mapped[uuid.UUID] = Columns.tenant_id()
    processed_at: Mapped[datetime] = Columns.timestamp("processedAt")
```

`backend/src/erp/modules/integration/repository.py`:

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from erp.modules.integration.models import OutboxEvent, ProcessedEvent


class OutboxEventRepository:
    """All queries on integration "OutboxEvents"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: OutboxEvent) -> UUID:
        self._session.add(event)
        self._session.flush()
        return event.outbox_event_id

    def claim_pending(
        self, *, batch_size: int, max_attempts: int
    ) -> list[OutboxEvent]:
        """Lock the oldest undispatched events, skipping locked rows."""
        return list(
            self._session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.dispatched_at.is_(None),
                    OutboxEvent.attempt_count < max_attempts,
                )
                .order_by(OutboxEvent.occurred_at, OutboxEvent.outbox_event_id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )


class ProcessedEventRepository:
    """All queries on integration "ProcessedEvents"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(self, *, consumer: str, event_id: UUID, tenant_id: UUID) -> bool:
        """Insert the (consumer, event) key; False if it exists."""
        statement = (
            insert(ProcessedEvent)
            .values(
                {
                    ProcessedEvent.consumer_name: consumer,
                    ProcessedEvent.event_id: event_id,
                    ProcessedEvent.tenant_id: tenant_id,
                }
            )
            .on_conflict_do_nothing(index_elements=["consumerName", "eventId"])
            .returning(ProcessedEvent.event_id)
        )
        return self._session.execute(statement).first() is not None
```

Append to `backend/src/erp/model_registry.py`:

```python
from erp.modules.integration import models as integration_models  # noqa: F401
```

`backend/migrations/tenant/versions/t0004_integration_outbox.py`:

```python
"""tenant DB: integration OutboxEvents and ProcessedEvents"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "t0004"
down_revision = "t0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "OutboxEvents",
        cols.uuid("outboxEventId"),
        cols.owner_tenant_id("OutboxEvents"),
        sa.Column("eventTopic", sa.String(200), nullable=False),
        sa.Column("eventPayload", JSONB(), nullable=False),
        cols.timestamp("occurredAt"),
        sa.Column("dispatchedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attemptCount", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("lastError", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("outboxEventId", name="pk_OutboxEvents"),
        sa.UniqueConstraint(
            "tenantId",
            "outboxEventId",
            name="uq_OutboxEvents_tenantId_outboxEventId",
        ),
        schema="integration",
    )
    op.create_index(
        "ix_OutboxEvents_pending",
        "OutboxEvents",
        ["occurredAt"],
        schema="integration",
        postgresql_where=sa.text('"dispatchedAt" IS NULL'),
    )
    op.create_table(
        "ProcessedEvents",
        sa.Column("consumerName", sa.String(100), nullable=False),
        sa.Column("eventId", sa.Uuid(), nullable=False),
        cols.owner_tenant_id("ProcessedEvents"),
        cols.timestamp("processedAt"),
        sa.PrimaryKeyConstraint(
            "consumerName", "eventId", name="pk_ProcessedEvents"
        ),
        schema="integration",
    )
    for table in ("OutboxEvents", "ProcessedEvents"):
        for statement in RlsSql.tenant_policy("integration", table):
            op.execute(statement)
    # The relay reads and marks this database's outbox without
    # BYPASSRLS, and can touch nothing else (ADR-0005).
    outbox = RlsSql.table_ref("integration", "OutboxEvents")
    op.execute(f"GRANT SELECT, UPDATE ON {outbox} TO erp_relay")
    op.execute(
        f'CREATE POLICY "relayDispatch" ON {outbox} TO erp_relay '
        "USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.drop_table("ProcessedEvents", schema="integration")
    op.drop_index(
        "ix_OutboxEvents_pending", "OutboxEvents", schema="integration"
    )
    op.drop_table("OutboxEvents", schema="integration")
```

- [ ] **Step 4: Outbox services**

`backend/src/erp/modules/integration/outbox.py`:

```python
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy.orm import Session

from erp.core.db import Database
from erp.modules.integration.models import OutboxEvent
from erp.modules.integration.repository import (
    OutboxEventRepository,
    ProcessedEventRepository,
)
from erp.modules.platform.interface import TenantDatabaseRouter


@dataclass(frozen=True)
class OutboxMessage:
    event_id: UUID
    tenant_id: UUID
    topic: str
    payload: dict[str, Any]


Publisher = Callable[[OutboxMessage], None]


class Outbox:
    """Add events to the caller's business transaction (ARC-03)."""

    def __init__(self, session: Session) -> None:
        self._events = OutboxEventRepository(session)

    def enqueue(
        self, *, tenant_id: UUID, topic: str, payload: dict[str, Any]
    ) -> UUID:
        return self._events.add(
            OutboxEvent(tenant_id=tenant_id, event_topic=topic, event_payload=payload)
        )


class OutboxRelay:
    """Publish one tenant DB's committed outbox rows at least once.

    Must use erp_relay credentials (ADR-0005). If the process dies after
    publishing but before committing, the events are published again;
    EventInbox makes that harmless.
    """

    def __init__(
        self,
        database: Database,
        publish: Publisher,
        *,
        batch_size: int = 100,
        max_attempts: int = 10,
    ) -> None:
        self._db = database
        self._publish = publish
        self._batch_size = batch_size
        self._max_attempts = max_attempts

    def run_once(self) -> int:
        published = 0
        with self._db.platform_session() as session:
            events = OutboxEventRepository(session).claim_pending(
                batch_size=self._batch_size, max_attempts=self._max_attempts
            )
            for event in events:
                if self._dispatch(event):
                    published += 1
        return published

    def _dispatch(self, event: OutboxEvent) -> bool:
        event.attempt_count += 1
        message = OutboxMessage(
            event.outbox_event_id,
            event.tenant_id,
            event.event_topic,
            event.event_payload,
        )
        try:
            self._publish(message)
        except Exception as exc:  # noqa: BLE001 - retried next run
            event.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return False
        event.dispatched_at = datetime.now(UTC)
        return True


class TenantOutboxRelay:
    """One relay pass over every active tenant database.

    An unreachable tenant is logged and skipped so it never blocks the
    others. Pass a router built with erp_relay credentials.
    """

    LOGGER: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(
        self, router: TenantDatabaseRouter, publish: Publisher, **relay_kwargs: Any
    ) -> None:
        self._router = router
        self._publish = publish
        self._relay_kwargs = relay_kwargs

    def run_pass(self) -> int:
        total = 0
        for tenant_id in self._router.active_tenant_ids():
            try:
                database = self._router.for_tenant(tenant_id)
                relay = OutboxRelay(database, self._publish, **self._relay_kwargs)
                total += relay.run_once()
            except Exception:  # noqa: BLE001 - isolate tenant failures
                self.LOGGER.exception("outbox relay failed for %s", tenant_id)
        return total


class EventInbox:
    """Exactly-once consumer effects over at-least-once delivery."""

    def __init__(self, session: Session) -> None:
        self._processed = ProcessedEventRepository(session)

    def consume_once(self, *, consumer: str, message: OutboxMessage) -> bool:
        """Claim (consumer, event) in the caller's transaction.

        Returns False if already processed. Apply the handler's effects
        in the same transaction: if the handler fails, the claim rolls
        back too and a retry can process the event.
        """
        return self._processed.claim(
            consumer=consumer,
            event_id=message.event_id,
            tenant_id=message.tenant_id,
        )
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass, including 9 in `tests/outbox/test_outbox.py` and both drift tests.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat(integration): per-tenant outbox, relay pass, consumer dedup"
```

---

### Task 11: Module system — manifests, dependency graph, per-tenant enable/disable

**Files:**
- Create: `backend/src/erp/core/modules.py`, `backend/src/erp/modules/platform/module.py`, `backend/src/erp/modules/integration/module.py`, `backend/src/erp/module_catalog.py`, `backend/src/erp/modules/platform/module_state.py`, `backend/migrations/registry/versions/r0003_registry_tenant_modules.py`
- Modify: `backend/src/erp/modules/platform/registry_models.py` (add `TenantModule`), `backend/src/erp/modules/platform/registry_repository.py` (add `TenantModuleRepository`), `backend/src/erp/modules/platform/dependencies.py` (add `ModuleGuard`), `backend/src/erp/modules/platform/interface.py`, `backend/src/erp/app.py`
- Test: `backend/tests/core/test_modules.py`, `backend/tests/platform/test_tenant_modules.py`, `backend/tests/platform/test_module_gating.py`

**Interfaces:**
- Produces:
  - `ModuleManifest(key, name, depends_on=(), core=False, controllers=())`, where `controllers` are `Controller` subclasses.
  - `ModuleCatalog(manifests)`, iterable in enable order, with `.get`, `.core_keys`, `.dependencies(key)` and `.dependents(key)`.
  - `ModuleCatalogError`.
  - `InstalledModules.MANIFESTS` and `InstalledModules.catalog()`.
  - `TenantModuleRepository(session)` with `.enabled_keys(tenant_id)` and `.upsert(tenant_id, key, *, is_enabled)`.
  - `TenantModules(registry, catalog)` with `.enabled`, `.require`, `.enable(tenant_id, key, *, with_dependencies=False)` and `.disable`.
  - `ModuleDisabledError` (403 `MODULE_DISABLED`) and `ModuleChangeRejectedError` (409 `MODULE_CHANGE_REJECTED`).
  - `ModuleGuard(module_key)` and `ApplicationFactory(..., catalog=None)`.
- The 50-app graph is **not** encoded here (pending `docs/plan/module-dependencies.md`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/core/test_modules.py`:

```python
import pytest

from erp.core.modules import ModuleCatalog, ModuleCatalogError, ModuleManifest


def manifest(key, depends_on=(), core=False):
    return ModuleManifest(key, key.title(), tuple(depends_on), core)


CATALOG = ModuleCatalog(
    [
        manifest("platform", core=True),
        manifest("catalog", ["platform"]),
        manifest("inventory", ["catalog"]),
        manifest("sales", ["inventory", "catalog"]),
        manifest("pos", ["sales"]),
    ]
)


def test_iteration_follows_enable_order():
    keys = [m.key for m in CATALOG]

    assert keys == ["platform", "catalog", "inventory", "sales", "pos"]


def test_dependencies_are_transitive_and_in_enable_order():
    expected = ["platform", "catalog", "inventory", "sales"]
    assert CATALOG.dependencies("pos") == expected


def test_dependents_are_transitive():
    assert CATALOG.dependents("inventory") == ["sales", "pos"]


def test_unknown_dependency_is_rejected():
    with pytest.raises(ModuleCatalogError, match="unknown module 'inventory'"):
        ModuleCatalog([manifest("sales", ["inventory"])])


def test_dependency_cycle_is_rejected():
    with pytest.raises(ModuleCatalogError, match="cycle"):
        ModuleCatalog([manifest("a", ["b"]), manifest("b", ["a"])])


def test_duplicate_key_is_rejected():
    with pytest.raises(ModuleCatalogError, match="duplicate"):
        ModuleCatalog([manifest("a"), manifest("a")])


def test_core_module_cannot_depend_on_an_optional_module():
    with pytest.raises(ModuleCatalogError, match="core module"):
        ModuleCatalog(
            [manifest("sales"), manifest("platform", ["sales"], core=True)]
        )
```

`backend/tests/platform/test_tenant_modules.py`:

```python
from uuid import uuid4

import pytest

from erp.core.modules import ModuleCatalog, ModuleManifest
from erp.modules.platform.module_state import (
    ModuleChangeRejectedError,
    ModuleDisabledError,
    TenantModules,
)
from erp.modules.platform.registry_models import Tenant

CATALOG = ModuleCatalog(
    [
        ModuleManifest("platform", "Platform", core=True),
        ModuleManifest("catalog", "Catalogue", ("platform",)),
        ModuleManifest("inventory", "Inventory", ("catalog",)),
        ModuleManifest("sales", "Sales", ("inventory", "catalog")),
    ]
)


@pytest.fixture
def modules(registry):
    return TenantModules(registry, CATALOG)


def _tenant(registry):
    with registry.platform_session() as s:
        tenant = Tenant(
            account_number=f"M{uuid4().hex[:12]}",
            tenant_name="Modules Ltd",
            database_name=f"unprovisioned_{uuid4().hex}",
        )
        s.add(tenant)
        s.flush()
        return tenant.tenant_id


def test_core_modules_are_always_enabled(modules, registry):
    assert modules.enabled(_tenant(registry)) == {"platform"}


def test_enabling_requires_dependencies_first(modules, registry):
    tenant_id = _tenant(registry)

    with pytest.raises(ModuleChangeRejectedError, match="catalog, inventory"):
        modules.enable(tenant_id, "sales")


def test_enabling_with_dependencies_enables_them_in_order(modules, registry):
    tenant_id = _tenant(registry)

    enabled = modules.enable(tenant_id, "sales", with_dependencies=True)

    assert enabled == ["catalog", "inventory", "sales"]
    expected = {"platform", "catalog", "inventory", "sales"}
    assert modules.enabled(tenant_id) == expected


def test_cannot_disable_a_module_enabled_modules_depend_on(modules, registry):
    tenant_id = _tenant(registry)
    modules.enable(tenant_id, "sales", with_dependencies=True)

    with pytest.raises(ModuleChangeRejectedError, match="sales"):
        modules.disable(tenant_id, "inventory")


def test_disable_then_re_enable(modules, registry):
    tenant_id = _tenant(registry)
    modules.enable(tenant_id, "sales", with_dependencies=True)

    modules.disable(tenant_id, "sales")
    assert "sales" not in modules.enabled(tenant_id)
    modules.enable(tenant_id, "sales")
    assert "sales" in modules.enabled(tenant_id)


def test_core_module_cannot_be_disabled(modules, registry):
    with pytest.raises(ModuleChangeRejectedError, match="core"):
        modules.disable(_tenant(registry), "platform")


def test_require_rejects_disabled_modules(modules, registry):
    tenant_id = _tenant(registry)

    with pytest.raises(ModuleDisabledError):
        modules.require(tenant_id, "catalog")
    modules.enable(tenant_id, "catalog")
    modules.require(tenant_id, "catalog")


def test_enablement_is_per_tenant(modules, registry):
    a, b = _tenant(registry), _tenant(registry)

    modules.enable(a, "catalog")

    assert "catalog" in modules.enabled(a)
    assert "catalog" not in modules.enabled(b)
```

`backend/tests/platform/test_module_gating.py`:

```python
from fastapi.testclient import TestClient

from erp.app import ApplicationFactory
from erp.core.controller import Controller
from erp.core.modules import ModuleCatalog, ModuleManifest
from erp.module_catalog import InstalledModules
from erp.modules.platform.registry_models import Identity, Membership
from support import TEST_ISSUER, bearer


class DemoController(Controller):
    prefix = "/api/v1/demo"
    tags = ("demo",)

    def register_routes(self) -> None:
        self.router.add_api_route("/ping", self.ping, methods=["GET"])

    def ping(self) -> dict[str, bool]:
        return {"pong": True}


def test_every_route_of_a_disabled_module_is_rejected(
    registry, router, verifier, make_token, two_tenants
):
    demo = ModuleManifest(
        "demo", "Demo", ("platform",), controllers=(DemoController,)
    )
    catalog = ModuleCatalog([*InstalledModules.MANIFESTS, demo])
    app = ApplicationFactory(
        registry=registry, tenant_router=router, verifier=verifier, catalog=catalog
    ).build()
    client = TestClient(app)
    with registry.platform_session() as s:
        identity = Identity(issuer=TEST_ISSUER, subject="alice")
        s.add(identity)
        s.flush()
        identity_id = identity.identity_id
    with registry.tenant_session(two_tenants.a) as s:
        s.add(Membership(tenant_id=two_tenants.a, identity_id=identity_id))
    headers = bearer(make_token("alice"))
    modules = app.state.tenant_modules

    disabled = client.get("/api/v1/demo/ping", headers=headers)
    modules.enable(two_tenants.a, "demo")
    enabled = client.get("/api/v1/demo/ping", headers=headers)
    modules.disable(two_tenants.a, "demo")
    disabled_again = client.get("/api/v1/demo/ping", headers=headers)

    assert disabled.status_code == 403
    assert disabled.json()["code"] == "MODULE_DISABLED"
    assert enabled.json() == {"pong": True}
    assert disabled_again.status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/test_modules.py tests/platform/test_tenant_modules.py tests/platform/test_module_gating.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.core.modules'`

- [ ] **Step 3: Catalog and manifests**

`backend/src/erp/core/modules.py`:

```python
"""Module system (ADR-0009): installed modules and dependencies."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from erp.core.controller import Controller


@dataclass(frozen=True)
class ModuleManifest:
    """Declared by each module in erp/modules/<key>/module.py."""

    key: str
    name: str
    depends_on: tuple[str, ...] = ()
    core: bool = False  # always enabled; can never be disabled
    controllers: tuple[type[Controller], ...] = field(
        default=(), compare=False, repr=False
    )


class ModuleCatalogError(ValueError):
    pass


class ModuleCatalog:
    """Every module installed in this build, validated as a DAG."""

    def __init__(self, manifests: Iterable[ModuleManifest]) -> None:
        self._modules: dict[str, ModuleManifest] = {}
        for manifest in manifests:
            if manifest.key in self._modules:
                raise ModuleCatalogError(
                    f"duplicate module key {manifest.key!r}"
                )
            self._modules[manifest.key] = manifest
        for manifest in self._modules.values():
            self._validate_dependencies(manifest)
        self._order = self._topological_order()

    def __iter__(self) -> Iterator[ModuleManifest]:
        return (self._modules[key] for key in self._order)

    def get(self, key: str) -> ModuleManifest:
        try:
            return self._modules[key]
        except KeyError:
            raise ModuleCatalogError(f"unknown module {key!r}") from None

    def core_keys(self) -> frozenset[str]:
        return frozenset(k for k, m in self._modules.items() if m.core)

    def dependencies(self, key: str) -> list[str]:
        """Transitive dependencies of `key`, in enable order."""
        needed: set[str] = set()
        stack = list(self.get(key).depends_on)
        while stack:
            dependency = stack.pop()
            if dependency not in needed:
                needed.add(dependency)
                stack.extend(self._modules[dependency].depends_on)
        return [k for k in self._order if k in needed]

    def dependents(self, key: str) -> list[str]:
        """Modules depending on `key`, transitively, in enable order."""
        self.get(key)
        return [k for k in self._order if key in self.dependencies(k)]

    def _validate_dependencies(self, manifest: ModuleManifest) -> None:
        for dependency in manifest.depends_on:
            if dependency not in self._modules:
                raise ModuleCatalogError(
                    f"{manifest.key!r} depends on unknown module {dependency!r}"
                )
            if manifest.core and not self._modules[dependency].core:
                raise ModuleCatalogError(
                    f"core module {manifest.key!r} cannot depend on "
                    f"optional module {dependency!r}"
                )

    def _topological_order(self) -> list[str]:
        remaining = {k: set(m.depends_on) for k, m in self._modules.items()}
        order: list[str] = []
        while remaining:
            ready = sorted(k for k, deps in remaining.items() if not deps)
            if not ready:
                raise ModuleCatalogError(
                    f"dependency cycle among {sorted(remaining)}"
                )
            for key in ready:
                order.append(key)
                del remaining[key]
            for deps in remaining.values():
                deps.difference_update(ready)
        return order
```

`backend/src/erp/modules/platform/module.py`:

```python
from erp.core.modules import ModuleManifest
from erp.modules.platform.controller import CompanyController, MeController

MODULE = ModuleManifest(
    key="platform",
    name="Platform",
    core=True,
    controllers=(MeController, CompanyController),
)
```

`backend/src/erp/modules/integration/module.py`:

```python
from erp.core.modules import ModuleManifest

MODULE = ModuleManifest(
    key="integration", name="Integration", depends_on=("platform",), core=True
)
```

`backend/src/erp/module_catalog.py`:

```python
from typing import ClassVar

from erp.core.modules import ModuleCatalog, ModuleManifest
from erp.modules.integration.module import MODULE as INTEGRATION
from erp.modules.platform.module import MODULE as PLATFORM


class InstalledModules:
    """Modules installed in this build; register each MODULE here."""

    MANIFESTS: ClassVar[tuple[ModuleManifest, ...]] = (PLATFORM, INTEGRATION)

    @classmethod
    def catalog(cls) -> ModuleCatalog:
        return ModuleCatalog(cls.MANIFESTS)
```

- [ ] **Step 4: Registry table, repository and enablement service**

Append to `backend/src/erp/modules/platform/registry_models.py`:

```python
class TenantModule(RegistryBase):
    """Whether a tenant enabled an optional module.

    Core modules have no row; they are always on. Disabling only flips
    isEnabled; the module's data is untouched (PLT-05).
    """

    __tablename__ = "TenantModules"
    __table_args__ = (SCHEMA,)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        "tenantId", ForeignKey("registry.Tenants.tenantId"), primary_key=True
    )
    module_key: Mapped[str] = mapped_column(
        "moduleKey", String(64), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column("isEnabled")
    changed_at: Mapped[datetime] = Columns.timestamp("changedAt")
```

`backend/migrations/registry/versions/r0003_registry_tenant_modules.py`:

```python
"""registry: per-tenant module enablement (TenantModules)"""

import sqlalchemy as sa
from alembic import op

from erp.core.migrations import MigrationColumns as cols
from erp.core.rls import RlsSql

revision = "r0003"
down_revision = "r0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TenantModules",
        cols.registry_tenant_id("TenantModules"),
        sa.Column("moduleKey", sa.String(64), nullable=False),
        sa.Column("isEnabled", sa.Boolean(), nullable=False),
        cols.timestamp("changedAt"),
        sa.PrimaryKeyConstraint(
            "tenantId", "moduleKey", name="pk_TenantModules"
        ),
        schema="registry",
    )
    for statement in RlsSql.tenant_policy("registry", "TenantModules"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("TenantModules", schema="registry")
```

Append to `backend/src/erp/modules/platform/registry_repository.py` (merge imports: `from sqlalchemy import func`, `from sqlalchemy.dialects.postgresql import insert`, `TenantModule` into the registry_models import):

```python
class TenantModuleRepository:
    """All queries on registry "TenantModules"."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enabled_keys(self, tenant_id: UUID) -> set[str]:
        return set(
            self._session.scalars(
                select(TenantModule.module_key).where(
                    TenantModule.tenant_id == tenant_id,
                    TenantModule.is_enabled.is_(True),
                )
            )
        )

    def upsert(self, tenant_id: UUID, key: str, *, is_enabled: bool) -> None:
        statement = (
            insert(TenantModule)
            .values(
                {
                    TenantModule.tenant_id: tenant_id,
                    TenantModule.module_key: key,
                    TenantModule.is_enabled: is_enabled,
                }
            )
            .on_conflict_do_update(
                index_elements=["tenantId", "moduleKey"],
                set_={"isEnabled": is_enabled, "changedAt": func.now()},
            )
        )
        self._session.execute(statement)
```

`backend/src/erp/modules/platform/module_state.py`:

```python
"""Per-tenant module enablement (ADR-0009, PLT-05)."""

from uuid import UUID

from sqlalchemy.orm import Session

from erp.core.db import Database
from erp.core.errors import ConflictError, ForbiddenError, NotFoundError
from erp.core.modules import ModuleCatalog
from erp.modules.platform.registry_repository import (
    TenantModuleRepository,
    TenantRepository,
)


class ModuleDisabledError(ForbiddenError):
    code = "MODULE_DISABLED"


class ModuleChangeRejectedError(ConflictError):
    code = "MODULE_CHANGE_REJECTED"


class TenantModules:
    """Enable, disable and check modules for one tenant at a time."""

    def __init__(self, registry: Database, catalog: ModuleCatalog) -> None:
        self._registry = registry
        self._catalog = catalog

    def enabled(self, tenant_id: UUID) -> frozenset[str]:
        with self._registry.tenant_session(tenant_id) as s:
            return self._enabled(s, tenant_id)

    def require(self, tenant_id: UUID, key: str) -> None:
        if key not in self.enabled(tenant_id):
            name = self._catalog.get(key).name
            raise ModuleDisabledError(
                f"the {name} module is not enabled for this account"
            )

    def enable(
        self, tenant_id: UUID, key: str, *, with_dependencies: bool = False
    ) -> list[str]:
        """Enable `key`; return the newly enabled modules in order.

        Missing dependencies are rejected unless the caller explicitly
        asks to enable them as well.
        """
        self._catalog.get(key)
        with self._registry.tenant_session(tenant_id) as s:
            self._lock(s, tenant_id)
            current = self._enabled(s, tenant_id)
            dependencies = self._catalog.dependencies(key)
            missing = [d for d in dependencies if d not in current]
            if missing and not with_dependencies:
                raise ModuleChangeRejectedError(
                    f"{key} requires {', '.join(missing)} to be enabled first"
                )
            newly_enabled = missing + ([] if key in current else [key])
            modules = TenantModuleRepository(s)
            for module_key in newly_enabled:
                modules.upsert(tenant_id, module_key, is_enabled=True)
        return newly_enabled

    def disable(self, tenant_id: UUID, key: str) -> None:
        if self._catalog.get(key).core:
            raise ModuleChangeRejectedError(
                f"{key} is a core module and cannot be disabled"
            )
        with self._registry.tenant_session(tenant_id) as s:
            self._lock(s, tenant_id)
            current = self._enabled(s, tenant_id)
            dependents = self._catalog.dependents(key)
            blocking = [d for d in dependents if d in current]
            if blocking:
                raise ModuleChangeRejectedError(
                    f"disable {', '.join(blocking)} before {key}"
                )
            if key in current:
                TenantModuleRepository(s).upsert(tenant_id, key, is_enabled=False)

    def _enabled(self, session: Session, tenant_id: UUID) -> frozenset[str]:
        installed = {m.key for m in self._catalog}
        stored = TenantModuleRepository(session).enabled_keys(tenant_id)
        return self._catalog.core_keys() | (stored & installed)

    @staticmethod
    def _lock(session: Session, tenant_id: UUID) -> None:
        """Serialise module changes per tenant."""
        if not TenantRepository(session).lock(tenant_id):
            raise NotFoundError("unknown tenant", code="TENANT_NOT_FOUND")
```

- [ ] **Step 5: Enforce on every module route**

Append to `backend/src/erp/modules/platform/dependencies.py` (merge import: `from erp.modules.platform.module_state import TenantModules`):

```python
class ModuleGuard:
    """Dependency that rejects requests to a disabled module."""

    def __init__(self, module_key: str) -> None:
        self._module_key = module_key

    def __call__(
        self,
        context: Annotated[RequestContext, Depends(TenantContextProvider.resolve)],
        request: Request,
    ) -> None:
        modules: TenantModules = request.app.state.tenant_modules
        modules.require(context.tenant_id, self._module_key)
```

Add `ModuleGuard` (from `dependencies`), and `TenantModules`, `ModuleDisabledError`, `ModuleChangeRejectedError` (from `module_state`), to `backend/src/erp/modules/platform/interface.py` and its `__all__`.

Replace `backend/src/erp/app.py` with:

```python
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from erp.core.controller import Controller
from erp.core.db import Database
from erp.core.errors import ErrorHandlers
from erp.core.modules import ModuleCatalog
from erp.core.security import TokenVerifier
from erp.module_catalog import InstalledModules
from erp.modules.platform.interface import (
    ModuleGuard,
    TenantDatabaseRouter,
    TenantModules,
)


class HealthController(Controller):
    """Liveness and readiness probes (OPS-04)."""

    def __init__(self, registry: Database | None) -> None:
        self._registry = registry
        super().__init__()

    def register_routes(self) -> None:
        for path, endpoint in (("/healthz", self.healthz), ("/readyz", self.readyz)):
            self.router.add_api_route(
                path, endpoint, methods=["GET"], include_in_schema=False
            )

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
        catalog: ModuleCatalog | None = None,
    ) -> None:
        self._registry = registry
        self._tenant_router = tenant_router
        self._verifier = verifier
        self._catalog = catalog or InstalledModules.catalog()

    def build(self) -> FastAPI:
        app = FastAPI(title="Karmevo ERP API", version="0.1.0")
        app.state.registry = self._registry
        app.state.tenant_router = self._tenant_router
        app.state.verifier = self._verifier
        app.state.module_catalog = self._catalog
        app.state.tenant_modules = (
            TenantModules(self._registry, self._catalog)
            if self._registry is not None
            else None
        )
        ErrorHandlers.install(app)
        app.include_router(HealthController(self._registry).router)
        self._mount_modules(app)
        return app

    def _mount_modules(self, app: FastAPI) -> None:
        # Routes stay mounted when a tenant disables a module, so
        # callers get 403 MODULE_DISABLED rather than a misleading 404.
        for manifest in self._catalog:
            guards = [] if manifest.core else [Depends(ModuleGuard(manifest.key))]
            for controller_class in manifest.controllers:
                app.include_router(controller_class().router, dependencies=guards)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass, including 7 in `test_modules.py`, 8 in `test_tenant_modules.py`, 1 in `test_module_gating.py`, and `test_registry_models_match_migrations` (now covering `"TenantModules"`).

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat(platform): module manifests, dependency graph, per-tenant enablement"
```

---

### Task 12: Operator CLI, runnable API, Keycloak dev realm, guardrails and docs

**Files:**
- Create: `backend/src/erp/cli.py`, `backend/src/erp/main.py`, `Makefile`, `deploy/.env.example`, `deploy/keycloak/realms/realm-staff.dev.json`
- Modify: `deploy/compose.dev.yml`, `backend/pyproject.toml`, `backend/tests/conftest.py`, `CLAUDE.md`, `docs/plan/traceability.md`
- Test: `backend/tests/core/test_main.py`, `backend/tests/platform/test_cli.py`

**Interfaces:**
- Produces:
  - `ProductionApp.build() -> FastAPI`, run with `uvicorn --factory erp.main:ProductionApp.build`.
  - `Cli(settings=None).run(argv=None) -> int` with subcommands:
    - `provision-tenant --account-number N --name NAME`
    - `upgrade-tenants`
    - `enable-module --tenant UUID --module KEY [--with-dependencies]`
    - `disable-module --tenant UUID --module KEY`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/conftest.py` (add `import json` at the top):

```python
@pytest.fixture
def cli_env(monkeypatch):
    """Point erp.cli at the test registry and tenant-DB prefix."""
    from erp.core.config import Settings

    monkeypatch.setenv("ERP_REGISTRY_DATABASE_URL", REGISTRY_APP_URL)
    monkeypatch.setenv("ERP_TENANT_DB_PREFIX", TENANT_DB_PREFIX)
    monkeypatch.setenv("ERP_TENANT_DB_SERVERS", json.dumps(TENANT_DB_SERVERS))
    Settings.load.cache_clear()
    yield
    Settings.load.cache_clear()
```

`backend/tests/platform/test_cli.py`:

```python
from uuid import UUID, uuid4

from erp.cli import Cli


def test_provision_tenant_prints_the_new_tenant_id(
    cli_env, provisioner, registry, capsys
):
    number = f"C{uuid4().hex[:12]}"
    argv = ["provision-tenant", "--account-number", number, "--name", "Kappa"]

    assert Cli().run(argv) == 0
    UUID(capsys.readouterr().out.strip())


def test_upgrade_tenants_reports_each_ready_tenant(cli_env, provisioned, capsys):
    exit_code = Cli().run(["upgrade-tenants"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert str(provisioned[0]) in output
    assert str(provisioned[1]) in output


def test_enabling_an_unknown_module_fails_cleanly(
    cli_env, provisioned, registry, capsys
):
    argv = ["enable-module", "--tenant", str(provisioned[0]), "--module", "nope"]

    assert Cli().run(argv) == 2
    assert "unknown module" in capsys.readouterr().err
```

`backend/tests/core/test_main.py`:

```python
from erp.main import ProductionApp


def test_build_wires_registry_router_verifier_and_modules():
    app = ProductionApp.build()

    assert app.state.registry is not None
    assert app.state.tenant_router is not None
    assert app.state.verifier is not None
    assert app.state.tenant_modules is not None
```

Run: `cd backend && uv run pytest tests/platform/test_cli.py tests/core/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'erp.cli'`

- [ ] **Step 2: Implement the CLI and the production factory**

`backend/src/erp/cli.py`:

```python
"""Operator commands; run by the operator, never exposed over HTTP.

    python -m erp.cli provision-tenant --account-number 100001 \\
        --name "Alpha Traders"
    python -m erp.cli upgrade-tenants
    python -m erp.cli enable-module --tenant <uuid> --module sales \\
        --with-dependencies
"""

import argparse
import sys
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from erp.core.config import Settings
from erp.core.db import Database, DbCredentials, TenantDbLocator
from erp.core.errors import DomainError
from erp.core.modules import ModuleCatalogError
from erp.module_catalog import InstalledModules
from erp.modules.platform.module_state import TenantModules
from erp.modules.platform.provisioning import TenantProvisioner


class Cli:
    """Entry point for `python -m erp.cli`."""

    ALEMBIC_INI: ClassVar[Path] = (
        Path(__file__).resolve().parents[2] / "alembic.ini"
    )
    MODULE_COMMANDS: ClassVar[tuple[str, ...]] = (
        "enable-module",
        "disable-module",
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings.load()

    def run(self, argv: list[str] | None = None) -> int:
        args = self._parser().parse_args(argv)
        registry = Database(self._settings.registry_database_url)
        try:
            if args.command in self.MODULE_COMMANDS:
                return self._change_module(args, registry)
            provisioner = self._provisioner(registry)
            if args.command == "provision-tenant":
                tenant_id = provisioner.provision(
                    account_number=args.account_number, tenant_name=args.name
                )
                print(tenant_id)
                return 0
            return self._upgrade(provisioner)
        finally:
            registry.dispose()

    @classmethod
    def _parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="erp")
        commands = parser.add_subparsers(dest="command", required=True)
        provision = commands.add_parser(
            "provision-tenant", help="create a tenant and its database"
        )
        provision.add_argument("--account-number", required=True)
        provision.add_argument("--name", required=True)
        commands.add_parser(
            "upgrade-tenants", help="migrate every ready tenant database"
        )
        for name in cls.MODULE_COMMANDS:
            command = commands.add_parser(name)
            command.add_argument("--tenant", required=True, type=UUID)
            command.add_argument("--module", required=True)
            if name == "enable-module":
                command.add_argument("--with-dependencies", action="store_true")
        return parser

    def _provisioner(self, registry: Database) -> TenantProvisioner:
        settings = self._settings
        return TenantProvisioner.create(
            registry,
            TenantDbLocator(
                settings.tenant_db_servers,
                database_prefix=settings.tenant_db_prefix,
            ),
            owner=DbCredentials(
                settings.tenant_db_owner_user, settings.tenant_db_owner_password
            ),
            runtime_roles=[
                settings.tenant_db_app_user,
                settings.tenant_db_relay_user,
            ],
            alembic_ini=self.ALEMBIC_INI,
        )

    @staticmethod
    def _upgrade(provisioner: TenantProvisioner) -> int:
        outcomes = provisioner.upgrade_all()
        for outcome in outcomes:
            result = outcome.revision or f"FAILED {outcome.error}"
            print(f"{outcome.tenant_id} {result}")
        return 1 if any(o.error for o in outcomes) else 0

    @staticmethod
    def _change_module(args: argparse.Namespace, registry: Database) -> int:
        modules = TenantModules(registry, InstalledModules.catalog())
        try:
            if args.command == "enable-module":
                enabled = modules.enable(
                    args.tenant,
                    args.module,
                    with_dependencies=args.with_dependencies,
                )
                print("enabled: " + (", ".join(enabled) or "nothing new"))
            else:
                modules.disable(args.tenant, args.module)
                print(f"disabled: {args.module}")
        except (DomainError, ModuleCatalogError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0


if __name__ == "__main__":
    sys.exit(Cli().run())
```

`backend/src/erp/main.py`:

```python
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
            DbCredentials(
                settings.tenant_db_app_user, settings.tenant_db_app_password
            ),
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
```

Run: `cd backend && uv run pytest tests/platform/test_cli.py tests/core/test_main.py -v`
Expected: `4 passed`.

- [ ] **Step 3: Keycloak dev realm and compose service**

`deploy/.env.example`:

```bash
# Copy to deploy/.env (git-ignored). Pin Keycloak to the current release listed at
# https://www.keycloak.org/downloads, e.g. KEYCLOAK_VERSION=<major.minor.patch>. Never "latest".
KEYCLOAK_VERSION=
```

Run: `cp deploy/.env.example deploy/.env` and set `KEYCLOAK_VERSION` to the current release number from https://www.keycloak.org/downloads.

Append under `services:` in `deploy/compose.dev.yml`:

```yaml
  keycloak:
    # Dev mode keeps Keycloak's storage in the container, apart from ERP databases (IAM-02).
    image: quay.io/keycloak/keycloak:${KEYCLOAK_VERSION:?set KEYCLOAK_VERSION in deploy/.env}
    command: ["start-dev", "--import-realm", "--http-port=8180"]
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: admin_dev
    ports: ["8180:8180"]
    volumes:
      - ./keycloak/realms:/opt/keycloak/data/import:ro
```

`deploy/keycloak/realms/realm-staff.dev.json` is DEVELOPMENT ONLY. It is the `staff` realm from ADR-0004; the per-tenant `<slug>-web` clients are created by provisioning in P1.1b, and `erp-web` is the dev stand-in:

```json
{
  "realm": "staff",
  "enabled": true,
  "registrationAllowed": false,
  "sslRequired": "external",
  "clients": [
    {
      "clientId": "erp-api",
      "enabled": true,
      "publicClient": false,
      "standardFlowEnabled": false,
      "implicitFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": false
    },
    {
      "clientId": "erp-web",
      "enabled": true,
      "publicClient": true,
      "standardFlowEnabled": true,
      "implicitFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "redirectUris": ["http://localhost:5173/*"],
      "webOrigins": ["http://localhost:5173"],
      "attributes": {
        "pkce.code.challenge.method": "S256",
        "post.logout.redirect.uris": "http://localhost:5173/*"
      },
      "protocolMappers": [
        {
          "name": "erp-api-audience",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "config": {
            "included.client.audience": "erp-api",
            "access.token.claim": "true",
            "id.token.claim": "false"
          }
        }
      ]
    }
  ],
  "users": [
    {
      "username": "dev.alice",
      "email": "alice@example.test",
      "emailVerified": true,
      "firstName": "Alice",
      "lastName": "Dev",
      "enabled": true,
      "credentials": [{ "type": "password", "value": "dev-alice-password", "temporary": false }]
    }
  ]
}
```

- [ ] **Step 4: Architecture guardrails**

Run: `cd backend && uv add --dev import-linter`

Append to `backend/pyproject.toml`:

```toml
[tool.importlinter]
root_package = "erp"

[[tool.importlinter.contracts]]
name = "core does not depend on shared or business modules"
type = "forbidden"
source_modules = ["erp.core"]
forbidden_modules = ["erp.modules", "erp.shared"]

[[tool.importlinter.contracts]]
name = "shared does not depend on business modules"
type = "forbidden"
source_modules = ["erp.shared"]
forbidden_modules = ["erp.modules"]
```

Run: `cd backend && uv run lint-imports`
Expected: `Contracts: 2 kept, 0 broken.` The "modules import each other only via `interface`" contract is added in P1.1b, once the first business module exists (ADR-0009).

Add a class-based guard test, `backend/tests/core/test_class_based.py`, which enforces ADR-0011 (no module-level functions in `erp/`):

```python
import ast
from pathlib import Path

import erp

SOURCE_ROOT = Path(erp.__file__).parent


def test_application_code_has_no_module_level_functions():
    offenders = []
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                offenders.append(f"{path.relative_to(SOURCE_ROOT)}:{node.name}")
    assert offenders == []
```

Run: `cd backend && uv run pytest tests/core/test_class_based.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Makefile**

`Makefile` (recipe lines are indented with a single tab):

```make
.PHONY: dev-up dev-down migrate provision-demo test lint api

dev-up:
	docker compose -f deploy/compose.dev.yml up -d --wait

dev-down:
	docker compose -f deploy/compose.dev.yml down

migrate:
	cd backend && uv run alembic -n registry upgrade head && uv run python -m erp.cli upgrade-tenants

provision-demo:
	cd backend && uv run python -m erp.cli provision-tenant --account-number 100001 --name "Demo Traders"

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run lint-imports

api:
	cd backend && uv run uvicorn --factory erp.main:ProductionApp.build --reload --port 8000
```

- [ ] **Step 6: Smoke run against real services**

```bash
make dev-up
curl -s http://localhost:8180/realms/staff/.well-known/openid-configuration | python3 -c "import json,sys; print(json.load(sys.stdin)['issuer'])"
```
Expected: `http://localhost:8180/realms/staff`. Keycloak takes roughly 20–40 s to boot and import the realm; retry if connection refused or 404.

```bash
make migrate
make provision-demo
docker compose -f deploy/compose.dev.yml exec postgres psql -U postgres -d erp_registry \
  -Atc 'select "accountNumber", "databaseName", "databaseStatus" from registry."Tenants"'
make api &   # or run it in a second terminal
curl -s http://localhost:8000/readyz
curl -s -i http://localhost:8000/api/v1/companies | head -n 1
```
Expected:
- `make provision-demo` prints a UUID.
- The `psql` query prints `100001|erp_t_<hex>|ready`. Note the quoted CamelCase identifiers.
- `/readyz` returns `{"status":"ready"}`.
- `/api/v1/companies` returns `HTTP/1.1 401 Unauthorized`.

If uvicorn rejects the dotted factory path `erp.main:ProductionApp.build`, add `app_factory = ProductionApp.build` to `main.py` (an attribute, not a function), point the Makefile at `erp.main:app_factory`, and record the change.

Stop the API afterwards.

- [ ] **Step 7: Full verification**

Run: `make lint && make test`
Expected: ruff clean (PEP 8 incl. `W505` and `N`), `Contracts: 2 kept, 0 broken.`, and all tests pass with 0 failures, including `test_class_based.py`.

- [ ] **Step 8: Update CLAUDE.md commands and traceability**

In `CLAUDE.md`, replace the whole `## Repository state` section with:

```markdown
## Commands

Prerequisites: Docker, `uv` (`brew install uv`). Copy `deploy/.env.example` to `deploy/.env` and pin `KEYCLOAK_VERSION`.

- `make dev-up` / `make dev-down`: Postgres 18 (port 55432) + Keycloak (port 8180, realm `staff`)
- `make migrate`: registry migrations (`alembic -n registry upgrade head`), then every ready tenant DB (`python -m erp.cli upgrade-tenants`)
- `make provision-demo`, or `cd backend && uv run python -m erp.cli provision-tenant --account-number N --name NAME`: create a tenant and its own database
- `cd backend && uv run python -m erp.cli enable-module --tenant <uuid> --module <key> [--with-dependencies]` (and `disable-module`)
- `make test`: full backend suite. It uses `erp_registry_test` plus throwaway `erp_test_t_*` tenant DBs and needs `make dev-up`.
- Single test: `cd backend && uv run pytest tests/platform/test_tenant_isolation.py::test_each_tenant_is_routed_to_its_own_database -v`
- `make lint`: ruff (PEP 8) check + format check + import-linter contracts
- `make api`: run the API at http://localhost:8000 (`/healthz`, `/readyz`, `/docs`)
- New tenant-DB migration: add a file under `backend/migrations/tenant/versions/`. It must be expand/contract compatible, because tenant DBs are upgraded one by one. Registry migrations go under `backend/migrations/registry/versions/`.
- In `psql`, quote CamelCase names: `select "tenantName" from registry."Tenants";`

The implementation plan is `docs/plan/00-implementation-plan.md`, ADRs are in `docs/adr/`, the traceability matrix is `docs/plan/traceability.md`, and detailed slice plans are in `docs/superpowers/plans/`.
```

In `docs/plan/traceability.md`, set these rows to Status `partial`, with Implementation and Test evidence as shown:

| ID | Implementation | Test evidence |
|---|---|---|
| ARC-01 | `erp/core/modules.py`, `erp/module_catalog.py`, `erp/modules/*/module.py` | `tests/core/test_modules.py` |
| ARC-03 | `erp/modules/integration/outbox.py` | `tests/outbox/test_outbox.py` |
| ARC-06 | `erp/core/errors.py`, `erp/shared/schemas.py`, `erp/modules/platform/controller.py` | `tests/core/test_errors.py`, `tests/shared/test_schemas.py`, `tests/platform/test_context_api.py` |
| TEN-01 | `erp/modules/platform/registry_models.py`, `models.py` | `tests/platform/test_registry.py` |
| TEN-02 | `erp/modules/platform/provisioning.py`, `tenant_db.py`, `migrations/tenant/*` | `tests/platform/test_provisioning.py`, `tests/platform/test_tenant_isolation.py`, `tests/core/test_db_roles.py` |
| TEN-03 | `erp/modules/platform/context.py`, `dependencies.py` | `tests/platform/test_context_api.py` |
| IAM-02 | `erp/core/security.py` | `tests/core/test_security.py` |
| IAM-04 | `erp/modules/platform/audit.py` | `tests/platform/test_audit.py` |
| PLT-05 | `erp/modules/platform/module_state.py`, `dependencies.ModuleGuard`, `app.py` | `tests/platform/test_tenant_modules.py`, `tests/platform/test_module_gating.py` |
| DB-01, DB-02 | `migrations/registry/*`, `migrations/tenant/*` | `tests/core/test_migrations.py`, `tests/platform/test_tenant_isolation.py` |
| JOB-04 | `erp/modules/integration/outbox.py` | `tests/outbox/test_outbox.py` |
| OPS-05 | `erp/cli.py` (`Cli` `upgrade-tenants`) | `tests/platform/test_provisioning.py`, `tests/platform/test_cli.py` |
| PLT-06 | `erp/shared/money.py` | `tests/shared/test_money.py`, `tests/core/test_errors.py` |
| OWN-02 | all of `erp/` (class-based layers) | `tests/core/test_class_based.py` |

- [ ] **Step 9: Commit**

```bash
git add Makefile deploy backend CLAUDE.md docs/plan/traceability.md
git commit -m "chore: operator CLI, production app, dev Keycloak, guardrails, docs"
```

---

## Slice exit checklist (report against this, honestly)

- [ ] `make lint && make test` green; paste the summary line into the slice report.
- [ ] Traceability rows updated (Task 12 Step 8). Every other ID remains `planned`.
- [ ] Known limitations recorded in the slice report:
  - **no permission engine yet** (P1.1b), so every active member can list companies
  - module enable/disable is operator-CLI only; the admin API/UI with audit and the licence-entitlement check come in P1.1b/P1.1c
  - the 50-app dependency graph is not encoded (pending `docs/plan/module-dependencies.md`)
  - `requires_any`, `integrates_with` and feature-level requirements are not implemented
  - the per-module settings store (`platform."ModuleSettings"`) arrives with the first business module
  - one shared `erp_app` credential can connect to every tenant DB; per-tenant login roles are P1.1e
  - no PgBouncer yet (P1.1e)
  - the relay is not yet wired to RabbitMQ and is unsharded (P1.1e)
  - the per-tenant restore runbook is P1.9
  - the Keycloak realm is dev-only, and per-tenant Keycloak clients plus tenant domains come in P1.1b
- [ ] Next plan: P1.1b, the permission engine (AUTH-01..12) + tenant domains + module-admin API. Write it against the merged code.
