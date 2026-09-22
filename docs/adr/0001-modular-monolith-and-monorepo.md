# 0001 — Modular monolith and monorepo layout

**Status:** Proposed · **Requirements:** ARC-01, ARC-02, ARC-04, ARC-05, OPS-01

## Context
The spec fixes FastAPI for the ERP, Go for the website backend and Flutter for mobile. It asks for module-owned tables, and for services to be extracted only when there is a demonstrated need. SaaS and client-hosted deployments must use the same images.

## Decision
- One Python package `erp` produces one container image, run in several roles: `api` (uvicorn), `worker` (Celery), `scheduler` (single Celery beat per schedule scope), `relay` (outbox relay).
- `control_plane` is a separate FastAPI app and image with its own database. It is deployed only by the vendor.
- Monorepo layout:
  ```
  backend/   pyproject.toml (uv), src/erp/{core,shared,modules/<name>}, src/control_plane, tests/, migrations/
  frontend/  pnpm workspace: apps/{erp-web,pos-web,sign-web}, packages/{ui,api-client}
  storefront/ Go module (storefront + B2B portal)
  mobile/    Flutter app (Phase 2 only)
  deploy/    compose files, keycloak realm templates, postgres init, later helm
  docs/      adr/, plan/, runbooks/
  ```
- Each module exposes `interface.py`. `import-linter` contracts forbid importing another module's internals (`models`, `service`, `api`).

## Consequences
- One deployable keeps local hosting simple, and module boundaries stay enforceable in code.
- Extracting a module later means replacing its `interface` with a client, which is a contained change.
- Every module shares one Alembic history. Migrations are ordered globally, and module ownership is enforced by schema.
