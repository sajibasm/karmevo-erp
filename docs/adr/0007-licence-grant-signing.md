# 0007 — Licence grant envelope and signing algorithm

**Status:** Proposed · **Requirements:** LIC-05..07, LIC-10

- Envelope: compact JWS (RFC 7515). Header `alg: EdDSA` (Ed25519), `kid` required, `typ: "erp-license+jwt"`. The payload follows the spec §26 field contract, with RFC 3339 UTC timestamps and a maximum size of 64 KiB.
- Verification: `alg` is checked against an allowlist of `EdDSA` only. `kid` must exist in the local trust bundle (public keys only, shipped with the release and updated only through a bundle signed by the established root). Keys are never fetched from URLs inside a grant. The verifier checks issuer, audience `erp-runtime`, `account_id` and `deployment_id` binding, `not_before`/`expires_at`, and `revision` ≥ last accepted.
- Library: a maintained JOSE implementation, chosen at pin time from its official docs (candidates: `joserfc`, `PyJWT` with `cryptography`).
- Private keys live only in the control plane's protected signing service (KMS/HSM where available). They never appear in images, repos or fixtures. Test keys use a `test` issuer that production configuration rejects.
- Rollback detection keeps the last accepted revision and the last trusted time. The limitation for cloned or restored machines is documented (LIC-07).
