# Architecture Decision Records

Format: Context · Decision · Consequences · Status. Status starts at **Proposed**. An ADR becomes **Accepted** only after owner review. ADRs flagged *Escalation* change authentication, scope, data ownership or compliance, and need explicit sign-off (spec §1).

| ADR | Title | Status |
|---|---|---|
| 0001 | Modular monolith and monorepo layout | Proposed |
| 0002 | PostgreSQL 18: database per tenant, central registry, RLS as defence in depth | **Accepted** 2026-09-22 |
| 0003 | Synchronous SQLAlchemy shared by API and workers | Proposed |
| 0004 | Keycloak realm and client layout (two shared realms, per-tenant clients) | **Accepted** 2026-09-22 · shopper-account sub-decision open |
| 0005 | Jobs: Celery + RabbitMQ with transactional outbox | Proposed |
| 0006 | REST API conventions | Proposed |
| 0007 | Licence grant envelope and signing algorithm | Proposed |
| 0008 | Web UI technologies (ERP/POS/sign SPAs, Go SSR storefront) | Proposed · resolves spec §23 open item |
| 0009 | Module system: independent apps, declared dependencies, per-tenant enablement | Proposed · 50-app dependency graph open |
| 0010 | Naming: PEP 8 Python, CamelCase database | **Accepted** 2026-09-22 |
| 0011 | Class-based architecture: controllers, services, repositories; everything in classes | **Accepted** 2026-09-22 |
