# 0009 — Module system: independent apps, declared dependencies, per-tenant enablement

**Status:** Proposed 2026-09-22 (owner requirement: "all 50 apps module-based and independent, enable/disable, some with dependencies, each module with its own config, model, controller, service, utils, plus a shared module") · **Requirements:** ARC-01, PLT-05, LIC-03/13, §17 catalogue

## Context
The spec requires module-owned tables and rules (ARC-01). It also says "module dependencies and entitlements must be enforced server-side. Disabling a module preserves historical data" (PLT-05). The owner wants every catalogue app to be an independently switchable module. Some apps depend on others (e.g. Sales needs Inventory); the concrete dependency graph for the 50 apps is a **separate decision**.

## Decision

### Package layout (one per app, `backend/src/erp/modules/<key>/`)
```
module.py      manifest: key, name, depends_on, core flag, routers (and later permissions, features, jobs)
config.py      the module's per-tenant settings as a pydantic model (defaults + validation)
models.py      SQLAlchemy tables (TenantBase), in the module's own schema
schemas.py     API request/response DTOs
controller.py  Controller classes owning FastAPI routers (thin: parse, authorize, call service)
service.py     Service classes: business rules and transactions (split into service/ when it grows)
repository.py  Repository classes: all queries for the module's aggregates (ADR-0011)
interface.py   the ONLY import surface for other modules (functions + DTOs)
utils.py       module-private helpers
tasks.py       Celery tasks (when needed)
```
Tests live in `backend/tests/modules/<key>/`. Migrations stay in `migrations/tenant/versions/`, named `t####_<module>_<change>.py`. Moving to per-module Alembic branches is revisited if the linear history becomes a bottleneck.

### Layers outside modules
- `erp/core`: framework infrastructure. Database/session handling, security, errors, the module system itself, RLS helpers. It never imports `erp.shared` or `erp.modules`.
- `erp/shared`: the "shared module". Cross-module building blocks with no business ownership: money/decimal types, units of measure, pagination, value objects, numbering helpers. It never imports `erp.modules`.
- Modules import each other only through `erp.modules.<other>.interface`. This is enforced by import-linter; the contract is added once the first business module exists.

### Manifests, catalog and enablement
- Each module's `module.py` declares `MODULE = ModuleManifest(key, name, depends_on, core, controllers)`. `InstalledModules` in `erp/module_catalog.py` lists the installed modules.
- `ModuleCatalog` validates the graph at startup: no duplicate keys, no unknown dependencies, no cycles, and core modules depend only on core modules. It provides enable order, transitive dependencies and dependents.
- **Core modules** (`platform`, `integration`, later `authz`, `licensing`, `workflow`, `documents` storage) are always on and cannot be disabled.
- **Per-tenant state** lives in `registry."TenantModules"("tenantId", "moduleKey", "isEnabled", "changedAt")`:
  - Enabling a module whose dependencies are off is rejected, unless the caller explicitly asks to enable the dependencies too.
  - Disabling a module that an enabled module depends on is rejected.
  - Changes are serialised per tenant with a row lock.
- **Enforcement:** `ApplicationFactory` attaches `ModuleGuard(key)` to every controller router of a non-core module, so a disabled module returns 403 `MODULE_DISABLED` on every endpoint, including direct API calls. Workers, exports and event consumers call `TenantModules.require()` the same way (P1.1e).
- **Disabling never deletes data.** Every installed module's tables exist in every tenant database whether or not the tenant enabled it, so re-enabling is instant and history survives.
- **Relation to licensing (§26):** a module can be enabled only if the tenant's licence grants its feature key (P1.1c adds this check). A licence downgrade never deletes data; it restricts new creation according to the LIC-11/12 policy. Enablement (the tenant's choice) and entitlement (what they paid for) are separate checks, and both must pass.
- **Per-tenant module settings** (`config.py` models) are stored in the tenant database in `platform."ModuleSettings"("moduleKey", "moduleSettings" jsonb, "settingsVersion")`, validated by the module's pydantic model. This is added with the first business module.

## Consequences
- Each app can be developed, tested and switched on or off independently. Cross-module coupling is visible in `depends_on` and `interface.py` imports.
- A module's optional integration with another module (e.g. Sales showing Inventory stock *if* Inventory is on) must check `enabled()` at runtime and degrade gracefully. That is distinct from a hard `depends_on`.
- Dependency changes between releases need care. Adding a hard dependency to an already-enabled module requires a data migration that enables the dependency for affected tenants.
- **Open (owner, separate discussion):** the dependency graph and the core/optional classification for all 50 catalogue apps. The working proposal and open decisions D1–D8 are in `docs/plan/module-dependencies.md`. It also needs three extensions to this ADR (`requires_any`, `integrates_with`, feature-level requirements), to be added once the graph is agreed.
