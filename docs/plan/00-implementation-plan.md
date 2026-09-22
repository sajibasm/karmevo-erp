# Karmevo ERP — Evidence-Based Implementation Plan

Status: **Draft for review** · Date: 2026-09-21 · Spec: `ERP_Coding_Agent_Requirements.md` v2.3
Responds to spec §1, §25, §35 and §38. Nothing here is implemented yet. After this plan is reviewed, the first detailed slice plan is `docs/superpowers/plans/2026-09-21-p1-1a-foundation-walking-skeleton.md`.

Companion documents:
- `docs/adr/` — draft architecture decision records (status *Proposed* until accepted).
- `docs/plan/traceability.md` — all 276 requirement IDs mapped to milestones (262 functional + 14 E2E gates).
- `docs/plan/module-dependencies.md` — proposed dependency graph for the 50 apps (not yet decided).

---

## 1. Evidence: repository gap assessment

| Item inspected | Finding |
|---|---|
| Source code, build files, tests, CI | **None.** The repository contains only the spec, `CLAUDE.md` and IDE metadata (`.idea/`). It is not yet a git repository. |
| Existing patterns to reuse | None. Every requirement is a gap, so there is nothing to preserve or migrate. |
| Local toolchain (developer machine) | Python 3.11.9, Docker 29.7 + Compose v5.5, Node 22, Go (installed), psql 18.6 client, Homebrew PostgreSQL 17 server. **Not installed:** `uv`, `pnpm`, Flutter. |
| External inputs the spec says must be supplied, not invented | Payment/bank/courier/SMS/signing providers; real bank statement formats; Bangladesh tax, payroll and invoice rules reviewed by qualified people; printer/scanner hardware; commercial licensing values; hosting/CI platform. **None supplied yet** (see §9 Blockers). |

Consequence: the plan starts with a walking skeleton. That means one deployable that proves tenancy, identity, the database role model, the error/decimal conventions and the outbox, all under test, before any business module is built.

## 2. Classification of scope

### 2.1 Confirmed (fixed by the spec; do not re-open)
- FastAPI ERP backend · Go website server/backend · Keycloak identity · Flutter/Dart Phase 2 app (§2, §39).
- SaaS + client-hosted from one codebase and the same images (§2, OPS-01).
- Bangladesh launch with configurable localization (LOC-01/02).
- Two major phases. Phase 1 is the full ERP/web scope, including all 50 catalogue apps "at the defined depth" (§22). Phase 2 is the shared Flutter app with staff + B2B buyer workspaces and B2B web-portal parity (§47).
- Approval workflow engine (§36), envelope signing (§37), licensing (§26), permission groups with overrides (§32), imports/landed costs (§33), split-source fulfilment (§27), returns/repairs (§28), expenses (§29), B2B portal (§40), payments (§41), manual bank reconciliation (§42), price lists (§43), loyalty (§44), messaging (§45). All are Phase 1.
- Account number + username/password sign-in, implemented as OIDC Authorization Code + PKCE (MOB-02/03).

### 2.2 Proposed defaults adopted by this plan (each has an ADR; accept or amend)
| Topic | Proposal | ADR |
|---|---|---|
| Deployment shape | Modular monolith (`erp-api`, `erp-worker`, `erp-scheduler`, `outbox-relay` from one image); separate `control-plane`, `storefront` (Go), Keycloak | 0001 |
| Repository | Monorepo: `backend/`, `frontend/`, `storefront/`, `mobile/` (Phase 2), `deploy/`, `docs/` | 0001 |
| Persistence | PostgreSQL **18** (native `uuidv7()`). **Database per tenant** on shared servers (owner decision 2026-09-22) + a central registry DB. Module schemas inside each tenant DB; `tenant_id` + RLS + `tenant_scope` FK kept as defence in depth | 0002 (Accepted) |
| DB access style | **Sync** SQLAlchemy 2 + psycopg 3 in both FastAPI (threadpool endpoints) and Celery, so domain code is shared without async/sync duplication | 0003 |
| Identity layout | Per deployment, shared by all its tenants: realm `staff` + realm `customers`. Per-tenant Keycloak *clients* for redirect URIs and branding only; ERP memberships decide tenant access | 0004 (Accepted; shopper-account sharing still open) |
| Jobs | Celery + RabbitMQ (quorum queues, publisher confirms), PostgreSQL job table authoritative, transactional outbox + inbox dedup | 0005 |
| API conventions | `/api/v1`, RFC 9457 problem+json with stable `code`, cursor pagination, decimals as strings, `Idempotency-Key`, `ETag`/`If-Match` versioning | 0006 |
| Licence grants | Compact JWS, EdDSA (Ed25519), `kid`-pinned trust bundle, algorithm allowlist | 0007 |
| Web UIs | React + TypeScript (Vite) for `erp-web`, `pos-web` (offline PWA) and `sign-web` (external signer). **Website: Go server-rendered HTML (html/template + htmx) for storefront and B2B portal.** Open decision in §23; this is the recommendation. | 0008 |
| Tooling | `uv` (Python), `ruff`, `pytest`; `pnpm` workspaces; `import-linter` contracts to enforce module boundaries | 0001 |
| Module system | Every catalogue app is a module package (`module.py` manifest, `config.py`, `models.py`, `schemas.py`, `api.py`, `service.py`, `interface.py`, `utils.py`) with declared `depends_on`; `erp/shared` for cross-module building blocks; per-tenant enable/disable in the registry, enforced on every route; disabling never deletes data | 0009 |
| Inventory valuation | FIFO cost layers first (matches IMP-06 lineage), moving average as second method. **Requires accounting review before P1.3 posting.** | recorded in §9 |

### 2.3 Unresolved decisions (tracked; blocking only where noted)
| Decision (spec §23 and findings) | Blocks | Proposed handling |
|---|---|---|
| Product name ("Karmevo" assumed from the folder name) | Branding only | Use "Karmevo" as a working name |
| Dependency graph and core/optional classification for all 50 apps (e.g. Sales → Inventory) | Enabling rules per app | Proposal + open decisions D1–D8 in `docs/plan/module-dependencies.md`; mechanism in P1.1a (ADR-0009) |
| Pilot industry and first-release depth | Ordering inside P1.3–P1.5 | Default order: wholesale/imports → retail POS → manufacturing → restaurant |
| Website rendering | P1.6 | ADR-0008 recommendation |
| Shared `customers` realm: may one shopper account span several merchants' stores? | P1.6 sign-up | ADR-0004 open sub-decision |
| Account-directory governance, restricted-host enrollment trust | P1.1e | Propose in P1.1e plan |
| Staff app on tenant subdomain (`customer1.erp.com`) vs single `app.erp.com` | P1.1b tenant domains | Recommendation: subdomains for storefront/portal; decide for staff app |
| Disconnected client hosting | P1.9 | Out of scope until decided; internet-connected assumed (§2) |
| Depth of each of the 50 catalogue apps | P1.8 exit | Needs a signed-off "minimum scope" sheet per app (§17 table is a starting point). Tension: §17 says "not a promise to ship them all in the first release"; §22 says all 50 are Phase 1 scope |
| Valuation method, recoverable-tax treatment, payroll statutory rules, invoice formats | P1.2/P1.3/P1.7 posting | Qualified accounting/tax review; golden examples supplied by the owner |
| Providers (payments, banks, courier, SMS, e-mail, signing, tax) | Each adapter | Owner supplies shortlist and sandbox credentials; adapters built against a capability interface first |
| Numeric targets: load, RPO/RTO, retention, API compatibility window | P1.9 sign-off | Owner decision; measurement harness built earlier |
| CI/git hosting platform | CI config in P1.1 | `make` targets now; CI YAML once host is known |

## 3. Target architecture

```
                         ┌──────────────────── vendor only ────────────────────┐
                         │ control-plane (FastAPI) ── control-plane DB          │
                         │ plans · subscriptions · deployments · grant signing  │
                         └───────────────▲──────────────────────────────────────┘
                                         │ signed grants (refresh / file import)
 browsers ─ erp-web / pos-web / sign-web │
            (React SPA, PKCE)            │
 buyers/shoppers ─ storefront (Go SSR) ──┼──► erp-api (FastAPI, /api/v1) ──► PgBouncer ─► PostgreSQL 18 servers
 Phase 2 ─ Flutter app (PKCE) ───────────┘        │  1. registry DB: tenants,     ├─ erp_registry
                                                  │     placement, memberships    ├─ erp_t_<tenant A>
                                                  │  2. router → tenant's own DB  └─ erp_t_<tenant B> …
                                                  │ outbox rows (same txn, in the tenant DB)
             Keycloak (own DB) ◄── OIDC ──────────┤
                                                  ▼
                                   outbox-relay ─► RabbitMQ ─► erp-worker (Celery)
                                                              erp-scheduler (single beat)
                                   Redis (cache, tenant+revision keyed) · S3-compatible storage
```

Key rules (see `CLAUDE.md` for the full list): the ERP is the only authority for business rules. The Go storefront and Flutter call ERP APIs and never write ERP tables. Every business change is one DB transaction, and external follow-up goes through the outbox. Each request first resolves membership in the registry DB, then the router opens a transaction on that tenant's own database. Inside it, tenant context is still set with `set_config('app.tenant_id', …, true)` and enforced by `FORCE ROW LEVEL SECURITY` plus a `tenant_scope` foreign key, so data can never be written into the wrong tenant's database.

### 3.1 Database role model (TEN-02 "bypass protections")
| Role | Used by | Privileges |
|---|---|---|
| `erp_owner` | Migrations and tenant provisioning (`python -m erp.cli`) only | `CREATEDB`; owns the registry and every tenant DB. Never used by running services. |
| `erp_app` | erp-api, erp-worker | `NOSUPERUSER NOBYPASSRLS`; SELECT/INSERT/UPDATE per table; DELETE granted only on explicitly deletable tables (drafts, carts). No DDL. `CONNECT` on the registry and each tenant DB (PUBLIC revoked). Per-tenant login roles are a P1.1e hardening item. |
| `erp_relay` | outbox-relay | Only `integration.outbox_events`, via a policy scoped `TO erp_relay`, so it can read across tenants without BYPASSRLS. |
| `erp_readonly_support` | Audited support access (IAM-04) | Later; time-boxed grants through a break-glass procedure |

Within a tenant DB, missing tenant context results in `nullif(current_setting('app.tenant_id', true), '')::uuid` being NULL, so zero rows come back. Composite foreign keys `(tenant_id, x_id)` make it impossible to reference another tenant's row. RI checks bypass RLS, so this is the guard.

## 4. Module boundaries (ARC-01, DB-01)

Each module lives at `backend/src/erp/modules/<name>/` with the standard layout from ADR-0009: `module.py` (manifest + `depends_on`), `config.py`, `models.py`, `schemas.py`, `api.py` (controllers), `service.py`, `interface.py`, `utils.py`. It owns its tables in its own schema. Other modules may import only `erp.modules.<other>.interface`, and `import-linter` enforces this in CI. Cross-module building blocks (money, units, pagination) live in `erp/shared`, and framework infrastructure in `erp/core`. Tenants enable or disable non-core modules individually, and every route of a disabled module returns `MODULE_DISABLED`. The table below is the internal module map; the 50 catalogue apps map onto it, and their exact dependency graph is an open owner decision.

| Module (schema) | Owns (initial aggregates) | Depends on (interfaces) | First milestone |
|---|---|---|---|
| `platform` | tenants, companies, branches, departments, identities, memberships, account directory, audit events, numbering, config versions, custom fields, calendars, fiscal periods | — | P1.1 |
| `authz` (platform schema) | permission definitions, groups, group policies, memberships, user overrides, authorization revisions, change audit | platform, licensing | P1.1 |
| `licensing` (runtime; `platform` schema tables) | verified grants, entitlement snapshots, quota allocations/usage, trust store | platform | P1.1 |
| `workflow` | definitions, versions, stages/clauses, requests, tasks, decisions, events, timers, action executions | platform, authz | P1.1 |
| `integration` | outbox, inbox dedup, job runs, webhook receipts, provider credentials references, feed cursors, sync operations, device registrations | platform | P1.1 |
| `catalog` | products, variants, units/conversions, packaging, identifiers, categories, price lists/rules, offers | platform, tax | P1.2 |
| `tax` | jurisdictions, registrations, tax types/rates, rule versions, tax snapshots | platform | P1.2 |
| `finance` | chart of accounts, journals, entries/lines, fiscal periods (locks), receivables/payables allocations, bank accounts, statement imports, canonical bank txns, reconciliation, payments (intent/attempt/txn/settlement), exchange rates, assets, budgets | platform, tax, workflow | P1.2 |
| `inventory` | warehouses, locations, batches, serials, stock movements (ledger), balances (projection), reservations, transfers, count sessions/lines, adjustments, cost layers, label templates/prints | catalog, finance, workflow | P1.3 |
| `purchasing` | requisitions, RFQs, supplier offers, POs, receipts, supplier bills, returns, import shipments, import charges, landed-cost batches/allocations | catalog, inventory, finance, tax, workflow | P1.3 |
| `sales` | leads/opportunities, quotations, sales orders, fulfilment allocations, shipments/revisions, pick tasks, loading scans, release events, invoices, credit notes, POS sessions/orders, RMAs, warranty, repair orders, custody movements, subscriptions/rentals | catalog, inventory, finance, tax, workflow | P1.4 |
| `manufacturing` | BOM/versions/lines, routings, work centres, production orders, consumption, output, PLM changes, quality checks, maintenance equipment/requests | catalog, inventory, finance, workflow | P1.5 |
| `restaurant` | menus, menu items, recipe versions, modifiers, floor plans, tables, kitchen stations, tickets, preparation events, waste records | catalog, inventory, sales | P1.5 |
| `commerce` | storefronts, domains, publications, pages/blocks, carts, customer accounts (B2C), buyer organizations/memberships (B2B), transfer claims, loyalty programs/ledger | catalog, sales, finance, authz | P1.6 |
| `people` | employees, contract versions, shifts, attendance events, leave, payroll runs/input snapshots/payslips, recruitment, appraisals, referrals, fleet, expense claims/lines/allocations, advances | platform, finance, workflow | P1.7 |
| `documents` | folders, files, versions, retention, signing templates/versions, envelopes, recipients, fields/values, sessions, acceptances, envelope events, provider txns, completed artifacts | platform, workflow, integration | P1.7 |
| `messaging` (integration schema) | templates/versions, preferences/consent, suppression, sends, delivery logs, campaigns | platform, integration | P1.4 / P1.8 |
| `service` | projects, tasks, timesheets, field service, helpdesk, planning, appointments | platform, sales, people | P1.8 |
| `extensions` | marketing automation, events, surveys, discuss, knowledge, spreadsheets, ESG, IoT, VoIP, AI, Studio metadata | per app | P1.8 |

`control_plane` is a separate FastAPI application (`backend/src/control_plane/`) with its own database (DB-01, §26). It shares only `erp.shared.grants` (the pure grant verification library), never ERP models.

## 5. Initial data model (P1.1–P1.2)

Names in this section are *logical*. Physical names follow ADR-0010 (e.g. `platform.companies` → `platform."Companies"`, `id` → `"companyId"`), and the code structure follows ADR-0011.

Conventions for every tenant-owned table:
- `tenant_id uuid not null` + `id uuid default uuidv7()`, `unique (tenant_id, id)`, composite FKs, `FORCE ROW LEVEL SECURITY`
- `created_at timestamptz`, `version int` for optimistic concurrency
- money is `numeric(20,6)` paired with `currency char(3)`; quantities are `numeric(20,6)` paired with a `unit_id`
- no hard delete on financial or stock tables (DELETE is not granted)

```
-- Registry DB (erp_registry, one per deployment) ---------------------------------------------
registry.tenants(id, account_number UNIQUE, display_name, status, db_server, db_name UNIQUE,
                 db_status[provisioning|ready|failed], schema_revision, last_migration_error)
registry.identities(id, issuer, subject, UNIQUE(issuer, subject))
registry.memberships(tenant_id→tenants, id, identity_id→identities, kind[staff|buyer|service], status)
    policies: tenant match (ALL) OR identity match (SELECT only, for context selection)
registry.account_directory(…), registry.tenant_domains(…)                                  -- P1.1b/e
-- Each tenant DB (erp_t_<tenant>) --------------------------------------------------------------
platform.tenant_scope(singleton PK, tenant_id UNIQUE)   -- one row; every tenant_id FKs to it
platform.companies(tenant_id, id, name, country_code, base_currency, timezone)
platform.branches(tenant_id, id, company_id→(tenant_id,companies.id), code UNIQUE per company)
platform.audit_events(tenant_id, id, occurred_at, actor_identity_id, action, target_type, target_id,
                      outcome, reason, details jsonb)                                       -- INSERT/SELECT only
platform.permission_definitions(key PK, resource, action, sensitivity, requires_feature)
platform.permission_groups(tenant_id, id, name, is_template, protected)
platform.group_policies(tenant_id, id, group_id, permission_key, effect[allow|deny], company_id?, branch_id?,
                        warehouse_id?, record_scope[own|team|all], conditions jsonb (typed tree),
                        limit_amount?, limit_currency?, valid_from, valid_to)
platform.user_group_memberships(tenant_id, membership_id, group_id, valid_from, valid_to)
platform.user_permission_overrides(tenant_id, id, membership_id, … same policy columns …, reason, granted_by)
platform.authorization_revisions(tenant_id, revision bigint, changed_at, changed_by)
platform.license_grants_runtime(tenant_id, grant_id, revision, kid, payload jsonb, artifact_sha256, accepted_at)
platform.entitlement_snapshots(tenant_id, grant_revision, features jsonb, limits jsonb, policy_version)
platform.quota_usage(tenant_id, feature_key, scope_key, used, UNIQUE(tenant_id, feature_key, scope_key))
integration.outbox_events(tenant_id, id, topic, payload jsonb, occurred_at, dispatched_at, attempts, last_error)
integration.inbox_dedup(tenant_id, consumer, event_id, processed_at, PK(consumer, event_id))
integration.job_runs(tenant_id, id, kind, operation_id UNIQUE per tenant, actor, status, progress, attempts,
                     config_version, result jsonb, error)
platform.idempotency_keys(tenant_id, actor_identity_id, key, request_sha256, response_status, response_body,
                          PK(tenant_id, actor_identity_id, key))
workflow.* per spec §36 table list; finance.journal_entries/lines with CHECK balanced per entry via
deferred constraint trigger; tax.tax_rule_versions immutable once published; catalog.* per §20.
```

Full ERDs for workflow and envelopes (§38 item 1) are scheduled as the first task of their slices, not written ahead of time.

## 6. API boundaries and conventions (ARC-06)

- Base path `/api/v1`. The OpenAPI document is generated by FastAPI and committed as `backend/openapi/v1.json`. A CI diff check flags breaking changes. The TypeScript client is generated into `frontend/packages/api-client`.
- Errors use `application/problem+json`: `{type, title, status, code, detail, errors?}`. `code` is stable, e.g. `UNAUTHENTICATED`, `TENANT_ACCESS_DENIED`, `TENANT_SELECTION_REQUIRED`, `PERMISSION_DENIED`, `FEATURE_NOT_LICENSED`, `QUOTA_EXCEEDED`, `LICENSE_RESTRICTED`, `VERSION_CONFLICT`, `IDEMPOTENCY_KEY_REUSED`, `STALE_APPROVAL`.
- Tenant selection: the `X-Tenant-Id` header is a *selection* validated against verified membership, never trusted on its own. Company/branch selection is validated by `authz` in the same way.
- Decimals are sent as JSON strings, and floats are rejected. Timestamps are RFC 3339 UTC. Currency is ISO 4217.
- Pagination uses opaque `cursor` + `limit` (max 200), filters are `filter[field]=`, sorting is `sort=-created_at`.
- Mutations accept an `Idempotency-Key`. Updates require `If-Match: "<version>"`, and a mismatch returns 409 `VERSION_CONFLICT`.
- Logical route groups: `/me`, `/capabilities`, `/license/status`, `/authz/*`, `/workflows/{definitions,requests,tasks,inbox}`, `/catalog/*`, `/tax/*`, `/finance/*`, `/inventory/*`, `/purchasing/*`, `/sales/*`, `/pos/*`, `/manufacturing/*`, `/restaurant/*`, `/people/*`, `/documents/*`, `/sign/*` (external signer, separate router, no staff auth), `/portal/*` (buyer-scoped), `/sync/{push,pull}`, `/devices/*`. The public account directory is `GET /directory/v1/accounts/{account_number}`, rate-limited, returning minimal metadata only.

## 7. Two-phase backlog with dependencies

Arrows mean "must be usable before". Milestones overlap where the arrows allow.

```
P1.1a skeleton ─► P1.1b authz ─► P1.1c licensing runtime ─► P1.1d workflow engine ─► P1.1e jobs/Celery+directory
        │                                   │                        │
        └──────────────► P1.2 shared business foundation (catalog, tax, finance, pricing, payment model)
                                              │
               ┌──────────────────────────────┼───────────────────────────┐
               ▼                              ▼                           ▼
         P1.3 procurement/warehouse ─► P1.4 sales/fulfilment/POS ─► P1.5 manufacturing & restaurant
               │                              │
               └──────────────► P1.6 web commerce + B2B portal (needs P1.4 orders/payments)
         P1.7 people & documents (needs P1.1d workflow, P1.2 finance)       P1.8 remaining catalogue
                                              └──────────────► P1.9 readiness & release gate ─► Phase 2
```

### Phase 1
| Slice | Scope (requirement IDs) | Exit evidence | Depends on |
|---|---|---|---|
| **P1.1a Walking skeleton** (detailed plan written) | Monorepo, FastAPI app, DB roles, registry DB, **per-tenant DB provisioning, upgrade runner and router**, RLS + `tenant_scope` defence in depth, JWT verification, tenant-context selection, problem+json, decimal conventions, audit primitive, per-tenant outbox + relay, **module system (manifests, dependency graph, per-tenant enable/disable)**, `erp/shared`, dev compose incl. Keycloak, `erp.cli`. PLT-05 (module dependencies), ARC-03/06, TEN-01..03, IAM-02, IAM-04 (primitive), DB-01/02, JOB-04 (outbox), PLT-06 | Each tenant routed to its own DB; wrong-tenant rows rejected; idempotent provisioning; upgrade continues past a broken tenant; token rejection; outbox redelivery (seed of E2E-01, E2E-12) | — |
| P1.1b Permission engine + tenant domains | AUTH-01..12, IAM-01/04, APR-01 (policy side). Group/override editor API + admin UI shell in `erp-web`. `registry.tenant_domains`, host → tenant middleware, reserved slugs, per-tenant Keycloak client provisioning | All 13 AUTH-12 cases via API; deny precedence; disjoint-branch-limit case; delegation limits | 1a |
| P1.1c Licensing | LIC-01..08, LIC-10..14 runtime + `control_plane` plan/version/subscription/grant issuance with test-only keys; `/capabilities`, `/license/status` | §26 required tests list (forged/expired/wrong-tenant/wrong-deployment/unknown key, rotation, concurrent seat quota, vendor outage) | 1a, 1b |
| P1.1d Workflow engine | WFL-01..19 engine, typed condition tree, test domain adapter; §38 design package items 1–3, 5, 6 | §36 acceptance scenarios against the test adapter | 1b, 1c |
| P1.1e Jobs & mobile-ready contracts | JOB-01..05 (Celery, RabbitMQ, single scheduler, job runs), MOB-04 directory, FLT-02/03 sync contract draft, OPS-01/02/04 skeleton, CI, PgBouncer, per-tenant DB login roles, relay sharding across workers | Worker crash/redelivery test (E2E-12), directory rate-limit + minimal-metadata test | 1a |
| P1.2 Shared foundation | PLT-01..06, TAX-01..04, FIN-01/02 (CoA, journals, periods), PRC-01..05, PMT-04/05 model, LOC-01/02 Bangladesh package v0 | Decimal/rounding golden cases, balanced-journal constraint, versioned tax examples (E2E-06 subset), price precedence examples | 1a–1d |
| **First business vertical slice** (§38) | Draft invoice → workflow policy selection → 2-salespeople-OR-manager quorum → protected post to journal | §36 invoice scenarios end-to-end with real invoice + journal; protected-field invalidation | 1d, P1.2 |
| P1.3 Procurement & warehouse | PUR-01/02, INV-01..09, BAR-01..05, IMP-01..09, DEV-01..03 (web/USB), label printing | Import-to-bin valuation (IMP-09 fixture), 40+60 bin aggregation, concurrent reservation (E2E-03), count replay (E2E-04) | P1.2 |
| P1.4 Sales & fulfilment | SAL-01, WHO-01, POS-01..05 (web POS offline PWA), FUL-01..08, RPR-01..06, PMT-01..08, BNK-01..11, MSG-01..04/06 transactional | §27 acceptance (one invoice across sources), serial return/repair, bank reimport cases (§42), E2E-07 web POS, E2E-08 | P1.3 |
| P1.5 Industry operations | MFG-01..05, RES-01..06, **OWN-01 restaurant self-service (kiosk `kiosk-web`, QR table ordering)** | E2E-02 (bins→production→POS), E2E-05 burger fixture | P1.3, P1.4 |
| P1.6 Web commerce | WEB-01..04, WHO-02, B2B-01..07, DB-03, storefront (Go) + B2B portal | Tenant-domain isolation, payment replay (E2E-08), wholesale price tamper test, buyer isolation (§46 gates) | P1.4 |
| P1.7 People & documents | HR-01/02, ATT-01, PAY-01/02, EXP-01..05, DOC-01, SIG-01..03, ENV-01..20 | E2E-09, E2E-10, §37 test list, expense acceptance | 1d, P1.2 |
| P1.8 Remaining catalogue | SAL-02, WEB-05, EXT-01..05, LOY-01..06, MSG-05, and the remaining §17 apps at agreed depth | Per-app functional UI/API + authz + integration evidence; §46 loyalty/marketing gates | P1.4, P1.6, P1.7 |
| P1.9 Readiness | OPS-03/05/07, LOC validation, both hosting profiles, backup/restore, upgrade, MOB-05/09 contracts | E2E-13, E2E-14, full traceability review, UAT | all |

### Phase 2 (starts only after the Phase 1 exit gate, §35)
| Slice | Scope | Exit evidence |
|---|---|---|
| P2.1 App foundation | MOB-01..06, FLT-01, BMA-01/02 | E2E-11: one build, two SaaS accounts + one private deployment, no leakage |
| P2.2 Business workflows + B2B workspace | MOB-07, BMA-03..07 | Role scenarios + buyer parity matrix |
| P2.3 Warehouse devices | DEV-01..03 native, FLT-05 | Handheld compatibility matrix |
| P2.4 Offline sync | MOB-08, FLT-03/04 | Interrupted sync, account switching, revoked access |
| P2.5 Release | MOB-09, FLT-06/07 | Real-device UAT, signed builds, authorized store publication |

## 8. First vertical-slice plan

§38 asks for "draft invoice → policy selection → quorum → protected post" as the first vertical slice. That slice needs tenancy, authorization, licensing, the workflow engine and a minimal finance/tax core underneath it. Building those first as thin layers is the dependency-honest ordering.

1. **P1.1a Walking skeleton.** Detailed TDD plan: `docs/superpowers/plans/2026-09-21-p1-1a-foundation-walking-skeleton.md` (9 tasks).
2. P1.1b → P1.1d, each getting its own detailed plan written when the previous one is merged, so plans reflect real code.
3. A minimal P1.2 subset: company CoA, journals with a balanced-entry constraint, one tax rule version, and invoice drafts with frozen tax snapshots.
4. The invoice approval slice itself, then extend the same engine to expenses, stock adjustments, payroll and dispatch.

## 9. Blockers, risks and escalations

**Escalate (these change auth, scope, data ownership or compliance):**
1. ADR-0004 realm layout (staff vs customer realms per deployment), which affects the mobile sign-in UX.
2. The depth sheet for all 50 catalogue apps (the §17 vs §22 tension).
3. Inventory valuation method(s) and recoverable-tax treatment for imports.
4. Whether the web POS must work offline with card payments. The spec says no by default (POS-04); confirm.

**Blocked pending external input (record as blocked, not as done):** payment/bank/courier/SMS/signing/tax providers and sandbox credentials; real bank statement samples; Bangladesh VAT/payroll rules and golden examples reviewed by qualified people; printer/scanner models; commercial plan values; CI host.

**Top technical risks:**
| Risk | Mitigation |
|---|---|
| Request routed to the wrong tenant DB | Membership resolved in the registry before routing. Inside each DB: RLS + `tenant_scope` FK reject foreign rows. Tests cover both. |
| Migration fan-out across N tenant DBs | Upgrade runner records per-tenant revision/error and continues past failures. Expand/contract migrations. Drift alert on `schema_revision`. |
| Connection exhaustion with many tenant DBs | Small per-tenant pools, router LRU, PgBouncer transaction pooling (compatible with transaction-local context) |
| Lost tenant DB silently re-created empty | Provisioner refuses to re-create a DB that was ever migrated; restore from backup |
| Scope sprawl (50 apps) diluting core correctness | Depth sheet, and each slice carries its own E2E gate |
| Stock/finance double effects under retries | Ledger + projection, unique operation IDs, inbox dedup, `SELECT … FOR UPDATE` on balances, concurrency tests in every slice |
| Offline POS/mobile conflicts | Stable operation IDs, server-wins canonical IDs, visible conflict states (FLT-03), no last-write-wins on stock/money |
| Keycloak version drift | Pin the image tag in `deploy/.env`, and test token claims (issuer/audience mapper) in CI with a live Keycloak |

## 10. Definition of done per slice
As in `CLAUDE.md` §"Definition of done". In addition, each slice updates `docs/plan/traceability.md` rows (implementation path + test names + status) and ships a short slice report: implemented / verified / partial / blocked / deferred, the test command output, and the remaining risks.
