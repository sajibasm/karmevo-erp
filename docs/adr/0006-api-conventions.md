# 0006 — REST API conventions

**Status:** Proposed · **Requirements:** ARC-06, PLT-06, FLT-02, LIC-13, WFL-18

- Versioned base paths `/api/v1` (ERP), `/directory/v1` (public account directory). The OpenAPI document is committed. Breaking changes need a new version and a compatibility note.
- Errors: RFC 9457 `application/problem+json` with `type, title, status, code, detail` and optional `errors[]` for field validation. `code` values are stable API contract.
- Auth: `Authorization: Bearer <access token>`. `X-Tenant-Id` selects among the caller's verified memberships. Company/branch are passed in the body or path and validated by authz.
- **JSON keys and multi-word query parameters are camelCase** (ADR-0010), via the shared `ApiSchema` base model. Python fields stay snake_case.
- Decimals are sent as strings and floats are rejected. Timestamps are RFC 3339 UTC. Currency is ISO 4217. Business-local dates are sent as `YYYY-MM-DD` together with the company time zone.
- Pagination: `?limit=` (default 50, max 200) and an opaque `cursor`. The response is `{items, next_cursor}`.
- Idempotency: the `Idempotency-Key` header is accepted on POST. A replay with the same key and body returns the stored response. The same key with a different body returns 409 `IDEMPOTENCY_KEY_REUSED`.
- Concurrency: resources carry a `version` and an `ETag: "<version>"`. Updates require `If-Match`, and a mismatch returns 409 `VERSION_CONFLICT`.
- IDs are validated for tenant ownership on every endpoint (RLS plus explicit lookups). An ID from another tenant returns 404, not 403, so existence is not revealed.
