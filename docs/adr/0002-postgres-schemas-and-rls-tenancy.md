# 0002 — PostgreSQL 18: database per tenant, central registry, RLS kept as defence in depth

**Status:** Accepted 2026-09-22 (owner chose "option B: a database per client on shared PostgreSQL servers") · **Requirements:** TEN-01..03, DB-01, DB-02, PLT-06, OPS-01, OPS-03

## Context
The spec's default is a shared SaaS database with row-level security (TEN-02, DB-01). The owner wants each client's business data physically separated, and asked for that to be the norm on SaaS as well. The spec allows dedicated databases "without changing business code". Some data belongs to no single tenant: a person can be staff in two companies, and tenant placement must be looked up before any tenant database can be chosen.

## Decision
- **Central registry database** (`erp_registry`, schema `registry`, one per deployment). It holds:
  - `tenants`: account number, status, and placement (`db_server`, `db_name`, `db_status`, `schema_revision`)
  - `identities`: issuer + subject
  - `memberships`: identity → tenant
  - later: `account_directory`, `tenant_domains`
- **One database per tenant** (`erp_t_<tenant uuid hex>`), created on shared PostgreSQL 18 servers. The registry records which server (`db_server`) so tenants can later be spread over several servers ("cells"). Schemas are per module (`platform`, `integration`, then `catalog`, `inventory`, …), and there is no schema per tenant.
- **Defence in depth inside each tenant database:**
  - Every tenant table keeps `tenant_id`, `UNIQUE (tenant_id, id)`, composite FKs, `FORCE ROW LEVEL SECURITY`, and the policy `tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid`.
  - A single-row `platform.tenant_scope` table stores the owning tenant, and every `tenant_id` column has a foreign key to it. A row belonging to another tenant cannot even be inserted into this database, even if a routing bug sends the wrong context.
- **Routing:** `TenantDatabaseRouter.for_tenant(tenant_id)` reads placement from the registry and caches one small connection pool per active tenant. It keeps an LRU of at most `max_cached` pools and disposes evicted ones. Requests resolve membership in the registry first, then open `tenant_session()` on the tenant's database.
- **Context** is still set with transaction-local `set_config(..., true)`. This works with PgBouncer transaction pooling, which the deployment profile adds in front of PostgreSQL to keep server connections bounded.
- **Roles** are cluster-wide:
  - `erp_owner`: `CREATEDB`; owns the registry and all tenant DBs; runs migrations and provisioning only
  - `erp_app`: runtime; `NOBYPASSRLS`; no DDL; no DELETE by default
  - `erp_relay`: outbox only
  - `CONNECT` on each tenant DB is revoked from PUBLIC and granted only to runtime roles
- **Provisioning and upgrades** run as an operator tool (`python -m erp.cli`), never inside the API:
  1. register the tenant with status `provisioning`
  2. `CREATE DATABASE`
  3. run the tenant Alembic tree
  4. seed `tenant_scope`
  5. mark `ready`

  Every step is idempotent. `upgrade-tenants` migrates each ready DB, records its revision or error, and continues past failures. A database that was migrated before and is now missing is **never silently re-created**; it must be restored from backup.
- **Two Alembic trees:** `migrations/registry` and `migrations/tenant`, selected with `alembic -n registry|tenant`. Tenant migrations must be expand/contract compatible, because during a rollout some tenant DBs run the new schema while others still run the old one.

## Consequences
- Per-tenant backup/restore and export are plain `pg_dump`/`pg_restore` of one database. Point-in-time recovery is still per server cluster, so restoring one tenant to a point in time means recovering to a side cluster and copying that database back. This is documented in the P1.9 runbook.
- Each release runs migrations N times. Operations monitor `schema_revision` drift and `last_migration_error` per tenant.
- Connection count scales with active tenants. This is managed by small per-tenant pools, the router LRU, and PgBouncer.
- Vendor-wide reporting cannot query one database. It uses per-tenant metrics exported to a central store.
- Cross-tenant joins are impossible by construction. Anything genuinely cross-tenant must live in the registry.
- **Hardening follow-up (P1.1e):** per-tenant login roles (`erp_t_<id>_app`) whose credentials live in the secret store, so a leaked credential opens only one tenant database. Until then, one `erp_app` credential can connect to every tenant DB. RLS and `tenant_scope` still bind each transaction to one tenant.
- A client-hosted install is the same layout: one registry DB plus its one (or few) tenant DBs.
