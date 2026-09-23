# P1.1b-1 Permission Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tenant-owned authorization engine — permission groups, group policies, user overrides, ordered evaluation with deny precedence, typed conditions, record scope, approval limits, separation of duties and delegation limits — and enforce it on real endpoints, so all 13 AUTH-12 cases pass through the API.

**Architecture:** A new **core** module `erp/modules/authz/` owning the `authz` schema in every tenant database. Evaluation is a pure, ordered pipeline (`AuthorizationService.evaluate`) over policy records loaded by a revision-keyed cache; enforcement reaches other modules only through `RequirePermission`, a FastAPI dependency exported from `interface.py`. Admin writes go through a single service that bumps the authorization revision and writes a change-audit row in the same transaction.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 (sync), psycopg 3, Alembic (tenant tree), PostgreSQL 18 with RLS, pytest.

**Spec:** `ERP_Coding_Agent_Requirements.md` v2.3 §32 (AUTH-01..12), §4 (IAM-01..04), §16 (APR-01), §36 WFL-05 (condition tree, borrowed deliberately — see Ruling R4).

## Global Constraints

Every task's requirements implicitly include these. Values are copied verbatim from `CLAUDE.md` and the ADRs.

- **PEP 8**, enforced by ruff rules `E,W,N,F,I,B,UP`; code lines ≤ 99 characters; comments and docstrings ≤ 72 characters.
- **Class-based only (ADR-0011).** There are **no module-level functions** anywhere under `backend/src/erp/`. Stateless helpers are `@staticmethod` or `@classmethod` on a named class. `backend/tests/core/test_class_based.py` fails the build otherwise. Permitted exceptions: Alembic `upgrade()`/`downgrade()`, the `__main__` guard, pytest test functions and fixtures.
- **Exception class names must end in `Error`** (ruff `N818`). No exceptions to this — P1.1a lost a review round to it.
- **Database naming (ADR-0010):** tables plural PascalCase, columns camelCase, ids spelled out (`permissionGroupId`, never `id`), FK columns named after the column they reference, generic words qualified. **Every table and column name is double-quoted in raw SQL.** ORM attributes stay snake_case and map explicitly: `group_name: Mapped[str] = mapped_column("groupName", String(100))`.
- **API JSON (ADR-0010):** every request/response model inherits `erp.shared.schemas.ApiSchema`. Python fields snake_case, JSON camelCase. Multi-word query params declare `Query(alias="membershipId")`.
- **Errors:** RFC 9457 `application/problem+json` via `DomainError` subclasses with a stable `code`.
- **Money and decimals (PLT-06):** `Decimal` only, never `float`. JSON carries decimals as **strings**. Use `erp.shared.money.DecimalStr` for schema fields.
- **Tenancy (ADR-0002):** every `authz` table carries `"tenantId"` with an FK to `platform."DatabaseOwners"."tenantId"` via `Columns.tenant_id()`, plus `RlsSql.tenant_policy(...)` in its migration. No exceptions.
- **Migrations are expand/contract compatible**; tenant DBs upgrade one at a time.
- **Timestamps** are `timestamptz` UTC, named `…At`.
- **Module imports:** modules reach each other only through `interface.py`. `erp.core` and `erp.shared` never import `erp.modules`.
- **Commits:** conventional-commit subject, and a trailer naming the model that wrote the commit.

---

## Rulings made while writing this plan

These resolve gaps between the spec, the implementation plan and the existing code. Each is binding for this slice; a reviewer must not re-litigate them, but must flag any code that contradicts them.

**R1 — `authz` owns its own schema, not `platform`.** `docs/plan/00-implementation-plan.md` §5 sketched these tables as `platform.permission_definitions` etc. That predates the module system. CLAUDE.md's ARC-01 invariant ("each module owns its tables") wins: the tables live in schema `authz`, owned by the new `authz` module. Cost if wrong: a schema rename migration, cheap while no data exists.

**R2 — `authz` is a core module.** Every other module's enforcement depends on it, so it can never be disabled. `core=True`, `depends_on=("platform",)`. `ModuleCatalog._validate_dependencies` permits this (core may depend on core).

**R3 — `PermissionDefinitions` has no `tenantId`.** It is a static catalogue of the keys this build knows about, identical in every tenant database, seeded by migration. It therefore carries no RLS policy and `erp_app` gets `SELECT` only. Adding a permission key is a migration, which is the honest cost of a new key.

**R4 — The condition tree is specified by WFL-05, not by AUTH-03.** AUTH-03 says only "business conditions". WFL-05 (§36) is the spec's sole definition of a restricted typed expression tree, and CLAUDE.md already applies it project-wide. This slice implements it in `authz/conditions.py`; P1.1d's workflow engine reuses that class rather than writing a second one.

**R5 — `recordScope: "team"` is rejected at write time in this slice.** AUTH-03 requires own/team/all, but no team or reporting-line model exists until P1.7 (people). Accepting `team` now would mean evaluating it as something else silently — a security hole. Writes carrying `team` return 422 `RECORD_SCOPE_UNSUPPORTED`. Traceability records AUTH-03 as **partial** with this named gap. Cost if wrong: a follow-up slice enables the value; nothing built on a wrong meaning.

**R6 — The "licensed action" tier is module enablement in this slice.** Real licensing is P1.1c. `PermissionDefinition.requiresFeatureKey` holds a **module key**. `FeatureGate` denies `FEATURE_NOT_LICENSED` when the key is not in this build's `ModuleCatalog` at all, and `MODULE_DISABLED` when it is installed but not enabled for the tenant. P1.1c replaces the gate's implementation behind the same interface. This makes AUTH-12 case 7 genuinely testable today.

**R7 — A scoped policy does not match an unscoped request.** If a policy sets `companyId` and the request supplies none, the policy does **not** match. The request must prove it is inside the scope; absence is not proof. Same for `branchId` and `warehouseId`.

**R8 — Grants require delegation; denies do not.** AUTH-08 limits administrators to "only delegated permissions/scopes". Writing an **allow** requires the actor to hold that permission at an equal-or-wider scope. Writing a **deny** is always permitted to a permission administrator, because restricting access cannot escalate privilege.

**R9 — Permission changes are audited in `authz."PermissionChangeAudit"`, not only in `platform."AuditEvents"`.** AUTH-11 names the table explicitly, and it needs before/after policy snapshots that the generic audit row cannot carry. Both are written: `AuditEvents` for the IAM-04 trail, `PermissionChangeAudit` for the policy-version history AUTH-11 requires.

**R10 — `warehouseId` has no foreign key yet.** AUTH-03 requires warehouse scope, but no warehouse table exists until P1.3. The column exists and is enforced by evaluation; its composite FK is added by the inventory slice. Noted in the migration as a comment so it is not mistaken for an oversight.

**R11 — Hidden fields are proven on audit-event details.** AUTH-12 case 9 needs a real sensitive-field surface. Inventing a cost or payroll model for it would be scope creep. `GET /api/v1/audit-events` redacts `auditDetails` unless the caller holds `platform.audit.details.view`. That is a genuine sensitive field on data that already exists.

---

## File structure

```
backend/src/erp/modules/authz/
  __init__.py
  module.py         MODULE manifest (core, depends_on platform)
  config.py         AuthzConfig: cache size, approval action names
  permissions.py    PermissionKeys: the key catalogue this build declares
  models.py         7 SQLAlchemy models
  schemas.py        ApiSchema request/response models
  conditions.py     ConditionTree, ConditionFields  (pure; R4)
  policy.py         AccessRequest, Decision, PolicyRecord, PolicyMatcher
  cache.py          RevisionCache
  resolver.py       PolicyResolver: membership -> policy records
  gates.py          FeatureGate, SeparationOfDuties   (non-bypassable tier)
  delegation.py     DelegationGuard
  templates.py      GroupTemplates: the seven AUTH-01 templates
  repository.py     5 repositories
  service.py        AuthorizationService (read) + PermissionAdminService (write)
  controller.py     4 controllers
  errors.py         authz-specific DomainError subclasses
  interface.py      RequirePermission, AuthorizationFacade  (the only public surface)
  utils.py          small helper classes

backend/migrations/tenant/versions/
  t0005_authz_permission_definitions.py
  t0006_authz_groups_and_policies.py
  t0007_authz_overrides_revisions_audit.py

backend/tests/authz/
  test_conditions.py  test_policy_matching.py  test_resolver.py
  test_evaluation.py  test_delegation.py       test_admin_api.py
  test_inspector.py   test_auth12_conformance.py
```

Files that change: `erp/module_catalog.py` (register the manifest), `erp/modules/platform/controller.py` (enforce on companies, add audit-events endpoint), `erp/modules/platform/schemas.py`, `erp/modules/platform/service.py`, `erp/cli.py` (`grant-admin`), `erp/modules/platform/provisioning.py` (seed templates), `backend/pyproject.toml` (import-linter contract), `docs/plan/traceability.md`.

---

## Interfaces at a glance

Every task below consumes these. They are defined in Tasks 4–10 and must not drift.

```python
# policy.py
@dataclass(frozen=True)
class AccessRequest:
    permission_key: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    warehouse_id: UUID | None = None
    record_owner_membership_id: UUID | None = None
    amount: Decimal | None = None
    currency: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PolicyRecord:
    policy_id: UUID
    origin: str           # "group:<uuid>" or "override"
    origin_name: str      # group name, or "user override"
    permission_key: str
    effect: str           # "allow" | "deny"
    company_id: UUID | None
    branch_id: UUID | None
    warehouse_id: UUID | None
    record_scope: str | None
    conditions: Mapping[str, Any]
    limit_amount: Decimal | None
    limit_currency: str | None
    valid_from: datetime | None
    valid_to: datetime | None

@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str
    reason: str
    origin: str | None = None
    origin_name: str | None = None

# service.py
class AuthorizationService:
    def evaluate(self, request: AccessRequest) -> Decision: ...
    def require(self, request: AccessRequest) -> None: ...   # raises on deny
    def effective_permissions(self, membership_id: UUID) -> list[EffectivePermissionOut]: ...

# interface.py
class RequirePermission:
    def __init__(self, permission_key: str) -> None: ...
    def __call__(self, ...) -> AuthorizationService: ...     # FastAPI dependency
```

---

### Task 1: The `authz` module skeleton and permission catalogue

**Files:**
- Create: `backend/src/erp/modules/authz/__init__.py`, `permissions.py`, `config.py`, `errors.py`, `module.py`, `models.py`
- Create: `backend/migrations/tenant/versions/t0005_authz_permission_definitions.py`
- Modify: `backend/src/erp/module_catalog.py`
- Test: `backend/tests/authz/__init__.py`, `backend/tests/authz/test_catalogue.py`

**Interfaces:**
- Consumes: `Columns`, `TenantBase` from `erp.core.models`; `ModuleManifest` from `erp.core.modules`; `RlsSql` from `erp.core.rls`.
- Produces: `PermissionKeys.ALL`, `PermissionDefinition` model, module key `"authz"`, tenant migration head `t0005`.

- [ ] **Step 1: Write the failing test**

`backend/tests/authz/test_catalogue.py`:

```python
"""The permission catalogue is declared in code and seeded by migration."""

from sqlalchemy import text

from erp.modules.authz.permissions import PermissionKeys
from erp.module_catalog import InstalledModules


def test_authz_is_a_core_module_depending_on_platform():
    catalog = InstalledModules.catalog()
    manifest = catalog.get("authz")
    assert manifest.core is True
    assert manifest.depends_on == ("platform",)


def test_every_declared_key_is_resource_dot_action_shaped():
    for key in PermissionKeys.ALL:
        resource, _, action = key.rpartition(".")
        assert resource and action, key


def test_the_keys_named_by_auth_02_are_declared():
    required = {
        "sales.order.create",
        "sales.discount.approve",
        "inventory.count.submit",
        "inventory.adjustment.approve",
        "shipment.loading.approve",
        "shipment.dispatch.release",
        "finance.cost.view",
        "people.payroll.view",
        "platform.permissions.manage",
    }
    assert required <= {d.permission_key for d in PermissionKeys.ALL}


def test_definitions_are_seeded_into_every_tenant_database(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.a) as session:
        rows = session.execute(
            text('select "permissionKey" from authz."PermissionDefinitions"')
        ).scalars()
        assert set(rows) == {d.permission_key for d in PermissionKeys.ALL}
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd backend && uv run pytest tests/authz/test_catalogue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erp.modules.authz'`

- [ ] **Step 3: Declare the catalogue**

`backend/src/erp/modules/authz/permissions.py`:

```python
"""The permission keys this build declares (AUTH-02).

Adding a key means adding a migration that seeds it, so the
catalogue in the database always matches the code.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class PermissionDefinitionSpec:
    """One declared permission key."""

    permission_key: str
    resource_name: str
    action_name: str
    sensitivity_level: str = "normal"
    requires_feature_key: str | None = None
    supports_record_scope: bool = False
    supports_approval_limit: bool = False


class PermissionKeys:
    """Every permission key known to this build (AUTH-02)."""

    SENSITIVITIES: ClassVar[frozenset[str]] = frozenset({"normal", "sensitive"})

    PLATFORM_PERMISSIONS_MANAGE = "platform.permissions.manage"
    PLATFORM_COMPANY_VIEW = "platform.company.view"
    PLATFORM_AUDIT_VIEW = "platform.audit.view"
    PLATFORM_AUDIT_DETAILS_VIEW = "platform.audit.details.view"

    ALL: ClassVar[tuple[PermissionDefinitionSpec, ...]] = (
        PermissionDefinitionSpec(
            PLATFORM_PERMISSIONS_MANAGE, "platform.permissions", "manage", "sensitive"
        ),
        PermissionDefinitionSpec(PLATFORM_COMPANY_VIEW, "platform.company", "view"),
        PermissionDefinitionSpec(PLATFORM_AUDIT_VIEW, "platform.audit", "view"),
        PermissionDefinitionSpec(
            PLATFORM_AUDIT_DETAILS_VIEW, "platform.audit.details", "view", "sensitive"
        ),
        # Declared now so policies can reference them; the feature gate
        # denies each one until its module is installed and enabled (R6).
        PermissionDefinitionSpec(
            "sales.order.create", "sales.order", "create",
            requires_feature_key="sales", supports_record_scope=True,
        ),
        PermissionDefinitionSpec(
            "sales.discount.approve", "sales.discount", "approve",
            requires_feature_key="sales", supports_approval_limit=True,
        ),
        PermissionDefinitionSpec(
            "inventory.count.submit", "inventory.count", "submit",
            requires_feature_key="inventory",
        ),
        PermissionDefinitionSpec(
            "inventory.adjustment.approve", "inventory.adjustment", "approve",
            requires_feature_key="inventory", supports_approval_limit=True,
        ),
        PermissionDefinitionSpec(
            "shipment.loading.approve", "shipment.loading", "approve",
            requires_feature_key="shipment",
        ),
        PermissionDefinitionSpec(
            "shipment.dispatch.release", "shipment.dispatch", "release",
            requires_feature_key="shipment",
        ),
        PermissionDefinitionSpec(
            "finance.cost.view", "finance.cost", "view", "sensitive",
            requires_feature_key="finance",
        ),
        PermissionDefinitionSpec(
            "people.payroll.view", "people.payroll", "view", "sensitive",
            requires_feature_key="people",
        ),
    )

    @classmethod
    def get(cls, permission_key: str) -> PermissionDefinitionSpec | None:
        return next((d for d in cls.ALL if d.permission_key == permission_key), None)

    @classmethod
    def keys(cls) -> frozenset[str]:
        return frozenset(d.permission_key for d in cls.ALL)
```

- [ ] **Step 4: Add the config, errors and model**

`backend/src/erp/modules/authz/config.py`:

```python
"""Module settings (ADR-0009)."""

from typing import ClassVar


class AuthzConfig:
    """Tunables for the authorization engine."""

    # Distinct (tenant, membership, revision) policy sets held in memory.
    POLICY_CACHE_SIZE: ClassVar[int] = 512

    # Actions that a record's own author may never perform (AUTH-06).
    SELF_APPROVAL_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {"approve", "release", "authorize"}
    )
```

`backend/src/erp/modules/authz/errors.py`:

```python
"""Authorization errors (RFC 9457 codes)."""

from erp.core.errors import ConflictError, DomainError, ForbiddenError


class PermissionDeniedError(ForbiddenError):
    code = "PERMISSION_DENIED"
    title = "Permission denied"


class SelfApprovalDeniedError(ForbiddenError):
    code = "SELF_APPROVAL_DENIED"
    title = "Self-approval is not permitted"


class SelfEscalationDeniedError(ForbiddenError):
    code = "SELF_ESCALATION_DENIED"
    title = "Self-escalation is not permitted"


class DelegationDeniedError(ForbiddenError):
    code = "DELEGATION_DENIED"
    title = "Grant exceeds delegated authority"


class FeatureNotLicensedError(ForbiddenError):
    code = "FEATURE_NOT_LICENSED"
    title = "Feature is not licensed"


class LastAdminProtectedError(ConflictError):
    code = "LAST_ADMIN_PROTECTED"
    title = "The last permission administrator cannot be removed"


class ProtectedTemplateError(ConflictError):
    code = "PROTECTED_TEMPLATE"
    title = "Protected template cannot be changed"


class RecordScopeUnsupportedError(DomainError):
    status = 422
    code = "RECORD_SCOPE_UNSUPPORTED"
    title = "Record scope is not supported yet"


class InvalidConditionError(DomainError):
    status = 422
    code = "INVALID_CONDITION"
    title = "Condition tree is not valid"
```

`backend/src/erp/modules/authz/models.py` (this task adds only the first model; Tasks 2 and 3 append):

```python
"""Authorization tables in each tenant database (AUTH-11)."""

from typing import Any, ClassVar

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from erp.core.models import TenantBase

SCHEMA: dict[str, Any] = {"schema": "authz"}


class PermissionDefinition(TenantBase):
    """The catalogue of permission keys (AUTH-02).

    Identical in every tenant database and seeded by migration, so
    it carries no tenantId and no row-level policy (R3).
    """

    __tablename__ = "PermissionDefinitions"
    __table_args__: ClassVar[Any] = (
        CheckConstraint(
            "\"sensitivityLevel\" in ('normal', 'sensitive')",
            name="sensitivityLevel",
        ),
        SCHEMA,
    )

    permission_key: Mapped[str] = mapped_column("permissionKey", String(100), primary_key=True)
    resource_name: Mapped[str] = mapped_column("resourceName", String(64))
    action_name: Mapped[str] = mapped_column("actionName", String(32))
    sensitivity_level: Mapped[str] = mapped_column(
        "sensitivityLevel", String(16), server_default="normal"
    )
    requires_feature_key: Mapped[str | None] = mapped_column(
        "requiresFeatureKey", String(64), nullable=True
    )
    supports_record_scope: Mapped[bool] = mapped_column(
        "supportsRecordScope", Boolean, server_default="false"
    )
    supports_approval_limit: Mapped[bool] = mapped_column(
        "supportsApprovalLimit", Boolean, server_default="false"
    )
```

- [ ] **Step 5: Write the migration**

`backend/migrations/tenant/versions/t0005_authz_permission_definitions.py`:

```python
"""tenant DB: authz schema and the permission-key catalogue

Revision ID: t0005
Revises: t0004
"""

from alembic import op
from sqlalchemy import column, table
from sqlalchemy import text as sql

from erp.modules.authz.permissions import PermissionKeys

revision = "t0005"
down_revision = "t0004"
branch_labels = None
depends_on = None

DEFINITIONS = table(
    "PermissionDefinitions",
    column("permissionKey"),
    column("resourceName"),
    column("actionName"),
    column("sensitivityLevel"),
    column("requiresFeatureKey"),
    column("supportsRecordScope"),
    column("supportsApprovalLimit"),
    schema="authz",
)


def upgrade() -> None:
    op.execute(sql("create schema if not exists authz"))
    op.execute(sql("grant usage on schema authz to erp_app"))
    op.create_table(
        "PermissionDefinitions",
        sa.Column("permissionKey", sa.String(100), primary_key=True),
        sa.Column("resourceName", sa.String(64), nullable=False),
        sa.Column("actionName", sa.String(32), nullable=False),
        sa.Column(
            "sensitivityLevel", sa.String(16), nullable=False, server_default="normal"
        ),
        sa.Column("requiresFeatureKey", sa.String(64), nullable=True),
        sa.Column(
            "supportsRecordScope", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "supportsApprovalLimit", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.CheckConstraint(
            "\"sensitivityLevel\" in ('normal', 'sensitive')",
            name="ck_PermissionDefinitions_sensitivityLevel",
        ),
        schema="authz",
    )
    # Catalogue rows are build-wide facts, so erp_app may only read
    # them; migrations own every write (R3).
    op.execute(sql('grant select on authz."PermissionDefinitions" to erp_app'))
    op.bulk_insert(
        DEFINITIONS,
        [
            {
                "permissionKey": d.permission_key,
                "resourceName": d.resource_name,
                "actionName": d.action_name,
                "sensitivityLevel": d.sensitivity_level,
                "requiresFeatureKey": d.requires_feature_key,
                "supportsRecordScope": d.supports_record_scope,
                "supportsApprovalLimit": d.supports_approval_limit,
            }
            for d in PermissionKeys.ALL
        ],
    )


def downgrade() -> None:
    op.drop_table("PermissionDefinitions", schema="authz")
    op.execute(sql("drop schema if exists authz"))
```

Add `import sqlalchemy as sa` to the migration's imports. Compare against `t0003_platform_audit_events.py` for the house style; the constraint name above is spelled out because `erp.core.models.NAMING_CONVENTION` does not apply to `op.create_table` outside the model metadata.

- [ ] **Step 6: Register the module**

`backend/src/erp/modules/authz/module.py`:

```python
from erp.core.modules import ModuleManifest

MODULE = ModuleManifest(
    key="authz",
    name="Authorization",
    depends_on=("platform",),
    core=True,
    controllers=(),
)
```

Then in `backend/src/erp/module_catalog.py`, import `MODULE as AUTHZ` from `erp.modules.authz.module` and add it to `MANIFESTS` between `PLATFORM` and `INTEGRATION`.

- [ ] **Step 7: Run the tests**

Run: `cd backend && uv run alembic -n registry upgrade head && uv run pytest tests/authz/test_catalogue.py tests/core/test_migrations.py tests/core/test_class_based.py -v`
Expected: PASS. If `test_migrations.py` asserts a specific head, update it to `t0005`.

- [ ] **Step 8: Lint and commit**

```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run lint-imports
git add backend/src/erp/modules/authz backend/tests/authz backend/migrations/tenant/versions/t0005_authz_permission_definitions.py backend/src/erp/module_catalog.py
git commit -m "feat(authz): add core authz module and the permission-key catalogue"
```

---

### Task 2: Permission groups and group policies (tables + RLS)

**Files:**
- Modify: `backend/src/erp/modules/authz/models.py`
- Create: `backend/migrations/tenant/versions/t0006_authz_groups_and_policies.py`
- Test: `backend/tests/authz/test_tables.py`

**Interfaces:**
- Consumes: `Columns.tenant_id()`, `Columns.uuid_pk()`, `Columns.created_at()`, `RlsSql.tenant_policy`.
- Produces: `PermissionGroup`, `GroupPolicy` models; tenant migration head `t0006`.

- [ ] **Step 1: Write the failing test**

`backend/tests/authz/test_tables.py`:

```python
"""Authorization tables are tenant-scoped and RLS-protected."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from erp.modules.authz.models import GroupPolicy, PermissionGroup


def test_a_group_belongs_to_the_database_owner(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.a) as session:
        session.add(PermissionGroup(tenant_id=two_tenants.a, group_name="Sales"))
    with database.tenant_session(two_tenants.a) as session:
        names = session.execute(
            text('select "groupName" from authz."PermissionGroups"')
        ).scalars()
        assert list(names) == ["Sales"]


def test_a_group_for_another_tenant_is_rejected(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises((IntegrityError, DBAPIError)):
        with database.tenant_session(two_tenants.a) as session:
            session.add(PermissionGroup(tenant_id=two_tenants.b, group_name="Smuggled"))


def test_rows_are_invisible_without_tenant_context(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.a) as session:
        session.add(PermissionGroup(tenant_id=two_tenants.a, group_name="Sales"))
    with database.platform_session() as session:
        rows = session.execute(text('select count(*) from authz."PermissionGroups"'))
        assert rows.scalar_one() == 0


def test_policy_effect_is_constrained(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.a) as session:
        group = PermissionGroup(tenant_id=two_tenants.a, group_name="Sales")
        session.add(group)
        session.flush()
        group_id = group.permission_group_id
    with pytest.raises((IntegrityError, DBAPIError)):
        with database.tenant_session(two_tenants.a) as session:
            session.add(
                GroupPolicy(
                    tenant_id=two_tenants.a,
                    permission_group_id=group_id,
                    permission_key="platform.company.view",
                    policy_effect="maybe",
                )
            )


def test_a_limit_needs_both_amount_and_currency(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.a) as session:
        group = PermissionGroup(tenant_id=two_tenants.a, group_name="Sales")
        session.add(group)
        session.flush()
        group_id = group.permission_group_id
    with pytest.raises((IntegrityError, DBAPIError)):
        with database.tenant_session(two_tenants.a) as session:
            session.add(
                GroupPolicy(
                    tenant_id=two_tenants.a,
                    permission_group_id=group_id,
                    permission_key="sales.discount.approve",
                    policy_effect="allow",
                    limit_amount=Decimal("100.00"),
                    limit_currency=None,
                )
            )
```

(Add `from decimal import Decimal` at the top.)

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/authz/test_tables.py -v`
Expected: FAIL — `ImportError: cannot import name 'PermissionGroup'`

- [ ] **Step 3: Add the models**

Append to `backend/src/erp/modules/authz/models.py`:

```python
class PermissionGroup(TenantBase):
    """A tenant-owned, editable permission group (AUTH-01)."""

    __tablename__ = "PermissionGroups"
    __table_args__: ClassVar[Any] = (
        UniqueConstraint("tenantId", "permissionGroupId"),
        UniqueConstraint("tenantId", "groupName"),
        SCHEMA,
    )

    permission_group_id: Mapped[UUID] = Columns.uuid_pk("permissionGroupId")
    tenant_id: Mapped[UUID] = Columns.tenant_id()
    group_name: Mapped[str] = mapped_column("groupName", String(100))
    group_description: Mapped[str | None] = mapped_column(
        "groupDescription", String(500), nullable=True
    )
    is_template: Mapped[bool] = mapped_column("isTemplate", Boolean, server_default="false")
    is_protected: Mapped[bool] = mapped_column("isProtected", Boolean, server_default="false")
    created_at: Mapped[datetime] = Columns.created_at()


class GroupPolicy(TenantBase):
    """One allow or deny rule carried by a group (AUTH-03)."""

    __tablename__ = "GroupPolicies"
    __table_args__: ClassVar[Any] = (
        UniqueConstraint("tenantId", "groupPolicyId"),
        CheckConstraint("\"policyEffect\" in ('allow', 'deny')", name="policyEffect"),
        CheckConstraint(
            "\"recordScope\" is null or \"recordScope\" in ('own', 'team', 'all')",
            name="recordScope",
        ),
        CheckConstraint(
            '("limitAmount" is null) = ("limitCurrency" is null)',
            name="limitPair",
        ),
        ForeignKeyConstraint(
            ["tenantId", "permissionGroupId"],
            ["authz.PermissionGroups.tenantId", "authz.PermissionGroups.permissionGroupId"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenantId", "companyId"],
            ["platform.Companies.tenantId", "platform.Companies.companyId"],
        ),
        ForeignKeyConstraint(
            ["tenantId", "branchId"],
            ["platform.Branches.tenantId", "platform.Branches.branchId"],
        ),
        SCHEMA,
    )

    group_policy_id: Mapped[UUID] = Columns.uuid_pk("groupPolicyId")
    tenant_id: Mapped[UUID] = Columns.tenant_id()
    permission_group_id: Mapped[UUID] = mapped_column("permissionGroupId")
    permission_key: Mapped[str] = mapped_column(
        "permissionKey", ForeignKey("authz.PermissionDefinitions.permissionKey")
    )
    policy_effect: Mapped[str] = mapped_column("policyEffect", String(8))
    company_id: Mapped[UUID | None] = mapped_column("companyId", nullable=True)
    branch_id: Mapped[UUID | None] = mapped_column("branchId", nullable=True)
    # No FK until the inventory slice creates warehouses (R10).
    warehouse_id: Mapped[UUID | None] = mapped_column("warehouseId", nullable=True)
    record_scope: Mapped[str | None] = mapped_column("recordScope", String(8), nullable=True)
    policy_conditions: Mapped[dict[str, Any]] = mapped_column(
        "policyConditions", JSONB, server_default=sql("'{}'::jsonb")
    )
    limit_amount: Mapped[Decimal | None] = mapped_column(
        "limitAmount", Numeric(18, 4), nullable=True
    )
    limit_currency: Mapped[str | None] = mapped_column(
        "limitCurrency", String(3), nullable=True
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        "validFrom", DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        "validTo", DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = Columns.created_at()
```

Imports to add at the top of `models.py`: `from datetime import datetime`, `from decimal import Decimal`, `from uuid import UUID`, and from `sqlalchemy`: `DateTime, ForeignKey, ForeignKeyConstraint, Numeric, UniqueConstraint`, `text as sql`; `from sqlalchemy.dialects.postgresql import JSONB`; `from erp.core.models import Columns, TenantBase`.

> **Composite-FK note (important):** PostgreSQL foreign keys default to `MATCH SIMPLE`, so a row with a NULL `companyId` is not checked against `platform."Companies"` even though `tenantId` is non-null. That is exactly the wanted behaviour: NULL means "any company". Do **not** add `MATCH FULL`.

- [ ] **Step 4: Write the migration**

`backend/migrations/tenant/versions/t0006_authz_groups_and_policies.py`, `revision = "t0006"`, `down_revision = "t0005"`. Create both tables with the columns and constraints above, then grant and protect them:

```python
def upgrade() -> None:
    op.create_table("PermissionGroups", ..., schema="authz")
    op.create_table("GroupPolicies", ..., schema="authz")
    for table_name in ("PermissionGroups", "GroupPolicies"):
        op.execute(
            sql(f'grant select, insert, update, delete on authz."{table_name}" to erp_app')
        )
        for statement in RlsSql.tenant_policy("authz", table_name):
            op.execute(sql(statement))
    op.create_index(
        "ix_GroupPolicies_permissionGroupId",
        "GroupPolicies",
        ["tenantId", "permissionGroupId"],
        schema="authz",
    )
```

DELETE is granted here because group and policy rows are editor-owned configuration, not financial or stock records — the ledger rule in CLAUDE.md does not apply, and AUTH-07 requires a group editor that can remove a policy. Every removal still writes a `PermissionChangeAudit` row (Task 11).

- [ ] **Step 5: Run the tests**

Run: `cd backend && uv run pytest tests/authz -v`
Expected: PASS (the migration runs through the session-scoped `provisioner` fixture, which drops and re-creates `erp_test_t_*` databases).

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run lint-imports
git add -A && git commit -m "feat(authz): add permission groups and group policies with RLS"
```

---

### Task 3: Overrides, revisions and change audit (tables + RLS)

**Files:**
- Modify: `backend/src/erp/modules/authz/models.py`
- Create: `backend/migrations/tenant/versions/t0007_authz_overrides_revisions_audit.py`
- Test: `backend/tests/authz/test_tables.py` (extend)

**Interfaces:**
- Produces: `UserGroupMembership`, `UserPermissionOverride`, `AuthorizationRevision`, `PermissionChangeAudit`; tenant migration head `t0007`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/authz/test_tables.py`:

```python
def test_a_membership_joins_a_group(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    membership_id = uuid4()
    with database.tenant_session(two_tenants.a) as session:
        group = PermissionGroup(tenant_id=two_tenants.a, group_name="Sales")
        session.add(group)
        session.flush()
        session.add(
            UserGroupMembership(
                tenant_id=two_tenants.a,
                membership_id=membership_id,
                permission_group_id=group.permission_group_id,
            )
        )
    with database.tenant_session(two_tenants.a) as session:
        count = session.execute(
            text('select count(*) from authz."UserGroupMemberships"')
        ).scalar_one()
        assert count == 1


def test_an_override_requires_a_reason(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with pytest.raises((IntegrityError, DBAPIError)):
        with database.tenant_session(two_tenants.a) as session:
            session.add(
                UserPermissionOverride(
                    tenant_id=two_tenants.a,
                    membership_id=uuid4(),
                    permission_key="platform.company.view",
                    policy_effect="allow",
                    override_reason=None,
                )
            )


def test_every_tenant_database_starts_at_revision_one(two_tenants, router):
    database = router.for_tenant(two_tenants.a)
    with database.tenant_session(two_tenants.a) as session:
        revision = session.execute(
            text('select "revisionNumber" from authz."AuthorizationRevisions"')
        ).scalar_one()
        assert revision == 1
```

(Add `from uuid import uuid4` and the three new model imports.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/authz/test_tables.py -v`
Expected: FAIL — `ImportError: cannot import name 'UserGroupMembership'`

- [ ] **Step 3: Add the models**

Append to `models.py`:

```python
class UserGroupMembership(TenantBase):
    """A tenant membership's place in a group (AUTH-01).

    membershipId lives in the registry database, so it carries no
    foreign key here, exactly like AuditEvents.actorIdentityId.
    """

    __tablename__ = "UserGroupMemberships"
    __table_args__: ClassVar[Any] = (
        PrimaryKeyConstraint("tenantId", "membershipId", "permissionGroupId"),
        ForeignKeyConstraint(
            ["tenantId", "permissionGroupId"],
            ["authz.PermissionGroups.tenantId", "authz.PermissionGroups.permissionGroupId"],
            ondelete="CASCADE",
        ),
        SCHEMA,
    )

    tenant_id: Mapped[UUID] = Columns.tenant_id()
    membership_id: Mapped[UUID] = mapped_column("membershipId")
    permission_group_id: Mapped[UUID] = mapped_column("permissionGroupId")
    valid_from: Mapped[datetime | None] = mapped_column(
        "validFrom", DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        "validTo", DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = Columns.created_at()


class UserPermissionOverride(TenantBase):
    """A per-user grant or denial that never edits the group (AUTH-03)."""

    __tablename__ = "UserPermissionOverrides"
    __table_args__: ClassVar[Any] = (
        UniqueConstraint("tenantId", "userPermissionOverrideId"),
        CheckConstraint("\"policyEffect\" in ('allow', 'deny')", name="policyEffect"),
        CheckConstraint(
            "\"recordScope\" is null or \"recordScope\" in ('own', 'team', 'all')",
            name="recordScope",
        ),
        CheckConstraint(
            '("limitAmount" is null) = ("limitCurrency" is null)', name="limitPair"
        ),
        ForeignKeyConstraint(
            ["tenantId", "companyId"],
            ["platform.Companies.tenantId", "platform.Companies.companyId"],
        ),
        ForeignKeyConstraint(
            ["tenantId", "branchId"],
            ["platform.Branches.tenantId", "platform.Branches.branchId"],
        ),
        SCHEMA,
    )

    user_permission_override_id: Mapped[UUID] = Columns.uuid_pk("userPermissionOverrideId")
    tenant_id: Mapped[UUID] = Columns.tenant_id()
    membership_id: Mapped[UUID] = mapped_column("membershipId")
    permission_key: Mapped[str] = mapped_column(
        "permissionKey", ForeignKey("authz.PermissionDefinitions.permissionKey")
    )
    policy_effect: Mapped[str] = mapped_column("policyEffect", String(8))
    company_id: Mapped[UUID | None] = mapped_column("companyId", nullable=True)
    branch_id: Mapped[UUID | None] = mapped_column("branchId", nullable=True)
    warehouse_id: Mapped[UUID | None] = mapped_column("warehouseId", nullable=True)
    record_scope: Mapped[str | None] = mapped_column("recordScope", String(8), nullable=True)
    policy_conditions: Mapped[dict[str, Any]] = mapped_column(
        "policyConditions", JSONB, server_default=sql("'{}'::jsonb")
    )
    limit_amount: Mapped[Decimal | None] = mapped_column(
        "limitAmount", Numeric(18, 4), nullable=True
    )
    limit_currency: Mapped[str | None] = mapped_column("limitCurrency", String(3), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(
        "validFrom", DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        "validTo", DateTime(timezone=True), nullable=True
    )
    override_reason: Mapped[str] = mapped_column("overrideReason", Text)
    granted_by_identity_id: Mapped[UUID | None] = mapped_column(
        "grantedByIdentityId", nullable=True
    )
    created_at: Mapped[datetime] = Columns.created_at()


class AuthorizationRevision(TenantBase):
    """One row per tenant database; bumped on every change (AUTH-10)."""

    __tablename__ = "AuthorizationRevisions"
    __table_args__: ClassVar[Any] = (SCHEMA,)

    tenant_id: Mapped[UUID] = mapped_column(
        "tenantId", ForeignKey(Columns.DATABASE_OWNER_FK), primary_key=True
    )
    revision_number: Mapped[int] = mapped_column(
        "revisionNumber", BigInteger, server_default="1"
    )
    changed_at: Mapped[datetime] = Columns.timestamp("changedAt")
    changed_by_identity_id: Mapped[UUID | None] = mapped_column(
        "changedByIdentityId", nullable=True
    )


class PermissionChangeAudit(TenantBase):
    """Before/after history of every policy change (AUTH-11, R9)."""

    __tablename__ = "PermissionChangeAudit"
    __table_args__: ClassVar[Any] = (
        UniqueConstraint("tenantId", "permissionChangeAuditId"),
        SCHEMA,
    )

    permission_change_audit_id: Mapped[UUID] = Columns.uuid_pk("permissionChangeAuditId")
    tenant_id: Mapped[UUID] = Columns.tenant_id()
    changed_at: Mapped[datetime] = Columns.timestamp("changedAt")
    changed_by_identity_id: Mapped[UUID | None] = mapped_column(
        "changedByIdentityId", nullable=True
    )
    revision_number: Mapped[int] = mapped_column("revisionNumber", BigInteger)
    change_action: Mapped[str] = mapped_column("changeAction", String(64))
    target_type: Mapped[str] = mapped_column("targetType", String(64))
    target_id: Mapped[str | None] = mapped_column("targetId", String(100), nullable=True)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(
        "beforeState", JSONB, nullable=True
    )
    after_state: Mapped[dict[str, Any] | None] = mapped_column(
        "afterState", JSONB, nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column("changeReason", Text, nullable=True)
```

Add `BigInteger`, `PrimaryKeyConstraint` and `Text` to the `sqlalchemy` imports.

- [ ] **Step 4: Write the migration**

`t0007_authz_overrides_revisions_audit.py`, `revision = "t0007"`, `down_revision = "t0006"`. Create the four tables, grant `erp_app` select/insert/update/delete on the first three, and **select, insert only** on `PermissionChangeAudit` (it is append-only like `AuditEvents`). Apply `RlsSql.tenant_policy` to all four.

The revision row is seeded by provisioning, not by this migration, because the migration does not know the tenant id. Add to `TenantProvisioner` in Task 14; until then the test above seeds it. **Implementer: if Task 3 runs before Task 14, mark `test_every_tenant_database_starts_at_revision_one` with `@pytest.mark.xfail(reason="seeded in Task 14")` and remove the marker in Task 14.**

- [ ] **Step 5: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check . && uv run lint-imports
git add -A && git commit -m "feat(authz): add overrides, authorization revisions and change audit"
```

---

### Task 4: The typed condition tree

**Files:**
- Create: `backend/src/erp/modules/authz/conditions.py`
- Test: `backend/tests/authz/test_conditions.py`

**Interfaces:**
- Consumes: `InvalidConditionError` from `authz/errors.py`.
- Produces: `ConditionTree.validate(tree) -> None`, `ConditionTree.evaluate(tree, attributes) -> bool`, `ConditionFields.ALLOWED`.

This is pure logic with no database. It is the highest-risk code in the slice, so it is tested exhaustively before anything uses it.

- [ ] **Step 1: Write the failing tests**

`backend/tests/authz/test_conditions.py`:

```python
"""Restricted typed condition trees (WFL-05, R4)."""

from decimal import Decimal

import pytest

from erp.modules.authz.conditions import ConditionTree
from erp.modules.authz.errors import InvalidConditionError


class TestEvaluate:
    def test_an_empty_tree_is_always_true(self):
        assert ConditionTree.evaluate({}, {}) is True

    def test_a_comparison_reads_the_named_attribute(self):
        tree = {"field": "discountPercent", "op": "lte", "value": "5"}
        assert ConditionTree.evaluate(tree, {"discountPercent": Decimal("5")}) is True
        assert ConditionTree.evaluate(tree, {"discountPercent": Decimal("6")}) is False

    def test_decimals_never_go_through_float(self):
        tree = {"field": "amount", "op": "lte", "value": "0.30"}
        attributes = {"amount": Decimal("0.1") + Decimal("0.2")}
        assert ConditionTree.evaluate(tree, attributes) is True

    def test_a_missing_attribute_makes_a_comparison_false(self):
        tree = {"field": "discountPercent", "op": "lte", "value": "5"}
        assert ConditionTree.evaluate(tree, {}) is False

    def test_a_missing_attribute_is_never_silently_permissive(self):
        tree = {"field": "discountPercent", "op": "gte", "value": "5"}
        assert ConditionTree.evaluate(tree, {}) is False

    def test_is_null_is_the_only_way_to_match_an_absent_attribute(self):
        assert ConditionTree.evaluate({"field": "branchCode", "op": "isNull"}, {}) is True
        assert (
            ConditionTree.evaluate({"field": "branchCode", "op": "isNotNull"}, {}) is False
        )

    def test_all_requires_every_child(self):
        tree = {
            "all": [
                {"field": "discountPercent", "op": "lte", "value": "5"},
                {"field": "documentType", "op": "eq", "value": "quotation"},
            ]
        }
        assert ConditionTree.evaluate(
            tree, {"discountPercent": Decimal("4"), "documentType": "quotation"}
        ) is True
        assert ConditionTree.evaluate(
            tree, {"discountPercent": Decimal("4"), "documentType": "invoice"}
        ) is False

    def test_any_requires_one_child(self):
        tree = {
            "any": [
                {"field": "documentType", "op": "eq", "value": "quotation"},
                {"field": "documentType", "op": "eq", "value": "invoice"},
            ]
        }
        assert ConditionTree.evaluate(tree, {"documentType": "invoice"}) is True
        assert ConditionTree.evaluate(tree, {"documentType": "order"}) is False

    def test_not_inverts(self):
        tree = {"not": {"field": "documentType", "op": "eq", "value": "invoice"}}
        assert ConditionTree.evaluate(tree, {"documentType": "quotation"}) is True

    def test_in_and_not_in(self):
        tree = {"field": "documentType", "op": "in", "value": ["quotation", "order"]}
        assert ConditionTree.evaluate(tree, {"documentType": "order"}) is True
        assert ConditionTree.evaluate(tree, {"documentType": "invoice"}) is False

    def test_an_empty_all_is_true_and_an_empty_any_is_false(self):
        assert ConditionTree.evaluate({"all": []}, {}) is True
        assert ConditionTree.evaluate({"any": []}, {}) is False


class TestValidate:
    def test_an_unknown_field_is_rejected(self):
        with pytest.raises(InvalidConditionError):
            ConditionTree.validate({"field": "salary", "op": "eq", "value": "1"})

    def test_an_unknown_operator_is_rejected(self):
        with pytest.raises(InvalidConditionError):
            ConditionTree.validate({"field": "documentType", "op": "regex", "value": ".*"})

    def test_a_python_expression_is_not_a_condition(self):
        with pytest.raises(InvalidConditionError):
            ConditionTree.validate({"field": "__class__", "op": "eq", "value": "x"})

    def test_a_dunder_or_callable_value_is_rejected(self):
        with pytest.raises(InvalidConditionError):
            ConditionTree.validate("__import__('os').system('rm -rf /')")

    def test_depth_is_bounded(self):
        tree: dict = {"field": "documentType", "op": "eq", "value": "x"}
        for _ in range(ConditionTree.MAX_DEPTH + 1):
            tree = {"all": [tree]}
        with pytest.raises(InvalidConditionError):
            ConditionTree.validate(tree)

    def test_a_valid_tree_passes(self):
        ConditionTree.validate(
            {
                "all": [
                    {"field": "discountPercent", "op": "lte", "value": "5"},
                    {"any": [{"field": "branchCode", "op": "eq", "value": "DHK"}]},
                ]
            }
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/authz/test_conditions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erp.modules.authz.conditions'`

- [ ] **Step 3: Implement**

`backend/src/erp/modules/authz/conditions.py`:

```python
"""Restricted typed condition trees (WFL-05).

No eval, no raw SQL, no dynamic attribute or method names. A tree is
plain JSON: {"all": [...]}, {"any": [...]}, {"not": {...}} or a leaf
{"field": ..., "op": ..., "value": ...}.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from erp.modules.authz.errors import InvalidConditionError


class ConditionFields:
    """Fields a condition may read (AUTH-02: no arbitrary names)."""

    # Registered by the modules that own them. A field absent from
    # this set can never be referenced by a stored policy.
    ALLOWED: ClassVar[frozenset[str]] = frozenset(
        {
            "amount",
            "currency",
            "discountPercent",
            "documentType",
            "branchCode",
            "companyCode",
            "customerClassification",
            "warehouseCode",
        }
    )

    NUMERIC: ClassVar[frozenset[str]] = frozenset({"amount", "discountPercent"})


class ConditionTree:
    """Validate and evaluate a condition tree."""

    MAX_DEPTH: ClassVar[int] = 8
    GROUPS: ClassVar[frozenset[str]] = frozenset({"all", "any", "not"})
    COMPARISONS: ClassVar[frozenset[str]] = frozenset(
        {"eq", "ne", "lt", "lte", "gt", "gte", "in", "notIn"}
    )
    PRESENCE: ClassVar[frozenset[str]] = frozenset({"isNull", "isNotNull"})

    @classmethod
    def validate(cls, tree: Any, *, depth: int = 0) -> None:
        """Raise InvalidConditionError unless `tree` is a legal tree."""
        if depth > cls.MAX_DEPTH:
            raise InvalidConditionError("condition tree is too deep")
        if not isinstance(tree, Mapping):
            raise InvalidConditionError("a condition must be an object")
        if not tree:
            return
        keys = set(tree)
        if keys & cls.GROUPS:
            cls._validate_group(tree, keys, depth)
            return
        cls._validate_leaf(tree)

    @classmethod
    def evaluate(cls, tree: Any, attributes: Mapping[str, Any]) -> bool:
        """Evaluate a *validated* tree against request attributes."""
        if not isinstance(tree, Mapping) or not tree:
            return True
        if "all" in tree:
            return all(cls.evaluate(child, attributes) for child in tree["all"])
        if "any" in tree:
            return any(cls.evaluate(child, attributes) for child in tree["any"])
        if "not" in tree:
            return not cls.evaluate(tree["not"], attributes)
        return cls._compare(tree, attributes)

    @classmethod
    def _validate_group(cls, tree: Mapping[str, Any], keys: set[str], depth: int) -> None:
        if len(keys) != 1:
            raise InvalidConditionError("a group takes exactly one of all, any, not")
        name = keys.pop()
        children = tree[name]
        if name == "not":
            cls.validate(children, depth=depth + 1)
            return
        if not isinstance(children, Sequence) or isinstance(children, str | bytes):
            raise InvalidConditionError(f"{name} takes a list of conditions")
        for child in children:
            cls.validate(child, depth=depth + 1)

    @classmethod
    def _validate_leaf(cls, tree: Mapping[str, Any]) -> None:
        field = tree.get("field")
        operator = tree.get("op")
        if not isinstance(field, str) or field not in ConditionFields.ALLOWED:
            raise InvalidConditionError(f"unknown condition field {field!r}")
        if operator in cls.PRESENCE:
            return
        if operator not in cls.COMPARISONS:
            raise InvalidConditionError(f"unknown condition operator {operator!r}")
        if "value" not in tree:
            raise InvalidConditionError(f"{operator} needs a value")
        value = tree["value"]
        if operator in {"in", "notIn"}:
            if not isinstance(value, Sequence) or isinstance(value, str | bytes):
                raise InvalidConditionError(f"{operator} takes a list")
            return
        if not isinstance(value, str | int | bool):
            raise InvalidConditionError("a comparison value must be a scalar")

    @classmethod
    def _compare(cls, leaf: Mapping[str, Any], attributes: Mapping[str, Any]) -> bool:
        field = leaf["field"]
        operator = leaf["op"]
        actual = attributes.get(field)
        if operator == "isNull":
            return actual is None
        if operator == "isNotNull":
            return actual is not None
        # Absence is never a match: a policy that cannot be shown to
        # apply does not apply (explicit null semantics, WFL-05).
        if actual is None:
            return False
        expected = leaf.get("value")
        if operator in {"in", "notIn"}:
            members = [cls._coerce(field, v) for v in expected]
            found = cls._coerce(field, actual) in members
            return found if operator == "in" else not found
        return cls._ordered(operator, cls._coerce(field, actual), cls._coerce(field, expected))

    @classmethod
    def _ordered(cls, operator: str, actual: Any, expected: Any) -> bool:
        if operator == "eq":
            return bool(actual == expected)
        if operator == "ne":
            return bool(actual != expected)
        try:
            if operator == "lt":
                return bool(actual < expected)
            if operator == "lte":
                return bool(actual <= expected)
            if operator == "gt":
                return bool(actual > expected)
            return bool(actual >= expected)
        except TypeError:
            # Comparing incomparable types is a non-match, not a crash.
            return False

    @classmethod
    def _coerce(cls, field: str, value: Any) -> Any:
        """Numeric fields compare as Decimal; never as float (PLT-06)."""
        if field not in ConditionFields.NUMERIC:
            return value
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/authz/test_conditions.py -v`
Expected: PASS, 18 tests.

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): add the restricted typed condition tree"
```

---

### Task 5: Policy value objects and matching

**Files:**
- Create: `backend/src/erp/modules/authz/policy.py`
- Test: `backend/tests/authz/test_policy_matching.py`

**Interfaces:**
- Consumes: `ConditionTree` from `authz/conditions.py`.
- Produces: `AccessRequest`, `PolicyRecord`, `Decision`, `PolicyEffect`, `RecordScope`, `PolicyMatcher.matches(policy, request, *, actor_membership_id, now) -> bool`.

`PolicyMatcher` decides whether **one complete policy** applies. AUTH-05 forbids combining two policies, so this must never see more than one at a time.

- [ ] **Step 1: Write the failing tests**

`backend/tests/authz/test_policy_matching.py`:

```python
"""One policy matches a request only if every part of it matches."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from erp.modules.authz.policy import AccessRequest, PolicyMatcher, PolicyRecord

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
ACTOR = uuid4()


def policy(**overrides) -> PolicyRecord:
    base = {
        "policy_id": uuid4(),
        "origin": "group:test",
        "origin_name": "Test",
        "permission_key": "sales.discount.approve",
        "effect": "allow",
        "company_id": None,
        "branch_id": None,
        "warehouse_id": None,
        "record_scope": None,
        "conditions": {},
        "limit_amount": None,
        "limit_currency": None,
        "valid_from": None,
        "valid_to": None,
    }
    return PolicyRecord(**{**base, **overrides})


def matches(p: PolicyRecord, r: AccessRequest) -> bool:
    return PolicyMatcher.matches(p, r, actor_membership_id=ACTOR, now=NOW)


class TestPermissionKey:
    def test_a_different_key_never_matches(self):
        request = AccessRequest(permission_key="sales.order.create")
        assert matches(policy(), request) is False


class TestValidity:
    def test_an_expired_policy_does_not_match(self):
        p = policy(valid_to=NOW - timedelta(days=1))
        assert matches(p, AccessRequest("sales.discount.approve")) is False

    def test_a_future_policy_does_not_match(self):
        p = policy(valid_from=NOW + timedelta(days=1))
        assert matches(p, AccessRequest("sales.discount.approve")) is False

    def test_an_open_ended_policy_matches(self):
        assert matches(policy(), AccessRequest("sales.discount.approve")) is True


class TestScope:
    def test_an_unscoped_policy_matches_any_scope(self):
        request = AccessRequest("sales.discount.approve", branch_id=uuid4())
        assert matches(policy(), request) is True

    def test_a_scoped_policy_matches_its_own_scope(self):
        branch = uuid4()
        request = AccessRequest("sales.discount.approve", branch_id=branch)
        assert matches(policy(branch_id=branch), request) is True

    def test_a_scoped_policy_rejects_another_scope(self):
        request = AccessRequest("sales.discount.approve", branch_id=uuid4())
        assert matches(policy(branch_id=uuid4()), request) is False

    def test_a_scoped_policy_rejects_an_unscoped_request(self):
        # R7: absence of scope is not proof of being inside it.
        request = AccessRequest("sales.discount.approve")
        assert matches(policy(branch_id=uuid4()), request) is False


class TestRecordScope:
    def test_all_matches_any_record(self):
        request = AccessRequest("sales.discount.approve", record_owner_membership_id=uuid4())
        assert matches(policy(record_scope="all"), request) is True

    def test_own_matches_only_the_actors_own_record(self):
        p = policy(record_scope="own")
        assert matches(p, AccessRequest("sales.discount.approve",
                                        record_owner_membership_id=ACTOR)) is True
        assert matches(p, AccessRequest("sales.discount.approve",
                                        record_owner_membership_id=uuid4())) is False

    def test_own_rejects_a_request_with_no_owner(self):
        p = policy(record_scope="own")
        assert matches(p, AccessRequest("sales.discount.approve")) is False


class TestLimits:
    def test_an_unlimited_policy_matches_any_amount(self):
        request = AccessRequest(
            "sales.discount.approve", amount=Decimal("1000000"), currency="BDT"
        )
        assert matches(policy(), request) is True

    def test_an_amount_within_the_limit_matches(self):
        p = policy(limit_amount=Decimal("5000"), limit_currency="BDT")
        request = AccessRequest(
            "sales.discount.approve", amount=Decimal("5000"), currency="BDT"
        )
        assert matches(p, request) is True

    def test_an_amount_over_the_limit_does_not(self):
        p = policy(limit_amount=Decimal("5000"), limit_currency="BDT")
        request = AccessRequest(
            "sales.discount.approve", amount=Decimal("5000.01"), currency="BDT"
        )
        assert matches(p, request) is False

    def test_a_limit_never_crosses_currency(self):
        # AUTH-05: higher thresholds do not cross currency boundaries.
        p = policy(limit_amount=Decimal("5000"), limit_currency="BDT")
        request = AccessRequest(
            "sales.discount.approve", amount=Decimal("10"), currency="USD"
        )
        assert matches(p, request) is False

    def test_a_limited_policy_needs_an_amount(self):
        p = policy(limit_amount=Decimal("5000"), limit_currency="BDT")
        assert matches(p, AccessRequest("sales.discount.approve")) is False


class TestConditions:
    def test_conditions_must_hold(self):
        p = policy(conditions={"field": "discountPercent", "op": "lte", "value": "5"})
        inside = AccessRequest(
            "sales.discount.approve", attributes={"discountPercent": Decimal("4")}
        )
        outside = AccessRequest(
            "sales.discount.approve", attributes={"discountPercent": Decimal("6")}
        )
        assert matches(p, inside) is True
        assert matches(p, outside) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/authz/test_policy_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erp.modules.authz.policy'`

- [ ] **Step 3: Implement**

`backend/src/erp/modules/authz/policy.py`:

```python
"""Value objects for authorization decisions (AUTH-03, AUTH-05)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID

from erp.modules.authz.conditions import ConditionTree


class PolicyEffect:
    ALLOW: ClassVar[str] = "allow"
    DENY: ClassVar[str] = "deny"
    ALL: ClassVar[frozenset[str]] = frozenset({ALLOW, DENY})


class RecordScope:
    OWN: ClassVar[str] = "own"
    TEAM: ClassVar[str] = "team"
    ALL_RECORDS: ClassVar[str] = "all"
    # "team" is stored but rejected on write until P1.7 (R5).
    SUPPORTED: ClassVar[frozenset[str]] = frozenset({OWN, ALL_RECORDS})
    ALL: ClassVar[frozenset[str]] = frozenset({OWN, TEAM, ALL_RECORDS})


class DecisionCode:
    GRANTED: ClassVar[str] = "PERMISSION_GRANTED"
    DENIED: ClassVar[str] = "PERMISSION_DENIED"
    SELF_APPROVAL: ClassVar[str] = "SELF_APPROVAL_DENIED"
    NOT_LICENSED: ClassVar[str] = "FEATURE_NOT_LICENSED"
    MODULE_DISABLED: ClassVar[str] = "MODULE_DISABLED"
    UNKNOWN_KEY: ClassVar[str] = "PERMISSION_UNKNOWN"


@dataclass(frozen=True)
class AccessRequest:
    """What the caller wants to do, in the context they claim."""

    permission_key: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    warehouse_id: UUID | None = None
    record_owner_membership_id: UUID | None = None
    amount: Decimal | None = None
    currency: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyRecord:
    """One allow or deny rule, flattened from a group or override."""

    policy_id: UUID
    origin: str
    origin_name: str
    permission_key: str
    effect: str
    company_id: UUID | None
    branch_id: UUID | None
    warehouse_id: UUID | None
    record_scope: str | None
    conditions: Mapping[str, Any]
    limit_amount: Decimal | None
    limit_currency: str | None
    valid_from: datetime | None
    valid_to: datetime | None


@dataclass(frozen=True)
class Decision:
    """The outcome, with the policy that produced it (AUTH-07)."""

    allowed: bool
    code: str
    reason: str
    origin: str | None = None
    origin_name: str | None = None


class PolicyMatcher:
    """Does one complete policy apply to this request?

    Never call this with a merged policy: AUTH-05 requires a request
    to satisfy at least one *complete* allow, so conditions from
    different grants must never be combined.
    """

    @classmethod
    def matches(
        cls,
        policy: PolicyRecord,
        request: AccessRequest,
        *,
        actor_membership_id: UUID,
        now: datetime,
    ) -> bool:
        return (
            policy.permission_key == request.permission_key
            and cls._is_current(policy, now)
            and cls._scope_matches(policy, request)
            and cls._record_scope_matches(policy, request, actor_membership_id)
            and cls._limit_matches(policy, request)
            and ConditionTree.evaluate(policy.conditions, request.attributes)
        )

    @staticmethod
    def _is_current(policy: PolicyRecord, now: datetime) -> bool:
        if policy.valid_from is not None and now < policy.valid_from:
            return False
        return not (policy.valid_to is not None and now > policy.valid_to)

    @staticmethod
    def _scope_matches(policy: PolicyRecord, request: AccessRequest) -> bool:
        pairs = (
            (policy.company_id, request.company_id),
            (policy.branch_id, request.branch_id),
            (policy.warehouse_id, request.warehouse_id),
        )
        for allowed, requested in pairs:
            if allowed is None:
                continue  # unscoped policy: any value, including none
            if requested != allowed:
                return False  # R7: absence is not proof
        return True

    @staticmethod
    def _record_scope_matches(
        policy: PolicyRecord, request: AccessRequest, actor_membership_id: UUID
    ) -> bool:
        if policy.record_scope in (None, RecordScope.ALL_RECORDS):
            return True
        if policy.record_scope == RecordScope.OWN:
            return request.record_owner_membership_id == actor_membership_id
        # "team" cannot be evaluated until P1.7, so it never grants (R5).
        return False

    @staticmethod
    def _limit_matches(policy: PolicyRecord, request: AccessRequest) -> bool:
        if policy.limit_amount is None:
            return True
        if request.amount is None:
            return False
        # AUTH-05: a threshold never crosses a currency boundary.
        if request.currency != policy.limit_currency:
            return False
        return request.amount <= policy.limit_amount
```

- [ ] **Step 4: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz/test_policy_matching.py -v
uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): add policy value objects and single-policy matching"
```
Expected: PASS, 17 tests.

---

### Task 6: Repositories

**Files:**
- Create: `backend/src/erp/modules/authz/repository.py`
- Test: `backend/tests/authz/test_repository.py`

**Interfaces:**
- Produces:
  - `PermissionDefinitionRepository(session)`: `.all() -> list[PermissionDefinition]`, `.get(key) -> PermissionDefinition | None`
  - `PermissionGroupRepository(session)`: `.add`, `.get(tenant_id, group_id)`, `.by_name(tenant_id, name)`, `.list(tenant_id)`, `.delete(group)`
  - `GroupPolicyRepository(session)`: `.add`, `.get`, `.for_groups(tenant_id, group_ids) -> list[GroupPolicy]`, `.for_group(tenant_id, group_id)`, `.delete`
  - `UserGroupMembershipRepository(session)`: `.add`, `.remove(tenant_id, membership_id, group_id)`, `.group_ids_for(tenant_id, membership_id, now) -> list[UUID]`, `.membership_ids_in(tenant_id, group_id) -> list[UUID]`
  - `UserPermissionOverrideRepository(session)`: `.add`, `.get`, `.for_membership(tenant_id, membership_id) -> list[UserPermissionOverride]`, `.delete`
  - `AuthorizationRevisionRepository(session)`: `.current(tenant_id) -> int`, `.bump(tenant_id, identity_id) -> int` (locks the row `FOR UPDATE`), `.seed(tenant_id) -> None`
  - `PermissionChangeAuditRepository(session)`: `.add(...) -> UUID`

- [ ] **Step 1: Write the failing tests**

`backend/tests/authz/test_repository.py` — cover at minimum:

```python
def test_group_ids_exclude_expired_memberships(two_tenants, router):
    """A membership whose validTo has passed contributes no groups."""

def test_bump_increments_and_returns_the_new_revision(two_tenants, router):
    """Two bumps in a row give 2 then 3, starting from the seeded 1."""

def test_bump_locks_the_row_against_a_concurrent_bump(two_tenants, router):
    """A second session's bump blocks until the first commits, and
    the two revisions differ. Use two Database instances so they are
    genuinely separate connections."""

def test_policies_for_groups_returns_nothing_for_an_empty_group_list(two_tenants, router):
    """An empty IN () must not become 'select everything'."""
```

That last one is the classic bug: `GroupPolicyRepository.for_groups(tenant_id, [])` must return `[]` without issuing a query whose `WHERE ... IN ()` collapses. Write the test first.

- [ ] **Step 2: Run to verify failure**, then implement.

Follow the house style in `erp/modules/platform/repository.py`: a class per aggregate, `__init__(self, session: Session)`, no commits, no business rules. Use `NEW_ID = text("select uuidv7()")` only where an id is needed before insert.

`AuthorizationRevisionRepository.bump` must be:

```python
    def bump(self, tenant_id: UUID, identity_id: UUID | None) -> int:
        """Advance the revision, serialising concurrent editors."""
        row = self._session.execute(
            select(AuthorizationRevision)
            .where(AuthorizationRevision.tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one()
        row.revision_number += 1
        row.changed_at = datetime.now(UTC)
        row.changed_by_identity_id = identity_id
        self._session.flush()
        return row.revision_number
```

- [ ] **Step 3: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): add authorization repositories"
```

---

### Task 7: Policy resolver and revision cache

**Files:**
- Create: `backend/src/erp/modules/authz/cache.py`, `backend/src/erp/modules/authz/resolver.py`
- Test: `backend/tests/authz/test_resolver.py`

**Interfaces:**
- Consumes: the repositories from Task 6, `PolicyRecord` from Task 5.
- Produces: `RevisionCache(max_entries)` with `.get(key) -> list[PolicyRecord] | None`, `.put(key, policies)`, `.clear()`; `PolicyResolver(session, cache)` with `.resolve(tenant_id, membership_id, revision) -> list[PolicyRecord]`.

The cache key is `(tenant_id, membership_id, revision_number)`. Because the revision is part of the key, a policy change invalidates every stale entry the moment the revision advances — which is exactly AUTH-10's "maintain authorization revision and invalidate relevant caches on changes", without a separate invalidation path that could be forgotten.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_members_groups_and_overrides_become_one_policy_list(...)
def test_an_override_is_tagged_with_a_distinct_origin(...)
def test_the_second_resolve_at_the_same_revision_hits_the_cache(...)
    """Assert by counting queries, e.g. with a SQLAlchemy event listener
    on 'before_cursor_execute', not by timing."""
def test_a_new_revision_misses_the_cache(...)
def test_the_cache_evicts_least_recently_used_entries(...)
def test_two_tenants_never_share_a_cache_entry(...)
```

- [ ] **Step 2: Implement `RevisionCache`**

```python
"""Bounded LRU cache of resolved policies (AUTH-10)."""

import threading
from collections import OrderedDict
from uuid import UUID

from erp.modules.authz.policy import PolicyRecord

CacheKey = tuple[UUID, UUID, int]


class RevisionCache:
    """Policies keyed by (tenant, membership, revision).

    The revision is part of the key, so a policy change makes every
    stale entry unreachable without an explicit invalidation step.
    """

    def __init__(self, max_entries: int) -> None:
        self._max = max_entries
        self._entries: OrderedDict[CacheKey, list[PolicyRecord]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: CacheKey) -> list[PolicyRecord] | None:
        with self._lock:
            policies = self._entries.get(key)
            if policies is not None:
                self._entries.move_to_end(key)
            return policies

    def put(self, key: CacheKey, policies: list[PolicyRecord]) -> None:
        with self._lock:
            self._entries[key] = policies
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
```

- [ ] **Step 3: Implement `PolicyResolver`**

`resolve` loads, in one transaction: the membership's currently-valid group ids, every policy on those groups, and every override for the membership; then flattens all of them into `PolicyRecord`s. Group policies get `origin=f"group:{group_id}"` and `origin_name=<group name>`; overrides get `origin="override"` and `origin_name="user override"`. Expired **memberships** are filtered in SQL (Task 6); expired **policies** are not filtered here — `PolicyMatcher._is_current` handles them, so one cached list stays correct as time passes within a revision.

> **Implementer note:** that last sentence is a real constraint. Do not filter `validTo` in the resolver's SQL as an "optimisation" — it would bake the load time into a cached entry and let an expired override keep granting until the next policy change. `test_an_expired_override_stops_granting_without_a_revision_bump` in Task 16 covers it.

- [ ] **Step 4: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): resolve member policies through a revision-keyed cache"
```

---

### Task 8: The non-bypassable gates

**Files:**
- Create: `backend/src/erp/modules/authz/gates.py`
- Test: `backend/tests/authz/test_gates.py`

**Interfaces:**
- Consumes: `ModuleCatalog`, `TenantModules` (via `erp.modules.platform.interface`), `AuthzConfig`, `PermissionKeys`.
- Produces: `FeatureGate(catalog, tenant_modules)` with `.check(definition, tenant_id) -> Decision | None`; `SeparationOfDuties(config)` with `.check(definition, request, actor_membership_id) -> Decision | None`. Both return `None` when they do not object.

These run **before** any grant is consulted, so no grant can override them (AUTH-04 "non-bypassable tenant/security/segregation rules").

- [ ] **Step 1: Write the failing tests**

```python
class TestFeatureGate:
    def test_a_key_with_no_feature_passes(self): ...
    def test_an_uninstalled_module_is_not_licensed(self):
        """requiresFeatureKey='sales', catalog has no 'sales' -> Decision
        with code FEATURE_NOT_LICENSED (R6)."""
    def test_an_installed_but_disabled_module_is_denied(self):
        """code MODULE_DISABLED."""
    def test_an_enabled_module_passes(self): ...

class TestSeparationOfDuties:
    def test_approving_your_own_record_is_refused(self):
        """action_name='approve', record_owner == actor -> code
        SELF_APPROVAL_DENIED."""
    def test_approving_someone_elses_record_passes(self): ...
    def test_a_non_approval_action_on_your_own_record_passes(self):
        """action_name='view' on your own record is fine."""
    def test_release_and_authorize_count_as_approvals(self): ...
    def test_a_request_with_no_record_owner_passes(self): ...
```

- [ ] **Step 2: Implement**

```python
"""Non-bypassable checks that run before any grant (AUTH-04)."""

from uuid import UUID

from erp.core.modules import ModuleCatalog, ModuleCatalogError
from erp.modules.authz.config import AuthzConfig
from erp.modules.authz.permissions import PermissionDefinitionSpec
from erp.modules.authz.policy import AccessRequest, Decision, DecisionCode


class FeatureGate:
    """Is the action licensed for this tenant? (AUTH-04 tier 2, R6)"""

    def __init__(self, catalog: ModuleCatalog, tenant_modules: object) -> None:
        self._catalog = catalog
        self._modules = tenant_modules

    def check(
        self, definition: PermissionDefinitionSpec, tenant_id: UUID
    ) -> Decision | None:
        feature = definition.requires_feature_key
        if feature is None:
            return None
        try:
            self._catalog.get(feature)
        except ModuleCatalogError:
            return Decision(
                allowed=False,
                code=DecisionCode.NOT_LICENSED,
                reason=f"{feature} is not part of this deployment",
            )
        if feature in self._catalog.core_keys():
            return None
        if feature not in self._modules.enabled(tenant_id):
            return Decision(
                allowed=False,
                code=DecisionCode.MODULE_DISABLED,
                reason=f"the {feature} module is disabled for this tenant",
            )
        return None


class SeparationOfDuties:
    """Rules no grant may override (AUTH-06)."""

    def __init__(self, config: type[AuthzConfig] = AuthzConfig) -> None:
        self._config = config

    def check(
        self,
        definition: PermissionDefinitionSpec,
        request: AccessRequest,
        actor_membership_id: UUID,
    ) -> Decision | None:
        if definition.action_name not in self._config.SELF_APPROVAL_ACTIONS:
            return None
        if request.record_owner_membership_id != actor_membership_id:
            return None
        return Decision(
            allowed=False,
            code=DecisionCode.SELF_APPROVAL,
            reason="the author of a record may not approve it",
        )
```

- [ ] **Step 3: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz/test_gates.py -v && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): add the feature and separation-of-duties gates"
```

---

### Task 9: Ordered evaluation — `AuthorizationService`

**Files:**
- Create: `backend/src/erp/modules/authz/service.py`
- Test: `backend/tests/authz/test_evaluation.py`

**Interfaces:**
- Consumes: everything from Tasks 4–8.
- Produces: `AuthorizationService(database, context, catalog, tenant_modules, cache)` with `.evaluate(request) -> Decision` and `.require(request) -> None`, plus **`AuthorizationService.build(context, database, state) -> Self`**, the classmethod Task 10's `RequirePermission` and every other caller use to assemble it from `app.state`. Name it `build`, not `provide`: `provide` is reserved for methods FastAPI calls directly as a `Depends` target, and this one takes an already-resolved state object.

This is the heart of the slice: AUTH-04's order, exactly.

- [ ] **Step 1: Write the failing tests**

`backend/tests/authz/test_evaluation.py` must assert the order itself, not just outcomes:

```python
class TestEvaluationOrder:
    def test_no_grant_means_denied(self):
        """AUTH-12 case 1, and AUTH-04's default deny."""

    def test_two_groups_union_their_grants(self):
        """AUTH-12 case 2: a member of both gets both permissions."""

    def test_a_user_override_can_add_a_grant(self):
        """AUTH-12 case 3."""

    def test_any_matching_deny_beats_every_grant(self):
        """AUTH-12 case 4: group A allows, group B denies -> denied.
        Assert the Decision's origin names the denying group."""

    def test_a_user_grant_cannot_override_a_group_deny(self):
        """AUTH-04, explicitly: 'An added user grant may extend a
        group's grant but cannot override a matching denial.'"""

    def test_an_expired_override_no_longer_grants(self):
        """AUTH-12 case 5."""

    def test_conditions_from_two_grants_never_combine(self):
        """AUTH-12 case 6 / AUTH-05: allow <=5% in Dhaka and <=10% in
        Chattogram; a 10% request in Dhaka is denied."""

    def test_a_disabled_feature_denies_before_grants_are_read(self):
        """AUTH-12 case 7. Grant the permission, disable the module,
        assert code MODULE_DISABLED -- not PERMISSION_DENIED. This
        proves the tier ran before grant matching."""

    def test_self_approval_is_refused_even_with_an_explicit_grant(self):
        """AUTH-12 case 13. Grant sales.discount.approve with scope
        'all', then approve your own record: SELF_APPROVAL_DENIED.
        This proves the non-bypassable tier runs before grants."""

    def test_an_unknown_permission_key_is_denied(self):
        """A key absent from the catalogue is denied, never allowed."""
```

- [ ] **Step 2: Run to verify failure**, then implement.

`AuthorizationService.evaluate` follows AUTH-04 literally, one tier per block, in this order and no other:

```python
    def evaluate(self, request: AccessRequest) -> Decision:
        """AUTH-04, in order. Each tier can only deny; the last
        tier is the only one that can allow."""
        definition = PermissionKeys.get(request.permission_key)
        if definition is None:
            return Decision(False, DecisionCode.UNKNOWN_KEY, "unknown permission key")

        # 1. Active membership: established by TenantContextProvider
        #    before this service is constructed (TEN-03).
        # 2. Licensed action.
        refusal = self._features.check(definition, self._context.tenant_id)
        if refusal is not None:
            return refusal

        # 3. Non-bypassable tenant/security/segregation rules.
        refusal = self._duties.check(definition, request, self._context.membership_id)
        if refusal is not None:
            return refusal

        policies = self._policies()
        now = datetime.now(UTC)

        # 4. Matching explicit denials. Deny always wins (AUTH-04).
        for policy in policies:
            if policy.effect == PolicyEffect.DENY and self._matches(policy, request, now):
                return Decision(
                    False, DecisionCode.DENIED,
                    "an explicit denial applies", policy.origin, policy.origin_name,
                )

        # 5. Matching grants. One *complete* policy must match; the
        #    matcher never combines two (AUTH-05).
        for policy in policies:
            if policy.effect == PolicyEffect.ALLOW and self._matches(policy, request, now):
                return Decision(
                    True, DecisionCode.GRANTED,
                    "granted", policy.origin, policy.origin_name,
                )

        # 6. Default deny.
        return Decision(False, DecisionCode.DENIED, "no policy grants this action")
```

`require(request)` raises the matching error class from `authz/errors.py` (`PermissionDeniedError`, `SelfApprovalDeniedError`, `FeatureNotLicensedError`, `ModuleDisabledError`) chosen by `Decision.code`, with the decision's reason as the detail. Map it through a small `ClassVar` dict, not an if-chain.

> **Implementer note:** the two loops must stay separate. A single loop that returns on the first match of either effect would make the outcome depend on row order, which is the deny-precedence bug AUTH-04 exists to prevent. `test_any_matching_deny_beats_every_grant` must fail if the loops are merged — make sure the fixture inserts the allow **before** the deny so the merged version really does break.

- [ ] **Step 3: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check . && uv run lint-imports
git add -A && git commit -m "feat(authz): evaluate access in AUTH-04 order with deny precedence"
```

---

### Task 10: The public surface — `RequirePermission`

**Files:**
- Create: `backend/src/erp/modules/authz/interface.py`
- Modify: `backend/src/erp/app.py` (build the shared `RevisionCache` onto `app.state`)
- Modify: `backend/pyproject.toml` (import-linter contract)
- Test: `backend/tests/authz/test_interface.py`, `backend/tests/core/test_imports.py`

**Interfaces:**
- Produces: `RequirePermission(permission_key)` usable as `Depends(...)`, returning the `AuthorizationService` so the endpoint can make further scoped checks; `AuthorizationFacade` re-exporting `AccessRequest`, `Decision`, `AuthorizationService`, `PermissionKeys`.

Other modules import **only** from `erp.modules.authz.interface`. Nothing else in `authz` is public.

- [ ] **Step 1: Write the failing tests**

```python
def test_require_permission_allows_a_granted_call(client, ...):
    """A controller guarded by RequirePermission returns 200 when the
    caller's group grants the key."""

def test_require_permission_returns_problem_json_on_denial(client, ...):
    """403 with content-type application/problem+json and
    body['code'] == 'PERMISSION_DENIED'."""

def test_require_permission_denies_before_the_endpoint_body_runs(...):
    """Register a probe controller that appends to a list; assert the
    list is still empty after a denied call."""
```

And an architectural test in `backend/tests/core/test_imports.py`:

```python
def test_only_the_authz_interface_is_imported_by_other_modules():
    """No module outside erp.modules.authz imports erp.modules.authz.*
    except erp.modules.authz.interface. Walk the AST of every file
    under src/erp, like tests/core/test_class_based.py does."""
```

- [ ] **Step 2: Implement**

```python
"""The only surface other modules may import (ARC-01)."""

from typing import Annotated, Self
from uuid import UUID

from fastapi import Depends, Request

from erp.core.db import Database
from erp.modules.authz.cache import RevisionCache
from erp.modules.authz.policy import AccessRequest, Decision
from erp.modules.authz.service import AuthorizationService
from erp.modules.platform.context import RequestContext
from erp.modules.platform.dependencies import (
    TenantContextProvider,
    TenantDatabaseProvider,
)

__all__ = [
    "AccessRequest",
    "AuthorizationService",
    "Decision",
    "RequirePermission",
]


class RequirePermission:
    """Guard a route with one permission key (AUTH-09).

    Usage:
        self.router.add_api_route(
            "", self.list_companies, methods=["GET"],
            dependencies=[Depends(RequirePermission("platform.company.view"))],
        )

    or as a parameter, when the endpoint needs further scoped checks:
        authz: Annotated[
            AuthorizationService, Depends(RequirePermission("sales.order.create"))
        ],
    """

    def __init__(self, permission_key: str) -> None:
        self._permission_key = permission_key

    def __call__(
        self,
        context: Annotated[RequestContext, Depends(TenantContextProvider.resolve)],
        database: Annotated[Database, Depends(TenantDatabaseProvider.resolve)],
        request: Request,
    ) -> AuthorizationService:
        service = AuthorizationService.build(context, database, request.app.state)
        service.require(AccessRequest(permission_key=self._permission_key))
        return service
```

Add to `ApplicationFactory.build`: `app.state.policy_cache = RevisionCache(AuthzConfig.POLICY_CACHE_SIZE)`. `AuthorizationService.build(context, database, state)` reads `state.module_catalog`, `state.tenant_modules` and `state.policy_cache`.

Add the import-linter contract to `backend/pyproject.toml`:

```toml
[[tool.importlinter.contracts]]
name = "modules reach authz only through its interface"
type = "forbidden"
source_modules = ["erp.modules.platform", "erp.modules.integration"]
forbidden_modules = [
    "erp.modules.authz.service",
    "erp.modules.authz.repository",
    "erp.modules.authz.models",
    "erp.modules.authz.resolver",
]
```

> **Note on a real circular-import risk:** `authz.interface` imports `platform.dependencies`, and Task 15 makes `platform.controller` import `authz.interface`. Python tolerates this only because the platform import happens at module level in `interface.py` while the authz import in `platform/controller.py` also happens at module level — which **will** deadlock if the two modules import each other during initialisation. Resolve it by importing `RequirePermission` inside `platform/controller.py` at module level but having `authz/interface.py` import `TenantContextProvider` and `TenantDatabaseProvider` from `erp.modules.platform.dependencies` (a leaf module that imports no controllers). Verify with `uv run python -c "import erp.app"` before committing. If it still cycles, move `RequirePermission` to depend on `erp.core.deps` accessors instead and pass the providers in from `ApplicationFactory`.

- [ ] **Step 3: Run, lint, commit**

```bash
cd backend && uv run python -c "import erp.app" && uv run pytest tests -q
uv run ruff format . && uv run ruff check . && uv run lint-imports
git add -A && git commit -m "feat(authz): expose RequirePermission as the module's only public surface"
```

---

### Task 11: Admin writes — delegation, revision bump, change audit

**Files:**
- Create: `backend/src/erp/modules/authz/delegation.py`
- Modify: `backend/src/erp/modules/authz/service.py` (add `PermissionAdminService`)
- Create: `backend/src/erp/modules/authz/schemas.py`
- Test: `backend/tests/authz/test_delegation.py`

**Interfaces:**
- Consumes: `AuthorizationService`, the repositories, `PermissionKeys`.
- Produces: `PolicyInput` (a frozen dataclass in `policy.py` carrying the policy fields a write supplies: `permission_key`, `policy_effect`, `company_id`, `branch_id`, `warehouse_id`, `record_scope`, `conditions`, `limit_amount`, `limit_currency`, `valid_from`, `valid_to` — the same shape `GroupPolicyIn` and `OverrideIn` validate into, so the guard never sees a Pydantic model); `DelegationGuard(authorization)` with `.check_grantable(policy: PolicyInput, actor_membership_id)`, `.check_not_self(target_membership_id, actor_membership_id)`, `.check_group_editable(group)`, `.check_not_last_admin(tenant_id, membership_id)`; `PermissionAdminService` with `create_group`, `update_group`, `delete_group`, `add_policy`, `remove_policy`, `add_member`, `remove_member`, `create_override`, `delete_override`.

Every write goes through one path that, **in a single transaction**: validates, applies, bumps the revision, writes a `PermissionChangeAudit` row with before/after state (R9), and writes a `platform."AuditEvents"` row through the existing `AuditTrail` (IAM-04).

- [ ] **Step 1: Write the failing tests**

```python
class TestDelegation:
    def test_an_admin_cannot_grant_what_they_do_not_hold(self):
        """AUTH-12 case 10. Actor holds platform.permissions.manage but
        not finance.cost.view; granting finance.cost.view to a group
        raises DelegationDeniedError."""

    def test_an_admin_can_grant_what_they_hold(self): ...

    def test_an_admin_cannot_widen_scope_beyond_their_own(self):
        """Actor holds sales.discount.approve for branch DHK only;
        granting it unscoped (all branches) is refused."""

    def test_an_admin_may_always_write_a_deny(self):
        """R8: denies need no delegation, because restricting access
        cannot escalate privilege."""

    def test_an_admin_cannot_add_themselves_to_a_group(self):
        """SelfEscalationDeniedError."""

    def test_an_admin_cannot_write_an_override_for_themselves(self): ...

    def test_a_protected_template_cannot_be_edited_or_deleted(self):
        """ProtectedTemplateError."""

    def test_the_last_permission_administrator_cannot_be_removed(self):
        """LastAdminProtectedError, on both remove_member and on a deny
        override that would strip platform.permissions.manage."""

    def test_a_bulk_member_add_enforces_delegation_per_entry(self):
        """AUTH-08: 'bulk endpoints must not bypass it.' Send a batch
        where entry 2 exceeds delegation; assert the whole call is
        rejected and entry 1 was not written either."""

class TestWritePath:
    def test_a_change_bumps_the_revision_once(self): ...
    def test_a_change_writes_before_and_after_state(self): ...
    def test_a_change_writes_an_audit_event(self): ...
    def test_a_rejected_change_leaves_the_revision_untouched(self):
        """The whole transaction rolls back: no revision bump, no
        change-audit row, no policy row."""
```

- [ ] **Step 2: Implement `DelegationGuard`**

`check_grantable` builds an `AccessRequest` describing the policy being granted, evaluated **as the actor**, and refuses unless the actor's own decision is `allowed`:

```python
    def check_grantable(self, policy: PolicyInput, actor_membership_id: UUID) -> None:
        """An administrator may grant only what they hold (AUTH-08)."""
        if policy.policy_effect == PolicyEffect.DENY:
            return  # R8: denying never escalates
        probe = AccessRequest(
            permission_key=policy.permission_key,
            company_id=policy.company_id,
            branch_id=policy.branch_id,
            warehouse_id=policy.warehouse_id,
            # Evaluate at the widest point of the grant being made: if
            # the grant is unscoped, the actor must hold it unscoped.
            record_owner_membership_id=actor_membership_id,
            amount=policy.limit_amount,
            currency=policy.limit_currency,
        )
        if not self._authorization.evaluate(probe).allowed:
            raise DelegationDeniedError(
                f"you do not hold {policy.permission_key} at this scope"
            )
```

> **Implementer: the scope-widening case needs care.** An actor scoped to branch DHK must not grant an unscoped policy. Probing with `branch_id=None` against a policy that has `branch_id=DHK` returns *not allowed* under R7 (a scoped policy does not match an unscoped request), which gives the right answer for free. Confirm with `test_an_admin_cannot_widen_scope_beyond_their_own` before relying on it; if R7's behaviour ever changes, this check must become explicit.

`check_not_last_admin` counts memberships that currently evaluate to `allowed` for `platform.permissions.manage` and refuses when removing the target would take the count to zero. Count by evaluating, not by counting group rows — a deny override could already have neutralised a member who still appears in the admin group.

- [ ] **Step 3: Implement `PermissionAdminService`**

One private helper carries the shared write shape so no caller can forget a step:

```python
    def _apply(
        self,
        *,
        session: Session,
        change_action: str,
        target_type: str,
        target_id: str | None,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
        reason: str | None = None,
    ) -> None:
        """Bump the revision and record the change (AUTH-10, AUTH-11)."""
        revision = AuthorizationRevisionRepository(session).bump(
            self._context.tenant_id, self._context.identity_id
        )
        PermissionChangeAuditRepository(session).add(
            tenant_id=self._context.tenant_id,
            changed_by_identity_id=self._context.identity_id,
            revision_number=revision,
            change_action=change_action,
            target_type=target_type,
            target_id=target_id,
            before_state=before,
            after_state=after,
            change_reason=reason,
        )
        AuditTrail(session).record(
            tenant_id=self._context.tenant_id,
            actor_identity_id=self._context.identity_id,
            action=change_action,
            target_type=target_type,
            target_id=target_id,
            outcome="success",
            reason=reason,
            details={"revision": revision, "after": after},
        )
```

Validation before any write: `ConditionTree.validate(policy.conditions)`; `record_scope in RecordScope.SUPPORTED` or raise `RecordScopeUnsupportedError` (R5); `permission_key in PermissionKeys.keys()` or `NotFoundError`; `policy_effect in PolicyEffect.ALL`.

- [ ] **Step 4: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): enforce delegation limits and audit every policy change"
```

---

### Task 12: Editor API — groups, policies, members, overrides

**Files:**
- Create: `backend/src/erp/modules/authz/controller.py`
- Modify: `backend/src/erp/modules/authz/schemas.py`, `module.py` (register controllers)
- Test: `backend/tests/authz/test_admin_api.py`

**Interfaces:**
- Produces these routes, every one guarded by `RequirePermission("platform.permissions.manage")`:

| Method | Path |
|---|---|
| GET | `/api/v1/authz/permissions` |
| GET, POST | `/api/v1/authz/groups` |
| GET, PATCH, DELETE | `/api/v1/authz/groups/{permissionGroupId}` |
| GET, POST | `/api/v1/authz/groups/{permissionGroupId}/policies` |
| DELETE | `/api/v1/authz/groups/{permissionGroupId}/policies/{groupPolicyId}` |
| GET | `/api/v1/authz/groups/{permissionGroupId}/members` |
| PUT, DELETE | `/api/v1/authz/groups/{permissionGroupId}/members/{membershipId}` |
| GET, POST | `/api/v1/authz/overrides` |
| DELETE | `/api/v1/authz/overrides/{userPermissionOverrideId}` |
| GET | `/api/v1/authz/revision` |

- [ ] **Step 1: Write the failing tests**

```python
def test_creating_a_group_returns_camel_case_json(client, admin_token):
    """body has 'permissionGroupId', 'groupName', 'isTemplate' --
    never 'permission_group_id'."""

def test_a_caller_without_permissions_manage_gets_403(client, member_token): ...
def test_an_unknown_permission_key_is_rejected_with_404(client, admin_token): ...
def test_record_scope_team_is_rejected_with_422(client, admin_token):
    """R5: code RECORD_SCOPE_UNSUPPORTED."""
def test_an_invalid_condition_tree_is_rejected_with_422(client, admin_token):
    """code INVALID_CONDITION."""
def test_a_limit_amount_is_sent_and_returned_as_a_string(client, admin_token):
    """PLT-06: '5000.0000', never a JSON number."""
def test_deleting_a_group_cascades_to_its_policies(client, admin_token): ...
def test_a_group_name_is_unique_per_tenant(client, admin_token):
    """409 CONFLICT on the second create."""
def test_the_revision_advances_after_each_write(client, admin_token): ...
def test_cross_tenant_ids_are_refused(client, admin_token, two_tenants):
    """AUTH-12 case 8: POST a policy whose companyId belongs to tenant
    B while acting as tenant A. Expect 4xx, and assert nothing was
    written -- the composite FK plus RLS must both hold."""
```

- [ ] **Step 2: Implement the schemas**

All inherit `ApiSchema`. Decimal fields use `DecimalStr` from `erp.shared.money`. Example:

```python
class GroupPolicyIn(ApiSchema):
    permission_key: str
    policy_effect: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    warehouse_id: UUID | None = None
    record_scope: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    limit_amount: DecimalStr | None = None
    limit_currency: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
```

- [ ] **Step 3: Implement the controllers**

Four `Controller` subclasses — `PermissionCatalogController`, `PermissionGroupController`, `GroupMemberController`, `OverrideController` — each registering its bound methods with `add_api_route`, following `platform/controller.py` exactly. Register all four in `authz/module.py`'s `controllers` tuple.

- [ ] **Step 4: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check . && uv run lint-imports
git add -A && git commit -m "feat(authz): add the group, policy, member and override editor API"
```

---

### Task 13: Effective-permissions inspector and change preview

**Files:**
- Modify: `backend/src/erp/modules/authz/service.py`, `controller.py`, `schemas.py`
- Test: `backend/tests/authz/test_inspector.py`

**Interfaces:**
- Produces: `GET /api/v1/authz/effective-permissions?membershipId=` and `POST /api/v1/authz/preview`.

AUTH-07: "an effective-permissions inspector. The inspector explains grant/deny origin, licence restrictions and context. Protect it against exposing inaccessible company or user metadata."

- [ ] **Step 1: Write the failing tests**

```python
def test_the_inspector_lists_every_key_with_its_decision(client, admin_token): ...

def test_the_inspector_names_the_group_that_granted(client, admin_token):
    """entry['origin'] == 'group:<uuid>', entry['originName'] == 'Sales'."""

def test_the_inspector_names_the_group_that_denied(client, admin_token): ...

def test_the_inspector_reports_a_licence_restriction_distinctly(client, admin_token):
    """A key whose module is disabled reports code MODULE_DISABLED, not
    PERMISSION_DENIED, so the UI can explain why (AUTH-07)."""

def test_the_inspector_does_not_leak_company_names_the_caller_cannot_see(...):
    """AUTH-07's last sentence. Scope references are returned as ids
    only; the caller resolves names through endpoints that are
    themselves permission-checked."""

def test_inspecting_another_membership_requires_permissions_manage(client, member_token):
    """403 for a caller who is not an administrator."""

def test_a_member_may_inspect_their_own_effective_permissions(client, member_token):
    """AUTH-07's inspector is also how the UI decides what to show, so
    self-inspection needs no admin right."""

def test_preview_reports_the_delta_without_writing(client, admin_token):
    """POST a candidate policy; response lists which keys change from
    denied to allowed. Assert the revision did not move and no policy
    row exists afterwards."""
```

- [ ] **Step 2: Implement**

`effective_permissions(membership_id)` evaluates every key in `PermissionKeys.ALL` for that membership and returns `EffectivePermissionOut(permission_key, allowed, code, reason, origin, origin_name)`. It reuses `AuthorizationService.evaluate` rather than reimplementing matching — the inspector must never be able to disagree with enforcement.

`preview(candidate)` runs inside a transaction that is **rolled back**: apply the candidate through `PermissionAdminService`, recompute effective permissions, compare against the current set, then roll back. Implement with an explicit `session.begin_nested()` savepoint and a rollback in a `finally`, and assert in the test that the revision did not move.

> **Implementer note:** the preview must not leave the shared `RevisionCache` poisoned. The rolled-back transaction bumps the revision inside the savepoint, so entries cached under the phantom revision would linger. Either construct the preview's resolver with a throw-away `RevisionCache` instance, or key the preview's cache entries separately. Whichever you choose, add a test that a preview followed by a real evaluation returns the pre-preview answer.

- [ ] **Step 3: Run, lint, commit**

```bash
cd backend && uv run pytest tests/authz -v && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): add the effective-permissions inspector and change preview"
```

---

### Task 14: The seven templates, provisioning and `grant-admin`

**Files:**
- Create: `backend/src/erp/modules/authz/templates.py`
- Modify: `backend/src/erp/modules/platform/provisioning.py`, `backend/src/erp/cli.py`
- Test: `backend/tests/authz/test_templates.py`, `backend/tests/platform/test_cli.py` (extend)

**Interfaces:**
- Produces: `GroupTemplates.ALL`, `GroupTemplates.seed(session, tenant_id)`; `erp.cli grant-admin --tenant <uuid> --membership <uuid>`.

AUTH-01 names exactly seven editable templates: salesperson, sales manager, warehouse operator, warehouse manager, accountant, HR/payroll and client administrator.

- [ ] **Step 1: Write the failing tests**

```python
def test_provisioning_seeds_the_seven_templates(provisioner, router):
    expected = {
        "Salesperson", "Sales manager", "Warehouse operator",
        "Warehouse manager", "Accountant", "HR and payroll",
        "Client administrator",
    }
    # assert set(group names where isTemplate) == expected

def test_templates_are_editable_except_the_client_administrator(...):
    """AUTH-08 protects the template that carries
    platform.permissions.manage; the other six are editable, because
    AUTH-01 says templates are editable."""

def test_manager_templates_do_not_imply_unrestricted_access(...):
    """AUTH-01's last sentence, asserted concretely: the sales manager
    template grants no people.payroll.view and no finance.cost.view."""

def test_provisioning_seeds_revision_one(provisioner, router):
    """Removes the xfail added in Task 3."""

def test_grant_admin_puts_a_membership_in_the_administrator_group(cli_env, ...):
    """The bootstrap path: a fresh tenant has no administrator until
    the vendor runs grant-admin."""

def test_grant_admin_is_idempotent(cli_env, ...): ...
```

- [ ] **Step 2: Implement the templates**

Each template is a declarative object: a name, a protected flag, and a tuple of `PolicyInput`s. Keep the grants deliberately narrow — AUTH-01 is explicit that a label like "manager" never implies unrestricted access, and `test_manager_templates_do_not_imply_unrestricted_access` enforces it.

Suggested starting grants (the owner will refine them; they are editable by design):

| Template | Grants | Protected |
|---|---|---|
| Salesperson | `sales.order.create` (record scope `own`) | no |
| Sales manager | `sales.order.create` (`all`), `sales.discount.approve` | no |
| Warehouse operator | `inventory.count.submit` | no |
| Warehouse manager | `inventory.count.submit`, `inventory.adjustment.approve`, `shipment.loading.approve`, `shipment.dispatch.release` | no |
| Accountant | `finance.cost.view`, `platform.company.view` | no |
| HR and payroll | `people.payroll.view` | no |
| Client administrator | `platform.permissions.manage`, `platform.company.view`, `platform.audit.view` | **yes** |

- [ ] **Step 3: Wire provisioning**

`TenantProvisioner` seeds, in the tenant database, after migrations run: the `AuthorizationRevisions` row (revision 1) and the seven template groups. Seeding runs as `erp_owner` in the provisioning transaction, and must be **idempotent** — re-provisioning an existing tenant must not duplicate groups or reset the revision. Guard on `PermissionGroupRepository.by_name`.

- [ ] **Step 4: Add `grant-admin` to the CLI**

A `Cli` method following the existing `enable_module` shape: resolve the tenant, open its database, find the "Client administrator" group, insert a `UserGroupMembership` for the given membership id, bump the revision, write a change-audit row with `changed_by_identity_id = None` and `change_reason = "vendor bootstrap"`. Print the resulting revision. Document it in `CLAUDE.md`'s command list and in `README.md`.

- [ ] **Step 5: Run, lint, commit**

```bash
cd backend && uv run pytest tests -q && uv run ruff format . && uv run ruff check .
git add -A && git commit -m "feat(authz): seed the seven AUTH-01 templates and add grant-admin"
```

---

### Task 15: Enforce on real endpoints, including hidden fields

**Files:**
- Modify: `backend/src/erp/modules/platform/controller.py`, `service.py`, `schemas.py`, `repository.py`
- Modify: `backend/tests/platform/test_context_api.py`, `test_module_gating.py`, `backend/tests/conftest.py`
- Test: `backend/tests/platform/test_field_visibility.py`

**Interfaces:**
- Consumes: `RequirePermission`, `AuthorizationService`, `AccessRequest` from `authz.interface`.
- Produces: `GET /api/v1/companies` guarded by `platform.company.view`; new `GET /api/v1/audit-events` guarded by `platform.audit.view`, whose `auditDetails` field is redacted unless the caller also holds `platform.audit.details.view` (R11).

This is where AUTH-09 stops being theoretical: "Backend endpoints, query filtering, field serialization, exports, background jobs and sockets use the same policy service."

- [ ] **Step 1: Write the failing tests**

```python
def test_listing_companies_needs_the_view_permission(client, member_token):
    """403 PERMISSION_DENIED without it, 200 with it."""

def test_audit_details_are_hidden_without_the_details_permission(client, token):
    """AUTH-12 case 9. The caller holds platform.audit.view only:
    every item's 'auditDetails' is None and 'detailsRedacted' is True.
    The rest of the row is present."""

def test_audit_details_are_visible_with_the_details_permission(client, token): ...

def test_the_hidden_field_does_not_leak_through_a_filter(client, token):
    """A caller without the details permission cannot filter on a value
    inside auditDetails to infer it -- the filter parameter is refused
    with 403 rather than silently ignored."""
```

That last test matters: AUTH-09 says hidden fields "must not leak through aggregate reports or download endpoints", and a silently-ignored filter is a slower leak, not a fix.

- [ ] **Step 2: Guard the company endpoint**

```python
    def register_routes(self) -> None:
        self.router.add_api_route(
            "",
            self.list_companies,
            methods=["GET"],
            dependencies=[Depends(RequirePermission(PermissionKeys.PLATFORM_COMPANY_VIEW))],
        )
```

- [ ] **Step 3: Fix the existing tests this breaks**

`tests/platform/test_context_api.py` and `test_module_gating.py` call `/api/v1/companies` with tokens that now hold no permission. Add a `granted_membership` fixture to `backend/tests/conftest.py` that creates a group, grants a list of keys and joins a membership to it, then use it in those tests. **Do not** weaken the guard to keep old tests green — the guard is the deliverable.

- [ ] **Step 4: Implement field visibility**

Add a small class, not a function:

```python
class FieldVisibility:
    """Drop fields the caller is not permitted to see (AUTH-09)."""

    def __init__(self, authorization: AuthorizationService) -> None:
        self._authorization = authorization

    def may_see(self, permission_key: str) -> bool:
        return self._authorization.evaluate(AccessRequest(permission_key)).allowed
```

The service asks once per request, not once per row, and passes the boolean into the serializer.

- [ ] **Step 5: Run the whole suite, lint, commit**

```bash
cd backend && uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run lint-imports
git add -A && git commit -m "feat(platform): enforce permissions on companies and audit events"
```

---

### Task 16: AUTH-12 conformance suite

**Files:**
- Create: `backend/tests/authz/test_auth12_conformance.py`
- Modify: `docs/plan/traceability.md`, `CLAUDE.md` (command list), `README.md` (status line)

**Interfaces:**
- Consumes: everything built above, through the HTTP API only.

The exit evidence for this milestone. One test class per AUTH-12 case, named for the case, **driven through the API** — not through the service — because AUTH-12 says "Verify the same results through ERP UI/API".

- [ ] **Step 1: Write the suite**

```python
"""AUTH-12: the thirteen required authorization cases, via the API."""


class TestCase01NoGrantDenial:
    def test_a_member_with_no_group_is_denied(self, client, member_token): ...


class TestCase02MultipleGroupUnion:
    def test_membership_of_two_groups_unions_their_grants(self, ...): ...


class TestCase03UserAllow:
    def test_an_override_grants_what_no_group_grants(self, ...): ...


class TestCase04DenyPrecedence:
    def test_a_deny_in_one_group_beats_an_allow_in_another(self, ...): ...
    def test_a_user_allow_cannot_beat_a_group_deny(self, ...): ...


class TestCase05ExpiredOverride:
    def test_an_override_past_its_validTo_no_longer_grants(self, ...): ...
    def test_it_expires_without_any_policy_change(self, ...):
        """No revision bump between the two calls: expiry is evaluated
        per request, not cached. Covers the Task 7 resolver note."""


class TestCase06DisjointBranchLimits:
    def test_five_percent_in_dhaka_and_ten_in_chattogram_is_not_ten_in_dhaka(self, ...):
        """AUTH-05's worked example, verbatim."""
    def test_a_money_limit_does_not_cross_currency(self, ...): ...


class TestCase07DisabledFeature:
    def test_a_granted_action_is_refused_while_its_module_is_disabled(self, ...): ...
    def test_it_is_allowed_again_once_the_module_is_enabled(self, ...): ...


class TestCase08CrossTenantIdentifiers:
    def test_a_policy_cannot_reference_another_tenants_company(self, ...): ...
    def test_another_tenants_company_id_in_a_request_never_matches(self, ...): ...


class TestCase09HiddenFields:
    def test_audit_details_are_redacted_without_the_field_permission(self, ...): ...


class TestCase10DelegationLimits:
    def test_an_administrator_cannot_grant_beyond_their_own_authority(self, ...): ...
    def test_a_bulk_call_does_not_bypass_the_check(self, ...): ...


class TestCase11ConcurrentPolicyChanges:
    def test_a_decision_reflects_a_change_made_after_it_was_cached(self, ...):
        """Evaluate (caching at revision N), change the policy in a
        second session, evaluate again: the new answer, not the cached
        one."""
    def test_two_concurrent_editors_produce_two_distinct_revisions(self, ...): ...


class TestCase12RevokedAccessInQueuedWork:
    def test_a_queued_action_rechecks_access_at_execution(self, ...):
        """AUTH-10. Write an outbox event while permitted, revoke the
        grant, then run the consumer: it must re-evaluate and refuse,
        recording the refusal rather than performing the action."""


class TestCase13ProhibitedSelfApproval:
    def test_the_author_of_a_record_cannot_approve_it(self, ...): ...
    def test_not_even_with_an_explicit_unscoped_grant(self, ...): ...
```

Case 12 needs a consumer to test against. Use the existing outbox: write an event carrying `{permissionKey, membershipId, recordOwnerMembershipId}`, and add a small `AuthorizedConsumer` class in the test that calls `AuthorizationService.evaluate` before acting. This is a test-local adapter, not production code — P1.1e builds the real worker. Say so in the test module's docstring.

- [ ] **Step 2: Run the whole suite**

Run: `cd backend && uv run pytest -q`
Expected: every test passes, including the 115 from P1.1a.

- [ ] **Step 3: Update traceability**

In `docs/plan/traceability.md`, set each of AUTH-01..12, IAM-01, IAM-04 and APR-01 (policy side) to its honest status with the implementation location and the test that proves it. Specifically:
- **AUTH-03: partial** — record scope `team` is rejected pending P1.7 (R5).
- **AUTH-09: partial** — endpoints, field serialization and queued work are covered; exports, sockets and the Go/Flutter surfaces arrive with their own slices.
- **AUTH-10: partial** — revision, invalidation and queued recheck are covered; offline-client revalidation is P1.1e/FLT-03.
- Everything else that is fully covered: **implemented**.

Do not mark a row implemented because code exists — mark it from the test that proves it, and name that test.

- [ ] **Step 4: Update the docs**

- `CLAUDE.md`: add `grant-admin` to the command list, and add a short "Authorization" bullet to the architecture invariants pointing at `RequirePermission` as the only way to enforce.
- `README.md`: move the status line to P1.1b-1 complete, with the new test count.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "test(authz): prove all thirteen AUTH-12 cases through the API"
```

---

## Definition of done for this slice (§35)

- [ ] Migrations `t0005`–`t0007` apply cleanly and downgrade cleanly; `make migrate` upgrades an existing tenant without data loss.
- [ ] Real domain logic — no stubs. `recordScope: "team"` is **refused**, not faked (R5).
- [ ] API published and camelCase; OpenAPI regenerates without error.
- [ ] Authorization enforced on every route added here **and** on the pre-existing company endpoint.
- [ ] Every policy change writes both a `PermissionChangeAudit` row and an `AuditEvents` row, in the same transaction as the change.
- [ ] Concurrency: revision bumps serialise under `FOR UPDATE`; the cache cannot serve a stale decision.
- [ ] All 13 AUTH-12 cases pass through the API.
- [ ] `make lint` clean: ruff, format, import-linter including the new authz contract.
- [ ] `make test` green, P1.1a's 115 tests included.
- [ ] Traceability updated honestly, with `partial` where it is partial and the gap named.

## Known gaps this slice deliberately leaves open

| Gap | Why | Lands in |
|---|---|---|
| `recordScope: "team"` | No team or reporting-line model (R5) | P1.7 people |
| Real licensing in the feature tier | `FeatureGate` is module enablement for now (R6) | P1.1c |
| `warehouseId` composite FK | No warehouse table (R10) | P1.3 |
| Export and socket enforcement | No exports or sockets exist yet | Their own slices |
| Offline-client revalidation (AUTH-10) | No sync protocol yet | P1.1e / FLT-03 |
| Emergency support access (AUTH-08 last sentence) | Needs the break-glass procedure and `erp_readonly_support` | P1.1e (IAM-04) |
| Admin UI (AUTH-07 editor screens) | Owner decision 2026-09-23: API only | A later erp-web slice |
