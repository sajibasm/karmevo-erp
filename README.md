# Karmevo ERP

A multi-tenant ERP platform: a modular monolith of 50 enable/disable business
apps, built as a Python **FastAPI** backend on **PostgreSQL 18**, with
**Keycloak** for identity. Each tenant gets its own database; a central
registry database records tenants, identities and memberships.

The full product specification is
[`ERP_Coding_Agent_Requirements.md`](ERP_Coding_Agent_Requirements.md) (v2.3).
Delivery is split into **Phase 1** (the whole ERP, admin, licensing, website /
eCommerce, web POS, warehouse and mobile-ready API contracts) and **Phase 2**
(one shared Flutter app for staff and B2B buyers).

**Status:** milestone P1.1a (foundation walking skeleton) is complete and on
`main` — tenant provisioning, per-tenant databases with RLS, Keycloak token
verification, the module system, the transactional outbox and a health API,
covered by 115 tests. P1.1b (permission engine, tenant domains, module-admin
API) is next.

## Getting started

Prerequisites: **Docker**, **uv** (`brew install uv`), Python 3.13 (uv
installs it), and `make`.

```bash
cp deploy/.env.example deploy/.env    # then pin KEYCLOAK_VERSION (never "latest")

make dev-up                           # Postgres 18 on :55432, Keycloak on :8180
make migrate                          # registry migrations, then every tenant DB
make provision-demo                   # creates tenant "Demo Traders" and its database
make api                              # API on http://localhost:8010
```

Check `http://localhost:8010/healthz`, `/readyz` and `/docs`. Override the port
with `make api API_PORT=8020`.

## Commands

| Command | What it does |
|---|---|
| `make dev-up` / `make dev-down` | Start / stop the Postgres + Keycloak dev containers |
| `make migrate` | `alembic -n registry upgrade head`, then `erp.cli upgrade-tenants` |
| `make provision-demo` | Provision a demo tenant and its own database |
| `make test` | Full backend suite (needs `make dev-up`) |
| `make lint` | ruff check + ruff format check + import-linter contracts |
| `make api` | Run the API with reload |

Single test:

```bash
cd backend && uv run pytest tests/platform/test_tenant_isolation.py -v
```

Tenant administration:

```bash
cd backend
uv run python -m erp.cli provision-tenant --account-number 100002 --name "Acme Ltd"
uv run python -m erp.cli enable-module --tenant <uuid> --module sales --with-dependencies
uv run python -m erp.cli disable-module --tenant <uuid> --module sales
uv run python -m erp.cli upgrade-tenants
```

## Architecture

- **Modular monolith, monorepo** (ADR-0001). Every catalogue app is a package
  under `backend/src/erp/modules/<key>/` with its own `module.py` manifest,
  `config.py`, `models.py`, `schemas.py`, `controller.py`, `service.py`,
  `repository.py` and `interface.py`. Modules talk to each other only through
  `interface.py`. Tenants enable or disable non-core modules; disabling never
  deletes data.
- **Database per tenant** (ADR-0002, accepted). A registry database
  (`erp_registry`) holds tenants, placement, identities and memberships; each
  tenant lives in its own `erp_t_<uuid hex>` database with row-level security,
  `FORCE ROW LEVEL SECURITY` and a transaction-local `app.tenant_id`.
- **Identity** (ADR-0004, accepted). One Keycloak per deployment with two
  realms shared by all tenants: `staff` and `customers`. Per-tenant Keycloak
  *clients* exist only for redirect URIs and branding — they never partition
  users. Tenant membership is resolved in the registry, never from a header.
- **Transactional outbox** (ADR-0005). Business changes and their follow-up
  events commit in one transaction; consumers are idempotent.
- **ERP is the authority** — pricing, tax, stock, orders, payroll and
  accounting live only here. Other surfaces call the API.

Architecture decisions are recorded in [`docs/adr/`](docs/adr/).

## Conventions

- **Python:** PEP 8, enforced by ruff (`E,W,N,F,I,B,UP`), 99-character lines.
- **Database:** CamelCase (ADR-0010) — plural PascalCase tables (`"SalesOrders"`),
  camelCase columns (`"orderStatus"`), spelled-out ids (`"salesOrderId"`, never
  `id`), FK columns named after the column they reference. Always double-quote
  identifiers in raw SQL: `select "tenantName" from registry."Tenants";`
- **API JSON:** camelCase (ADR-0010). Models inherit
  `erp.shared.schemas.ApiSchema`; Python fields stay snake_case.
- **Class-based** (ADR-0011). No module-level functions in `erp/`; the layering
  is Controller → Service → Repository → Model, with constructor injection.
- Errors are RFC 9457 `application/problem+json` with a stable `code`.

## Repository layout

```
backend/            FastAPI application
  src/erp/core/       framework infrastructure (db, config, security, modules)
  src/erp/shared/     cross-module building blocks (Money, ApiSchema)
  src/erp/modules/    business modules (platform, integration, …)
  migrations/         Alembic trees: registry/ and tenant/
  tests/              pytest suite
deploy/             dev compose file, Postgres init SQL, Keycloak realms
docs/adr/           architecture decision records
docs/plan/          implementation plan, traceability matrix, module dependencies
docs/superpowers/   detailed per-milestone implementation plans
```

## Documentation

- [Implementation plan](docs/plan/00-implementation-plan.md) — milestones,
  module boundaries, data model, API conventions, phase backlog
- [Traceability matrix](docs/plan/traceability.md) — every requirement ID →
  milestone → implementation → test evidence → status
- [Module dependencies](docs/plan/module-dependencies.md) — the 50-app
  dependency graph (a proposal; open decisions D1–D8)
- [ADR index](docs/adr/README.md)
- [CLAUDE.md](CLAUDE.md) — working agreements and architecture invariants
