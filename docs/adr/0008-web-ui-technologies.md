# 0008 — Web UI technologies

**Status:** Proposed · resolves spec §23 "website rendering approach" · **Requirements:** WEB-01..05, POS-03, ENV-19, B2B-02

## Decision
- `erp-web` (staff back office) and `pos-web` (touch POS, installable PWA with IndexedDB offline queue and service-worker cached catalogue versions): React + TypeScript + Vite in one pnpm workspace sharing `packages/ui` and the generated `packages/api-client`.
- `sign-web`: a separate minimal React app for external signers. It uses only the `/api/v1/sign/*` recipient-scoped API, so no staff API surface is loaded (ENV-19).
- Storefront and B2B portal: **Go server-rendered HTML** (`html/template` + htmx for partial updates). It serves themes/blocks, SEO and multi-domain routing, calls the ERP API for prices, carts, checkout and orders, and never writes ERP tables.

## Why Go SSR over Next.js
Go is already mandated for the website backend. SSR in the same process avoids a third runtime (Node) in client-hosted installs, keeps SEO simple, and avoids an extra BFF hop. Rich interactive pieces (product configurators) can be small islands later. The spec forbids introducing both approaches without a reason.
