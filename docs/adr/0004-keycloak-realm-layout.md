# 0004 — Keycloak realm and client layout

**Status:** Accepted 2026-09-22 for the realm layout; one sub-decision still open (see below) · **Requirements:** IAM-01..03, MOB-02..04, B2B-01, BMA-01/02

## Context
The spec forbids a realm per small SaaS tenant by default, requires separate employee, customer, service-account and mobile clients, and links B2B buyers by issuer/subject. One Flutter app serves staff and buyers. Keycloak clients are applications, not user partitions: any user in a realm can authenticate to any of its clients unless flows restrict it. User populations are therefore separated with realms, and tenants with ERP memberships.

## Decision
- Each deployment runs one Keycloak with two realms **shared by all tenants on that deployment**. For the shared SaaS deployment that means every client company. A dedicated or client-hosted deployment has its own Keycloak and its own two realms.
  - `staff`: employees of every tenant. No self-registration; MFA policy configurable; can federate to a client's IdP.
  - `customers`: B2B buyer users (invitation only) and B2C shoppers of every tenant.
- Keycloak runs on one fixed host, e.g. `auth.erp.com`, so issuers stay constant: `https://auth.erp.com/realms/staff` and `…/customers`. The API pins them.
- **Clients:**
  - Shared clients: `erp-api` (audience only, via audience mappers), `mobile` (public, PKCE S256, no direct grants), and service-account clients per worker role.
  - Per tenant: `<slug>-web` in `staff`, and `<slug>-store` / `<slug>-portal` in `customers`. These are created through the Keycloak Admin API at tenant provisioning, with exact redirect URIs for the tenant's domains (Keycloak does not accept subdomain wildcards in redirect URIs) and an optional per-client login theme for branding.
  - Per-tenant clients do **not** separate users. The staff client additionally denies users without the `staff` realm role, using a client browser-flow override with *Condition – User Role* + *Deny Access*.
- The ERP identifies people by `(issuer, subject)` in the registry's `identities` table. Tenant access comes only from registry `memberships`. Client administrators manage users through the ERP, which calls the Keycloak Admin API with a service account restricted to that tenant's users. Client admins never get Keycloak console access.

## Open sub-decision (owner)
With one shared `customers` realm, a shopper has one platform account across every merchant's store, and signing up at a second store reveals that the e-mail already has a platform account. If merchants must have fully separate shopper accounts, choose between:
- namespaced customer accounts per tenant, or
- Keycloak Organizations inside `customers`, verified against the pinned Keycloak version.

This must be decided before the P1.6 storefront sign-up is built.

## Consequences
- The number of realms stays at two however many tenants join. Each tenant adds only Keycloak clients.
- Someone who is staff in two companies has one login and two memberships, and switches company explicitly.
- Password policy and token lifetimes are per realm, so they are the same for all tenants. Stricter MFA for one tenant needs conditional flows.
