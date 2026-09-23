# 0012 — Tenant domains: per-tenant subdomains and host routing

**Status:** Accepted 2026-09-23 (owner decision) · **Supersedes** the open row "Staff app on tenant subdomain vs single `app.erp.com`" in `docs/plan/00-implementation-plan.md` §2 · **Extends** ADR-0004 (Keycloak realm layout)

## Context

The spec does not decide this. It never uses the words "subdomain", "reserved
slug" or "per-tenant Keycloak client". What it requires is narrower:

- **DB-03 (§30):** "Verify domain ownership and host routing; isolate public
  storefront caches."
- **WEB-01 (§13):** custom domains are a website-builder feature.
- **WEB-05 (§13):** "Customer data and unpublished content must not leak
  through shared caches or tenant domain routing."
- **OPS-02 (§19):** "Tenant hosts and trusted proxy headers must be validated."
- **§23** lists "Tenant/realm deployment policy and account-directory
  governance" as an open decision.

So the shape of tenant addressing is an owner decision, recorded here.

## Decision

**Every tenant gets its own subdomain, including for the staff ERP app.**

| Surface | Host | Notes |
|---|---|---|
| Staff ERP app | `<slug>.erp.com` | Per-tenant, this decision |
| Web POS | `<slug>.erp.com` (same host, separate route) | Same tenant resolution |
| Public storefront | `<slug>.erp.com` and tenant-owned custom domains | WEB-01 custom domains |
| B2B buyer portal | `<slug>.erp.com` | |
| Vendor control plane | a fixed vendor host, never a tenant slug | Separate from all tenant hosts |

The host is a **selection**, exactly like the `X-Tenant-Id` header it replaces
for browser traffic: it names a candidate tenant, and access is still granted
only by verified identity plus active membership (IAM-03, TEN-03). A host that
does not resolve, or that resolves to a tenant the caller has no membership
in, yields the existing `TENANT_ACCESS_DENIED`. **Never trust the host alone.**

## Consequences

- `registry."TenantDomains"` maps host → tenant, carrying the verification
  state required by DB-03 (`pending`, `verified`, `failed`) and a flag for
  whether the domain is vendor-issued (`<slug>.erp.com`) or tenant-owned.
- A **reserved-slug list** is required, because a tenant slug shares the
  namespace with vendor hosts. At minimum: `www`, `api`, `admin`, `app`,
  `auth`, `id`, `login`, `account`, `accounts`, `static`, `assets`, `cdn`,
  `mail`, `smtp`, `status`, `support`, `docs`, `help`, `billing`, `control`,
  `vendor`, `internal`, plus every host the deployment already serves.
- Host-to-tenant middleware must validate the `Host`/`X-Forwarded-Host` header
  against the trusted-proxy configuration before using it (OPS-02). An
  unvalidated forwarded host is a tenant-spoofing vector.
- Wildcard DNS (`*.erp.com`) and a wildcard TLS certificate are required for
  vendor-issued subdomains; tenant-owned custom domains need per-domain
  certificate issuance (ACME) once WEB-01 lands.
- **Per-tenant Keycloak clients** follow from this: the realms stay shared
  (`staff`, `customers`, ADR-0004), but each tenant needs its own client so
  its redirect URIs are restricted to its own host and its login page can
  carry its branding. Clients never partition users; membership does.
- Caches, and especially storefront caches, must be keyed by tenant and never
  by host alone, since one tenant may have several hosts (WEB-05).
- Client-hosted deployments serve a single tenant and may use any host; the
  same middleware resolves it, so there is no code fork (OPS-01).

## Open sub-decisions

- Slug allocation and change policy: who picks a slug, and what happens to old
  URLs when a tenant renames. Proposal: slugs are immutable once issued, with
  redirects from retired slugs held in the same table.
- Whether the vendor control plane also gets a `<slug>` per deployment, or
  only a fixed host.
- Custom-domain ownership verification method (DNS TXT vs HTTP file), due with
  WEB-01 in P1.6.

These are scheduled with **P1.1b-2**, the slice that implements this ADR, and
do not block the permission engine (P1.1b-1).
