# Global ERP and Commerce Platform — Coding Agent Requirements

Version: 2.3 | Date: 2026-09-22

## Delivery mandate: two major phases

**Phase 1 — Full ERP and web platform:** deliver all agreed ERP modules, administration, licensing, website/eCommerce, web POS, warehouse workflows and APIs. Break this work into milestones with working vertical slices; do not replace the full scope with an MVP without an explicit scope change.

**Phase 2 — Shared Flutter mobile app:** after the Phase 1 exit gate, implement the shared Android/iOS client using the released ERP APIs. No separate business engine or per-customer app forks. Phase 1 includes mobile-ready identity/discovery, authorization, API compatibility and synchronization contracts, but no production mobile app delivery. Shared dynamic approval workflows and DocuSign-style envelope signing are explicit Phase 1 requirements.

All mobile UI, native scanner integration, native secure storage and mobile app-store delivery requirements belong to Phase 2. Web/POS and USB/keyboard-wedge scanner workflows belong to Phase 1. Treat historical references to phased capabilities as milestones within these two phases, not additional major phases.

## 1. Assignment and working instructions

Build a modular business platform for manufacturing, wholesale, retail, restaurants, online commerce, HR and supporting business operations. Support SaaS and client-hosted installations using the same codebase. Launch in Bangladesh while keeping localization configurable for other countries.

This document is the product scope baseline and engineering brief. It does not claim feature parity with Odoo, certify regulatory compliance, or authorize deploying unfinished functionality as production-ready.

Before implementation, inspect the repository, its instructions, dependencies, tests and existing patterns. Produce a gap assessment, architecture decisions, entity model, API boundaries, prioritized backlog and first vertical-slice plan. Reuse suitable existing code. Do not rewrite working components merely to match a preferred framework. Implement in reviewable phases; report completed, partial and unimplemented requirements honestly. Do not build all modules as shallow screens or mock endpoints and call the platform complete.

Use requirement IDs below in backlog items and acceptance tests. Preserve a traceability matrix containing requirement, implementation location, test evidence and delivery status. Resolve routine engineering choices autonomously; explicitly record assumptions and escalate decisions that alter business scope, authentication, data ownership or compliance.

## 2. Confirmed scope versus proposed defaults

Confirmed product requirements:
- Global product; initial Bangladesh market; configurable taxes and localization.
- Both vendor-hosted SaaS and client-hosted deployments.
- Manufacturing, wholesale, retail, restaurants, website/eCommerce, HR, attendance, payroll and document signing.
- Barcode/QR workflows from receiving and manufacturing through warehouse and sales/POS.
- Warehouse stock and counting by rack, shelf and bin.
- One shared mobile app for all client businesses, entered through account number and individual username/password.
- Keycloak for identity. FastAPI for the ERP backend; Go for the website server/backend. Flutter/Dart for the shared Android/iOS app.
- Import shipments and landed costs; permission groups with per-user overrides.
- Two major delivery phases: full ERP/web platform first, Flutter app second.

Proposed engineering defaults, subject to repository evidence and architecture review:
- Modular monolith ERP with separately deployed storefront, identity and workers.
- PostgreSQL; SQLAlchemy and Alembic for Python persistence/migrations; Celery and RabbitMQ for jobs; Redis for cache; S3-compatible object storage.
- React/TypeScript for ERP and POS. Website UI choice remains open: Go-rendered HTML or React/Next.js with Go backend. Do not introduce both approaches without a reason.
- Flutter/Dart is confirmed for mobile; package/state-management choices require technical validation, not a new framework selection.
- Kafka is optional future event-streaming infrastructure, not an initial dependency.
- Internet-connected client hosting is the initial planning assumption. Fully disconnected operation remains a separate scope decision.

## 3. Architecture and ownership

ARC-01: Organize FastAPI into platform, catalogue, sales, purchasing, inventory, manufacturing, restaurant, tax, finance, people, documents and supporting modules. Each module owns its tables and business rules. Cross-module writes go through application interfaces; avoid a universal CRUD service or shared mutable tables without ownership.

ARC-02: Keep authoritative pricing, tax, reservations, orders, stock, payroll and accounting logic in the ERP. Go serves website needs and invokes ERP APIs; it must not independently implement these rules or directly write ERP tables. A storefront read model is allowed with documented synchronization and staleness handling.

ARC-03: Use database transactions for business changes requiring atomicity. Store an outbox record in the same transaction when external work must follow. Dispatch after commit; consumers deduplicate and retry safely. Never claim that a broker alone provides exactly-once business effects.

ARC-04: Separate business runtime from SaaS administration. SaaS administration handles signup, provisioning, subscriptions, deployment metadata and entitlements. Client-hosted core operations must continue without a live SaaS control-plane connection, subject to an explicitly defined licensing policy.

ARC-05: Extract services only for demonstrated independent scaling, ownership or isolation needs. API and Celery workers may share domain code without being independent microservices. Avoid premature distributed transactions.

ARC-06: Version REST APIs and publish OpenAPI schemas. Generate clients where useful. Define pagination, filtering, sorting, error codes, decimal serialization, idempotency, optimistic concurrency and compatibility policy. Validate IDs and ownership on every endpoint.

## 4. Tenancy, identity and access

TEN-01: Model tenant/business account, legal company, branch, warehouse and user membership separately. An account number identifies a tenant/deployment; it is not a password or proof of authorization. Use internal immutable IDs separate from human-readable account numbers.

TEN-02: SaaS may use a shared database with tenant-scoped constraints and row-level security. Document database-role bypass protections and connection-pool tenant-context handling. Support dedicated deployments without changing business code. Client hosting generally has one tenant with multiple companies/branches.

TEN-03: Scope database queries, cache keys, object storage access, jobs, exports, search, sockets, notifications and audit records to the correct tenant. Tenant context comes from verified identity and membership, not a freely trusted request header. Users belonging to multiple tenants must explicitly select an authorized context.

IAM-01: Keycloak handles authentication, SSO, MFA, reset and federation. ERP handles detailed company/branch permissions, record access, approval limits and segregation of duties. Separate employee, customer, service-account and mobile clients.

IAM-02: Validate issuer, signature, audience, expiry and appropriate token claims; support key rotation. Use least-privilege service identities. Never put confidential client secrets in browser/mobile applications. Keep Keycloak persistence separate from ERP-owned schemas and migrations.

IAM-03: Define realm strategy in an ADR; do not automatically allocate a realm per small SaaS tenant. Local installations can use local Keycloak and customer identity federation. Tenant membership is checked even after successful authentication.

IAM-04: Enforce permissions on the server as well as the UI. Record sensitive actions, actor, tenant, timestamp, target, outcome and reason; redact secrets and sensitive payroll data. Support session revocation and controlled, audited support access.

## 5. Phase 2: one shared Flutter mobile app for every client

MOB-01: Ship one application per supported mobile platform, usable by all clients; do not require a separate build per business. Audience includes staff, managers and B2B customer users. Provide separate authorized staff and buyer workspaces in the same Flutter app. B2C consumer shopping in the app remains a separate scope decision.

MOB-02: Sign-in journey: enter account number -> resolve trusted deployment configuration -> display business identity -> authenticate using username/password through Keycloak, with MFA if configured -> choose authorized company/branch -> load allowed modules. Preserve the requested account-number/user/password experience while using secure OIDC rather than collecting credentials into the ERP API.

MOB-03: Use Authorization Code with PKCE through the platform authentication session/system browser. Validate state, nonce, redirect and issuer. Do not default to resource-owner-password grants or embedded credential-capturing webviews. Any requirement for a completely native password form needs a separate identity design review.

MOB-04: Provide an account directory for SaaS and registered client-hosted deployments. Return only minimal approved metadata: account identity, API endpoint, issuer, client configuration, capabilities and minimum API/app compatibility. Authenticate administration of mappings, validate endpoint ownership, rate-limit lookup and avoid revealing users or sensitive account details. Never forward passwords or existing tokens to an endpoint supplied by an untrusted QR/link.

MOB-05: Client-hosted servers must be reachable through approved HTTPS, VPN or local connectivity. Account lookup cannot make an isolated server reachable. Provide a verified enrollment/configuration option for restricted environments; signed deployment configuration may bootstrap a local endpoint. No TLS validation bypass or arbitrary endpoint redirect is allowed.

MOB-06: Store refresh credentials in OS secure storage, never passwords. Namespace local databases, queued work and tokens by deployment/tenant/user. Account switching must not send pending work to another tenant. Logout must clear or lock cached sensitive data according to policy. Biometric unlock may protect a local session but does not replace server authorization.

MOB-07: Mobile functions delivered by phase: dashboards, approvals, product lookup, barcode/QR scans, receiving/counting/transfers, sales/order lookup, attendance and leave, payslips, notifications and task updates. Full desktop feature parity and mobile payment-terminal support are not assumed.

MOB-08: Explicitly label offline-capable operations. Queue them with stable operation IDs, server-side revalidation and visible conflict handling. Sensitive actions and first login require connectivity. Recheck permissions on sync; support expiry of offline access and explain delayed revocation while a device is disconnected.

MOB-09: Tenant-isolate push registrations and deep links. Push messages carry minimal information, and opening them rechecks access. Support capability negotiation because one app must work with client-hosted servers upgraded at different times. Publish minimum/supported version rules and graceful upgrade messages.

Acceptance: the same app connects to two SaaS accounts and one reachable client-hosted installation; wrong membership is rejected; switching accounts leaks no tokens, cached records or pending jobs; changed endpoints cannot capture credentials; old compatible servers function without an app fork.

## 6. Shared platform and master data

PLT-01: Companies, branches, departments, warehouses, locations, business calendars, fiscal periods, currencies, languages and time zones are configurable.
PLT-02: Shared contacts support customer/supplier roles, addresses, tax registrations and contacts without conflating employees with public customer identities.
PLT-03: Products support goods, services, ingredients, prepared stock and manufactured goods; variants, images, units, packaging, categories, tax classes, traceability and multiple identifiers. SKU and global trade identifier are distinct fields.
PLT-04: Unit conversion has explicit dimensions and precision. Packaging conversion is product-specific. Weight-to-volume conversions require approved product-specific factors rather than generic assumptions.
PLT-05: Configurable document numbering, templates, notifications, approvals, custom fields, import/export and audit. Module dependencies and entitlements must be enforced server-side. Disabling a module preserves historical data.
PLT-06: Use decimal quantities/money; explicit rounding; UTC timestamps plus business time-zone context. Do not use floating point for authoritative monetary calculations.

## 7. Inventory, warehouse and location counts

INV-01: Flexible hierarchy: warehouse -> zone -> aisle -> rack -> shelf -> bin. Levels may be skipped. Each location has a unique tenant-scoped code, barcode/QR, type, active status and optional capacity/product restrictions. Prevent cycles and ambiguous active codes.
INV-02: Distinguish physical storage, receiving, dispatch, production, transit, quarantine and scrap. Internal transfers preserve total stock except explicit loss/adjustment transactions. Track ownership for consigned stock if included in a later phase.
INV-03: Stock ledger tracks product variant, company, warehouse/location, quantity/unit, batch/serial, stock status and source document. Maintain consistent balances as projections; do not silently edit balances without ledger entries.
INV-04: Support on-hand, reserved, available, incoming, in-transit and quarantined quantities with documented formulas. Define configurable negative-stock policy and enforce serial uniqueness. Use transaction locking or equivalent to prevent concurrent overselling.
INV-05: Receiving, put-away, reservation, picking, packing, dispatch, transfers, returns, replenishment, opening balances and adjustments must create traceable movements. Multi-stage transfers distinguish dispatch from receipt.
INV-06: A product can occupy many bins and a bin can contain permitted products/batches. Aggregate shelf/rack/warehouse totals from stock-bearing locations without double counting. Define whether parent locations can directly hold stock; default to leaf locations.
INV-07: Support bin/shelf/rack/zone/warehouse count sessions, blind counts, assigned counters, recounts, batch/serial capture, approval thresholds and adjustment reasons. Use a movement freeze or timestamp-based reconciliation policy during counting.
INV-08: Cycle-count scheduling, discrepancy reports, capacity checks and location occupancy. Moving occupied locations or deactivating them requires controlled migration/validation.
INV-09: Inventory valuation method is explicitly selected and version-controlled by supported scope. Keep physical picking rules such as FEFO distinct from valuation rules. Reconcile inventory subledger with finance.

Acceptance: 40 units in one bin and 60 in another aggregate to 100; moving 10 changes location balances but not total. Two concurrent reservations cannot consume the same available units. An approved count produces exactly one adjustment even after retries. Quarantined stock is excluded from sellable availability.

## 8. Barcode, QR and labels

BAR-01: Support EAN/UPC, internal Code 128, GS1-128, GS1 DataMatrix, ordinary QR and GS1 Digital Link parsing/generation as applicable to approved use cases. Validate chosen standards against official specifications during implementation; support only documented subsets rather than claiming universal compliance.
BAR-02: Store multiple identifiers per product/variant/packaging. Associate packaging quantity and UOM; scan a carton of 12 as the intended package rather than one base unit. Map supplier identifiers explicitly.
BAR-03: Separate identifier recognition from business action. Product, location, production order, serial and document scans must be distinguished. Parse supported structured batch/expiry/serial data; reject malformed/ambiguous data without posting stock.
BAR-04: Label templates for materials, finished goods, bins, cartons and pallets. Validate printer DPI, dimensions, human-readable fields, encoding and scan quality. Track reprints. Global identifiers must come from valid assignments; never fabricate registered identifiers.
BAR-05: Test keyboard-wedge scanners, mobile cameras and selected 2D scanners. QR/DataMatrix require compatible hardware. Offline POS keeps versioned identifier mappings. Payment QR, table-order QR and product labels are separate purposes.

## 9. Purchasing and wholesale

PUR-01: Requisitions, RFQs, supplier offers, purchase orders, approval limits, agreements/tenders, partial receiving, rejected goods, purchase returns and supplier bills. Support configured tolerances and three-way matching between order, receipt and bill.
PUR-02: Supplier price lists, lead times, packaging, minimum quantities, replenishment proposals and landed-cost allocation with finance integration.
WHO-01: B2B accounts, negotiated price lists, quantity breaks, quotations, minimum orders, credit limits, payment terms, deposits, backorders and partial deliveries.
WHO-02: Customer portal for quotations, orders, invoices, balances and reorder; enforce server-side customer ownership and credit approval.

## 10. Manufacturing and product lifecycle

MFG-01: Versioned BOMs, units, routings, work centres, capacity, material requirements and production orders. Freeze relevant recipe/BOM version on release.
MFG-02: Plan, reserve and issue raw materials; track work in progress, actual consumption, yields, by-products, scrap, rework and finished-goods receipt. Link consumed batches/serials to produced batches for traceability and recall.
MFG-03: Material, labour and overhead costing with defined posting points and variance handling. Prevent duplicate completion/consumption under concurrent scans or job retries.
MFG-04: Subcontracting, production scheduling and multi-level BOM planning are phased capabilities; explicitly identify supported scheduling limitations. Detect BOM cycles.
MFG-05: PLM includes engineering changes, version approvals and effective dates. Maintenance covers equipment, preventive schedules, breakdown requests and downtime. Quality covers incoming, in-process and final inspection, holds, defects and corrective actions.

Acceptance: completing a production order decreases actual materials, records scrap, increases finished stock, preserves batch lineage and creates the intended cost/accounting effects once. A changed BOM does not rewrite an existing released order.

## 11. Sales, retail POS and returns

SAL-01: Leads/opportunities, activities, quotations, sales orders, discounts, price lists, reservations, deliveries, invoices, payments and credit notes with controlled state transitions.
POS-01: Touch-friendly checkout, barcode scans, variants/packaging, customer selection, promotions, tax, split tender, receipts, cash shifts, opening float, cash-in/out and reconciliation.
POS-02: Controlled refunds/exchanges, original-sale lookup, permissions, reason codes and treatment of damaged versus resellable returns. Payment refund, sales reversal and physical restocking are separate coordinated actions.
POS-03: Offline order queue, device IDs, stable transaction IDs, cached catalogue/rule versions and retry-safe synchronization. Define maximum offline age, stock policy and price conflict handling. Never silently overwrite completed offline sales on sync.
POS-04: Cash can follow approved offline policy. Offline card acceptance depends on provider/hardware capability and is not promised by local order storage.
POS-05: Receipt templates include seller details, items/modifiers, quantities, discounts, tax breakdown, service charges, payments, change and reference. Support selected printers, digital delivery, copies and refund receipts.
SAL-02: Subscriptions include recurring billing, renewals, cancellations and failed-payment handling. Rental includes availability, contracts, pickup/return, deposits and damage/late fees as later modules.

## 12. Restaurant recipes, ingredients and operations

RES-01: Menus, availability, sizes, variants, modifiers, kitchen stations, tables, floor plans, seats, table transfers, dine-in, takeaway and delivery. Include kitchen display/tickets, preparation states, course sequencing, split/merged bills, service charges and tips.
RES-02: Versioned recipe per menu item/size with ingredients, quantities, UOM, yield and modifier deltas. Cost per portion uses defined ingredient valuation. Include allergens and dietary tags as maintained business data, not inferred guarantees.
RES-03: Made-to-order items reserve ingredients at acceptance and consume at a configured preparation milestone. Batch-prepared sauces/dough/etc. consume raw ingredients and create prepared inventory, later consumed by meals. Do not double-consume both raw and intermediate stock.
RES-04: Trimming, cooking yield, substitutions, portions, spoilage and waste need explicit records. A cancelled unprepared order releases reservations; a prepared cancellation records waste/recovery according to policy. Refunds do not automatically restore ingredients.
RES-05: Track dry store, freezer, kitchen, outlet and other locations using the shared inventory hierarchy. Track ingredient batches/expiry and FEFO picking where configured.
RES-06: Customer receipt and kitchen ticket are distinct documents. QR menu/table ordering must validate table context and route accepted orders through normal pricing, stock and kitchen rules.

Acceptance: two burgers using 1 bun, 150 g chicken, 20 g lettuce and 15 g sauce each consume 2 buns, 300 g chicken, 40 g lettuce and 30 g sauce at the configured milestone. Extra toppings add their recipe quantities. Replayed kitchen events do not consume twice. Prepared-order refund does not replenish raw chicken.

## 13. Website, eCommerce and customer experience

WEB-01: Website builder/content management, themes, pages, navigation, media, custom domains, responsive design, Bangla/English, SEO metadata and publishing workflow. Begin with safe predefined blocks; unrestricted custom scripting is not a default feature.
WEB-02: Catalogue, search/filter, variants, customer-specific visibility/prices, cart, checkout, shipping/pickup, coupons, order tracking, customer accounts and return requests. Validate final totals and availability with ERP.
WEB-03: ERP owns order/payment state. Define pending, authorized, paid, failed, cancelled, refunded and partial states appropriate to providers. Verify webhook signatures, deduplicate events and handle out-of-order updates and payment success after reservation expiry.
WEB-04: Courier and payment adapters, cash-on-delivery collection/settlement reconciliation, fraud controls and provider sandbox tests. No unsupported provider integrations or pricing claims.
WEB-05: Blog publishing, moderated forum, eLearning courses/progress and live chat are phased modules. Customer data and unpublished content must not leak through shared caches or tenant domain routing.

## 14. Global tax, finance and Bangladesh localization

TAX-01: Dedicated shared tax engine for purchasing, sales, POS, restaurants and commerce. Configure jurisdictions, registrations, tax types, rates, effective dates, product categories and customer/supplier treatments.
TAX-02: Support inclusive/exclusive pricing, multiple and compound taxes, exemptions, zero-rated and out-of-scope distinctions, shipping/discount treatment, withholding where applicable and explicit rounding policies.
TAX-03: Rule selection may consider company, seller/buyer location, delivery location, transaction type and registration status. Record the selected rule version and reasoning. Unknown or ambiguous jurisdiction handling must be explicit.
TAX-04: Freeze tax inputs/results on posted documents. Credit notes follow original tax treatment where appropriate; rule changes do not recalculate history. Provide external-tax-provider adapters without duplicating ownership of calculations.
FIN-01: Chart of accounts, journals, balanced double-entry posting, receivables/payables, bank/cash reconciliation, expenses, assets/depreciation, budgets/cost centres, financial statements and period locks delivered in scoped phases.
FIN-02: Posted journals are corrected through authorized reversals/adjustments. Reconcile sales, stock valuation, payroll and payment settlements. Multi-currency tracks transaction/base currency, exchange-rate provenance and gains/losses.
LOC-01: Bangladesh package supplies validated defaults, Bangla/English templates, BDT and Asia/Dhaka defaults and local adapter configurations. Do not hard-code rates or assert compliance without reviewing current authoritative rules and qualified local requirements.
LOC-02: Country packages are separately versioned with effective dates, migration notes and golden calculation tests. Different companies can use different country configurations. Global readiness does not mean every country is launch-supported.

## 15. HR, attendance and payroll

HR-01: Employee profiles, departments, jobs, contracts, onboarding/offboarding, document permissions, recruitment pipeline, referrals, appraisals and goals. Fleet tracks vehicles, assignments, service and operating costs.
ATT-01: Shift plans, overnight shifts, holidays, clock-in/out, breaks, lateness, overtime, leave balances and approval. Attendance device imports and optional mobile location controls require deduplication and a declared privacy policy. Distinguish attendance from project timesheets.
PAY-01: Effective-dated salary structures, allowances, deductions, approved attendance/overtime inputs, payroll periods, calculation preview, approval, payslips, bank export and finance posting. Statutory rules are country-specific and validated before release.
PAY-02: Freeze payroll inputs and calculation version at approval. Correct finalized payroll through controlled adjustments. Prevent duplicate payment exports/submissions. Bank file generation does not itself prove payment settlement.
HR-02: Employee self-service on web/mobile includes leave requests, attendance corrections, own documents and own payslips. Managers see only their authorized teams; payroll access has separate permissions.

## 16. Documents, signing and approvals

DOC-01: Permissioned files/folders, tags, versions, retention, previews, malware scanning and links to business records. Signed document originals must be preserved.
SIG-01: Templates, signature/initial/date fields, sequential/parallel signers, request expiry, reminders, decline/cancel states, status tracking and configurable signer verification.
SIG-02: Preserve document hashes, evidence, timestamps, consent and immutable completed versions. Separate electronic signing from certificate-based digital signatures; integrate approved providers for the latter rather than inventing a trust system.
SIG-03: Connect sales, purchasing and HR records to signing requests. Changing a document after signing creates a new version/request. Signature assurance and legal suitability depend on market/document type and require validation.
APR-01: Reusable approvals with conditions, thresholds, delegation, escalation, rejection reasons and audit. No approval through a stale push action without rechecking current state and access.

## 17. Remaining app catalogue and phased requirements

All 50 apps visible in the reference screenshots remain roadmap scope. Their grouping is not a promise to ship them all in the first release.

| Group | Apps | Minimum scope |
|---|---|---|
| Website (6) | Website, eCommerce, Blog, Forum, eLearning, Live Chat | Content/storefront, publishing, moderation, learning progress, visitor support |
| Sales (5) | CRM, Sales, Point of Sale, Subscriptions, Rental | Pipeline, order lifecycle, checkout, recurring contracts, hire lifecycle |
| Finance (7) | Accounting, Invoicing, Expenses, Documents, Spreadsheets, Sign, ESG | Ledger, billing, reimbursements, records, data-linked sheets, signing, sustainability metrics |
| Inventory/manufacturing (6) | Inventory, Manufacturing, PLM, Purchase, Maintenance, Quality | Stock, production, change control, procurement, equipment, inspections |
| HR (7) | Employees, Recruitment, Time Off, Appraisals, Payroll, Referral, Fleet | People records, hiring, leave, reviews, pay, referrals, vehicles |
| Marketing (6) | Marketing Automation, Email Marketing, SMS Marketing, Social Marketing, Events, Survey | Campaign journeys, consent-aware delivery, provider integrations, ticketing and feedback |
| Services (6) | Project, Timesheet, Field Service, Helpdesk, Planning, Appointments | Tasks, billable time, onsite jobs, tickets/SLAs, schedules, booking |
| Productivity (6) | Discuss, Approvals, Internet of Things, VoIP, Knowledge, AI | Channels, authorizations, device adapters, telephony, knowledge content, assisted work |
| Customization (1) | Studio | Safe custom fields, forms, templates and workflows |

Attendance is an additional explicit requirement even though absent from the screenshots. Industry capabilities such as recipes and warehouse bins are deeper workflows within the catalogue.

EXT-01: Marketing includes audience rules, consent/unsubscribe, templates, scheduling, delivery status and deduplication. Social and telephony support depends on verified provider APIs.
EXT-02: Projects include tasks/dependencies, timesheets and billing; field service includes assignment, materials and completion evidence; helpdesk includes tickets, priorities, SLAs and customer access; appointments prevent double booking.
EXT-03: Discuss/Knowledge support permissions and business-record links. Spreadsheets need scoped data access and safe formulas/exports. ESG requires metric definitions, units, evidence and calculation versions, not unsupported certification claims.
EXT-04: IoT adapters authenticate devices and validate measurements. Studio starts with metadata-driven customization, not arbitrary tenant Python/SQL execution. Track configuration versions and migration compatibility.
EXT-05: AI is optional, permission-aware and provider-configurable; record model/prompt/tool provenance as appropriate. Human approval and normal domain validation govern financial, payroll and inventory mutations. Client data must not be sent to external AI without configured authorization.

## 18. Background jobs and integration contracts

JOB-01: Celery executes Python jobs; RabbitMQ transports tasks; separate queues for notifications, documents, imports, integrations and payroll. Configure broker durability, publisher confirmations, acknowledgement/recovery policy and tested bounded retries with backoff.
JOB-02: PostgreSQL stores authoritative job status, progress, attempts and business results. Include tenant, initiating actor, operation ID, record ID and rule/configuration versions; avoid embedding secrets or large files in messages.
JOB-03: One active scheduler per schedule scope. Store tenant business schedules with time-zone/DST handling, catch-up policy and overlap control. Retried recurring runs have unique execution keys.
JOB-04: Outbox publishing can repeat; consumers must be idempotent. Track failed jobs, support authorized replay and reconcile missing/stuck operations. Long tasks checkpoint or process bounded batches; use timeouts and resource limits.
JOB-05: Go requests ERP-owned jobs through the API. If native Go workers are added, use separate documented queues/contracts. Kafka requires a later ADR tied to actual event replay/fan-out needs.
INT-01: Define adapters for payments, banking files, couriers, email/SMS, signing, attendance devices, printers, tax providers and AI. Capture correlation IDs, signature verification, rate limits, circuit/timeouts and replay protection.

## 19. Deployment, security and operations

OPS-01: Same versioned container images and migrations for SaaS/client hosting. Provide a documented Linux container deployment profile; orchestration/HA profile is a separate supported option. No customer-specific code forks.
OPS-02: Per-environment secrets, TLS, private data services, least-privilege accounts, restricted CORS and CSRF protections where cookies are used. Tenant hosts and trusted proxy headers must be validated.
OPS-03: Document backup ownership, encrypted backups, PostgreSQL point-in-time recovery where supported, file/identity backups and restoration drills. Define measured RPO/RTO and availability targets before production sign-off; no invented SLA.
OPS-04: Structured logs, traces, metrics, health/readiness checks and alerts. Track queue age, job failures, payment reconciliation, stock inconsistencies, API latency and database health without logging credentials or sensitive payloads.
OPS-05: Releases include compatibility notes, checksums, migrations, upgrade preflight, backup requirements and recovery strategy. Test upgrades from supported versions. Reverting images alone does not reverse data migrations.
OPS-06: Offline/client-hosted licensing and telemetry are explicit policies. No mandatory vendor data export. External payment/email/push functions degrade transparently when connectivity is unavailable.
OPS-07: Select supported library versions during implementation using official documentation, then pin dependencies and scan them. Load-test realistic data, concurrent reservations, checkout and large job batches on the declared deployment profile. Agree numerical capacity targets before claiming global-scale performance.

## 20. Data model baseline

Create module-owned models, migrations and constraints for at least:
- Identity/platform: Tenant, AccountDirectoryEntry, Company, Branch, Membership, RolePolicy, ModuleEntitlement, AuditEvent, ConfigurationVersion.
- Catalogue: Product, Variant, Unit, UnitConversion, Packaging, ProductIdentifier, Category, PriceList, PriceRule.
- Warehouse: Warehouse, Location, Batch, Serial, StockMovement, StockBalance, Reservation, Transfer, CountSession, CountLine, Adjustment.
- Procurement/sales: Supplier, Customer, PurchaseOrder/Line, Receipt, SalesOrder/Line, Delivery, Return, Payment, Settlement.
- Production/restaurant: BOM/Version/Line, Routing, WorkCentre, ProductionOrder, Consumption, Output, MenuItem, RecipeVersion, Modifier, Table, KitchenTicket, PreparationEvent, WasteRecord.
- Finance/tax: TaxJurisdiction, Registration, TaxRuleVersion, TaxSnapshot, Invoice/Line, CreditNote, Account, JournalEntry/Line, FiscalPeriod, ExchangeRate.
- People: Employee, ContractVersion, Shift, AttendanceEvent, LeaveRequest, PayrollRun, PayrollInputSnapshot, Payslip.
- Documents/jobs/mobile: DocumentVersion, SigningRequest, SignerEvidence, ApprovalRequest, OutboxEvent, JobRun, InboxDeduplication, DeviceRegistration, SyncOperation.

This is a baseline, not a command to create one giant schema first. Add entities with vertical slices. Document unique constraints, tenant-qualified foreign keys, deletion/retention policy, indexes and concurrency strategy. Financial and stock records are never casually hard-deleted.

## 21. Critical end-to-end acceptance gates

| ID | Scenario and required evidence |
|---|---|
| E2E-01 | Tenant A cannot read/write/export tenant B records through IDs, caches, jobs, files, search, mobile or notifications. |
| E2E-02 | Receive materials into bins, transfer to production, manufacture, label finished goods, sell through POS, produce receipt and reconcile stock/accounting. |
| E2E-03 | Two channels compete for final available stock: reservation policy holds with no accidental oversell. |
| E2E-04 | Count during movement follows chosen freeze/reconciliation policy; replayed approval creates no duplicate adjustment. |
| E2E-05 | Recipe and batch-preparation tests prove correct consumption, modifiers, waste and cancellation/refund behaviour. |
| E2E-06 | Inclusive/exclusive, compound, exempt, rounded and effective-dated tax cases match reviewed golden examples; historical documents stay unchanged. |
| E2E-07 | Offline POS/mobile reconnects with duplicate submissions and changed prices/permissions; conflicts are visible and no duplicate financial effects occur. |
| E2E-08 | Payment webhook duplicates, delayed success, refund failure and out-of-order events reconcile without false paid status. |
| E2E-09 | Payroll rerun preserves approved inputs and creates no duplicate posting/export; employee payslip privacy is enforced. |
| E2E-10 | Signed document alteration is detectable; completion preserves original bytes and evidence. |
| E2E-11 | Shared mobile app switches SaaS accounts and client-hosted deployment with isolation and safe endpoint resolution. |
| E2E-12 | Broker/worker crash between commit, publish and acknowledgement recovers through outbox and idempotency. |
| E2E-13 | Restore a real backup and perform a supported version upgrade for both hosting profiles. |
| E2E-14 | Bangla text prints correctly on selected receipts/labels/documents; supported barcodes scan on target hardware. |

## 22. Two-phase delivery plan and coding-agent outputs

### Phase 1 — Full ERP, commerce and operational web applications

| Milestone | Deliverables | Exit evidence |
|---|---|---|
| P1.1 Discovery and foundation | Repository audit, ADRs, tenancy, Keycloak, permission engine, licensing, audit, module registry, migrations, CI, outbox/jobs, deployment skeleton | Tenant isolation, deny-precedence, licence and job-recovery tests |
| P1.2 Shared business foundation | Companies/branches, catalogue, identifiers, units, prices, tax configuration, financial posting foundation | Decimal/rounding cases, balanced journals, versioned tax examples |
| P1.3 Procurement and warehouse | Purchasing, import shipments/landed costs, receiving, bins, transfers, reservations, counts, barcode labels | Import-to-bin valuation and counting reconciliation |
| P1.4 Sales and fulfilment | CRM, wholesale, retail web POS, receipts, split-source allocation, loading approval, dispatch, returns/warranty/repair | One invoice across sources, approval invalidation, serial return/repair tests |
| P1.5 Industry operations | Manufacturing/BOM/PLM, quality, maintenance, restaurant recipes/batches/kitchen | Material-to-finished-sale traceability and restaurant consumption tests |
| P1.6 Web commerce | Go backend, chosen website UI, storefronts, content, catalogue, checkout, payments, shipping, portals | Tenant domains, payment replay, reservation and reconciliation tests |
| P1.7 People and documents | HR, recruitment, attendance, leave, appraisals, referrals, payroll, fleet, expenses, approvals, documents/signing | Authorized workflow tests, payroll validation, signed evidence, expense reconciliation |
| P1.8 Remaining catalogue | Rental/subscriptions, marketing, services, collaboration, spreadsheets, ESG, IoT, VoIP, Knowledge, AI and safe Studio | Each agreed capability has functional UI/API, authorization and integration evidence |
| P1.9 Readiness and release | Validated Bangladesh package, both hosting profiles, backups/restore, upgrade path, operational documentation, mobile-ready contracts | Full Phase 1 traceability review, UAT and release gate |

Milestones may overlap when dependencies allow. Finance, security, tax and audit are cross-cutting from the foundation, not last-minute additions. All 50 reference apps plus explicitly added workflows are Phase 1 scope at the defined depth. A disabled stub is not completion. Unknown provider availability or legal requirements must be recorded as explicit blockers, not hidden in implementation status.

Phase 1 exit gate:
- All Phase 1 requirement IDs mapped to implementation, tests and documented limitations; any deferral requires explicit scope agreement.
- End-to-end manufacturing, wholesale/imports, retail, restaurant and commerce workflows demonstrate consistent stock, tax, permissions and finance.
- Permission groups/user overrides and licence enforcement tested through direct APIs, exports and workers.
- SaaS and client-hosted install, backup restore and supported upgrade validated.
- API versioning, account resolution, capability discovery, device enrollment and sync contracts tested with non-mobile test clients.
- Bangladesh calculations/templates reviewed for their declared scope; no unsupported compliance or performance claims.

### Phase 2 — Shared Flutter Android/iOS application

| Milestone | Deliverables | Exit evidence |
|---|---|---|
| P2.1 App foundation | Flutter shell, account discovery, Keycloak PKCE, secure storage, account/company/branch selection, permissions/capabilities | One build signs into multiple SaaS accounts and a reachable private deployment without leakage |
| P2.2 Business workflows | Dashboards, orders/customers, approvals, expenses, attendance/leave, own payslips, notifications, authorized repair updates | Role-based scenarios verified against Phase 1 APIs |
| P2.3 Warehouse devices | Camera/2D scanning, receiving, put-away, transfers, counting, picking/loading, manager release | Supported handheld matrix, scan quantities, approval and duplicate protection |
| P2.4 Offline synchronization | Isolated local data, pending queue, retries, conflicts, tombstones/cursors, access/licence changes | Interrupted sync, account switching, duplicate and revoked-access cases |
| P2.5 Release | Bangla/English, accessibility, device performance, push/deep links, compatibility, signed packages and store submissions | Real-device UAT, secure build/signing, approved publication |

Phase 2 exit gate: fulfil MOB/DEV native requirements, no cross-tenant cache/token leakage, no duplicate stock/financial effects, safe server-version compatibility and tested supported devices. The agreed mobile scope includes staff and full B2B portal feature parity. B2C consumer shopping and native full POS/card-terminal parity are not implied.

For every milestone deliver working code, migrations, OpenAPI changes, meaningful tests, demo fixtures clearly separated from production, deployment notes, operator/user documentation and a traceability report. Document incomplete work. Do not fabricate successful tests or automatically deploy externally without appropriate authorization.

## 23. Open decisions to resolve without blocking unrelated work

- Product name; initial pilot industry and first-release depth.
- Flutter is fixed; decide supported OS versions, Flutter packages, scanner/printer/payment devices and app-store ownership.
- Whether B2C consumer shopping shares the app remains open; B2B buyer access in the shared app is confirmed.
- Website rendering approach; current Go requirement refers to server/backend.
- Tenant/realm deployment policy and account-directory governance; restricted-host enrollment trust model.
- Internet-connected versus fully disconnected client-hosting support; VPN/private endpoint setup.
- Bangladesh tax/payroll/invoice/signature validation, providers, supported currencies and accounting methods.
- Load, availability, backup recovery targets, retention, licensing, support and API compatibility windows.

## 24. Technical references for implementation verification

These references guide implementation; requirement statements above are proposed product design, not claims that frameworks provide the business functionality automatically.
- Native-app OAuth guidance: https://www.rfc-editor.org/rfc/rfc8252.html
- Keycloak OIDC: https://www.keycloak.org/securing-apps/oidc-layers
- Keycloak integration overview: https://www.keycloak.org/securing-apps/overview
- PostgreSQL row security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Celery brokers: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/
- Celery task behaviour: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- Celery periodic scheduling: https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
- Kafka purpose: https://kafka.apache.org/intro/

## 25. First instruction to the coding agent

Read this document completely and inspect the repository. First return an evidence-based implementation plan, requirement gaps, proposed module boundaries, initial data model and the two-phase backlog with Phase 1 milestone dependencies. Distinguish confirmed requirements, proposed defaults and unresolved decisions. Include the shared mobile account-number login and both hosting modes in the foundation. Do not begin a wholesale rewrite or claim full ERP completion. After the plan is reviewed, implement agreed vertical slices with migrations, security checks and acceptance evidence.

## 26. Subscription packages and licensing — implementation specification

This section makes the previously proposed licensing architecture the implementation baseline. Commercial values (prices, grace days, renewal cadence and quota sizes) remain configurable and require product decisions; do not invent production values. The ERP business-app Subscriptions module used by clients to bill their own customers is distinct from this vendor licensing subsystem.

LIC-01: Separate authentication (Keycloak), purchased entitlements (licensing) and user authorization (ERP). Access requires a permitted licence state, enabled feature, authorized user and tenant/company/branch scope. Do not put billing enforcement solely in Keycloak roles or menu visibility.

LIC-02: Central control plane owns plans, immutable published plan versions, subscription contracts, add-ons, deployments, signed grants and audited overrides. Local runtime owns entitlement validation and operation enforcement. Do not force client-hosted business requests through the vendor control plane.

### Data model and constraints

Use a vendor control-plane database, separate from client business data. Logical licensing tables:
- subscription_plans: stable plan identity and marketing metadata.
- plan_versions: immutable published definitions; changing a catalogue creates a new version.
- features: stable capability keys and dependency metadata.
- plan_entitlements: feature keys, allowed scope, quota definitions and limit values.
- subscriptions: account ID, plan version, contract reference, start/end, lifecycle state, billing reference, revision.
- subscription_addons: purchased feature/limit increments with effective dates.
- entitlement_overrides: reason, approver, scope, effective/expiry dates; never silently permanent.
- deployments: account, deployment ID, hosting mode, status and registered installation public key where used.
- license_grants: grant ID, subscription/deployment, revision, validity, key ID, signed artifact hash and issuance reason.
- signing_key_metadata: key IDs, public material and rotation state; private keys stay in protected signing infrastructure.
- billing_events: verified provider/event ID, deduplication key, processing outcome and reconciliation state.
- license_audit_events: actor, action, target, old/new revision and reason with sensitive fields redacted.

Runtime stores verified grant, effective entitlement snapshot, policy revision, quota allocations, usage counters and audit events. Protect tenant boundaries on SaaS records and use uniqueness/foreign-key constraints. No customer passwords or ERP payroll records belong in the licensing database.

LIC-03: Resolve plan version + active add-ons + explicit overrides into one deterministic effective snapshot. Define limit aggregation per feature; do not assume all limits sum. Validate dependencies and prohibit contradictory snapshots. Module entitlement is distinct from user permission.

LIC-04: Quotas specify unit, scope and counting policy: active named users versus concurrent sessions, enabled branches, active warehouses, storage bytes or monthly usage. Enforce hard quotas atomically with concurrent creates. Distinguish soft warnings. If one subscription spans deployments, allocate bounded quotas per deployment or define online coordination; disconnected deployments cannot guarantee a live global aggregate quota without allocation.

### Grant format and cryptographic verification

LIC-05: Use a standard signed envelope and maintained cryptographic library; record algorithm selection in an ADR. Example payload field contract:

```json
{
  "schema_version": 1,
  "grant_id": "opaque identifier",
  "issuer": "configured trusted issuer",
  "audience": "erp-runtime",
  "account_id": "immutable tenant identifier",
  "deployment_id": "registered installation identifier",
  "subscription_id": "contract identifier",
  "plan_version_id": "immutable plan version identifier",
  "revision": 1,
  "issued_at": "UTC timestamp",
  "not_before": "UTC timestamp",
  "expires_at": "UTC timestamp",
  "offline_until": "UTC timestamp",
  "features": [],
  "limits": {},
  "policy_version": "versioned lifecycle policy"
}
```

This is a schema illustration, not a valid issued licence. Concrete algorithms, timestamp encoding and size limits must be settled before coding verification. Include a protected signing-key ID. Validate signature, pinned issuer/audience, schema, account/deployment binding, dates, revision and configured algorithm allowlist. Reject unsigned, unknown-algorithm, wrong-account, wrong-deployment, malformed and untrusted-key grants. Do not fetch verification keys from an arbitrary URL embedded in an imported grant.

LIC-06: Private signing keys never ship in images, repositories or client deployments. Runtime trust stores contain public keys only. Support overlapping key rotation, offline trust-bundle updates through an established trust root and a compromise-response policy. Store no production signing secrets in demo fixtures.

LIC-07: Distinguish licence validity from renewal/check-in interval. Offline allowance cannot silently extend signed expiry; any grace extension is authorized by signed policy/grant. Preserve last accepted revision and last trusted time to detect basic rollback. Restored/cloned machines and administrator-controlled clocks cannot be made fully tamper-proof; document the limitation and provide audited reactivation/recovery.

### Lifecycle and operations

LIC-08: Subscription states: trial, active, grace, restricted, cancelled-at-term and expired, with explicit effective timestamps. Revocation is a separate security/contract action. Payment pending/failed is a billing state, not automatically permission to erase or abruptly disable operations. Define state transitions in a tested policy table.

LIC-09: Verified payment settlement or an authorized contract approval activates access. Webhook ingestion authenticates the provider, deduplicates events and reconciles out-of-order events; a browser success redirect is insufficient. Chargebacks, refunds and manual changes follow explicit policy and audit.

LIC-10: Connected deployments periodically refresh signed grants with authenticated deployment credentials, retries and backoff. Offline deployments import verified grant files. Unavailable control plane does not immediately deny operations while an existing grant remains valid. Revocation reaches offline clients only on reconnection or through expiry; document that latency.

LIC-11: Upgrade activation and downgrade scheduling have explicit effective dates. Preview dependency/limit conflicts before applying a downgrade. Never delete users, branches or transactions to force quota compliance. Disable new creation where appropriate, while preserving authorized historical access/export and obligations in progress.

LIC-12: Before expiry, notify administrators. After grace, use a versioned action policy: allow authorized reads/exports and explicitly defined reconciliation/return/settlement operations; restrict new unlicensed business creation. Long-running jobs must revalidate on start and at safe checkpoints, then finish/reconcile or pause consistently rather than abandon partially posted transactions. Security revocation and normal commercial expiry may have different policies.

LIC-13: Enforcement is an ERP application service invoked by endpoints and jobs, with feature key, action, actor, tenant/company/branch and quota delta. Return stable denial codes such as FEATURE_NOT_LICENSED, QUOTA_EXCEEDED or LICENSE_RESTRICTED. UI capability responses are advisory; direct API calls still enforce. Cache by tenant and revision with bounded TTL and explicit invalidation.

LIC-14: Shared mobile/POS clients obtain capabilities from the selected deployment. Do not download vendor signing secrets or make the mobile app the licence authority. Record policy/grant version on offline operations; on synchronization apply defined commercial-expiry treatment without bypassing identity or access checks. Pending work must not disappear when a package changes.

### Proposed API boundaries

These are logical routes; adapt names to repository conventions without changing responsibilities:
- Control-plane admin: publish plan version, activate/change subscription, manage add-ons, preview effective entitlements, register deployment, issue/revoke grant. MFA, granular permission and audit required.
- Billing ingress: verified webhook ingestion with provider-specific signature validation and deduplication.
- Deployment: authenticated enrollment and grant refresh; never issue a licence based only on an account number.
- Runtime administrator: import signed licence, inspect status, view quota usage and expiration notices. Licence import cannot alter trusted keys implicitly.
- Runtime client: GET /api/v1/capabilities and GET /api/v1/license/status with only permitted metadata.
- Quota allocation and signing APIs remain privileged internal/control-plane capabilities; frontend clients cannot call them as ordinary users.

LIC-15: Provide administrative screens for plans, versions, subscriptions, deployment inventory, expiring licences, overrides, quota conflicts and audit. Client administrators see their own purchased features, usage and renewal status, without other clients' commercial data.

### Licensing implementation order and acceptance

1. Define feature registry, dependency resolver, immutable plan versions and tested lifecycle policy.
2. Build entitlement enforcement and transactional quota checks using clearly marked test grants that are never trusted by production.
3. Add protected signing/verification, trust-store rotation and runtime import/refresh.
4. Add verified billing adapter and manual-contract activation with audit.
5. Add capability UI/mobile integration, renewal notifications and restricted-mode flows.
6. Verify deployment packaging, backup/restore, migration and failure behaviour before activation for customers.

Required tests: forged/expired/wrong-tenant/wrong-deployment/unknown-key grants rejected; allowed rotation accepted; older superseded revisions rejected when known; duplicate/out-of-order billing events create one intended transition; simultaneous seat creation cannot exceed quota; package downgrade preserves records; direct APIs and workers enforce the same policy; vendor outage preserves valid local operation; disconnected expiry follows policy; restored installation needs safe recovery where rollback markers conflict; mobile account switching cannot reuse another client's entitlements.

## 27. Multi-branch and split-source fulfilment — expanded requirements

FUL-01: Tenant -> legal company -> branch is an organizational hierarchy. Warehouse/location is a stock hierarchy, not a strict one-to-one child relationship with selling branch. Use explicit branch-to-warehouse fulfilment mappings; a central warehouse can serve multiple branches. Sales centres have stock locations for counter/backroom stock.
FUL-02: One sales order and one permitted invoice can include quantities sourced from several locations. Model order lines -> fulfilment allocations -> shipment lines. Invoice lines reference order lines and optional fulfilment references as required by invoice policy. Do not make one warehouse on the invoice the sole stock source.
FUL-03: Split a single line by quantity, source, reservation and shipment. Allocations and actual handover/dispatch totals must not exceed authorized quantities; handle backorders, substitutions, cancellation and partial returns explicitly. Payment and fulfilment states are independent. Keep one invoice within its selling legal entity; cross-company fulfilment requires explicit intercompany processes, not silently mixing tax entities.
FUL-04: Add warehouse workflow: confirmed -> reserved -> picked -> awaiting loading approval -> loading approved -> loaded -> released/dispatched -> delivered, with rejected/cancelled/partial states and a configured immediate counter-handover path.
FUL-05: Sales permission does not grant dispatch approval. Warehouse manager approves a specific immutable shipment revision containing product, quantity, batches/serials, packages and relevant source/destination information. Material changes invalidate approval; partial loading requires an approved amendment or explicit partial-release policy.
FUL-06: Loading operators scan approved products/packages. Detect wrong, extra, duplicate and missing scans. Manager release verifies approval, actual loaded quantity and required documents. Capture actor/time and optional vehicle/courier. Direct APIs cannot skip approvals.
FUL-07: Picking moves goods to staging through an internal movement; dispatch records departure once. Reservations do not reduce on-hand. Counter handover follows its own authorized issue event. Each source shipment requires its own authorization and contributes to aggregate order status.
FUL-08: Add allocation, shipment revision, pick task, loading scan, approval and release-event entities. Concurrency constraints and idempotency must prevent over-allocation, duplicate loading and double stock issue.

Acceptance: one invoice for A=2 from sales centre, B=5 from warehouse and C=3 split 1+2 produces correct source movements and independent approvals. Counter delivery does not auto-complete warehouse fulfilment. Changed serial after approval blocks release. Duplicate dispatch leaves balances unchanged after the first success.

## 28. Returns, warranty and customer repairs

RPR-01: Return authorization (RMA) references sale/order/invoice and serial/batch where available; record requested quantity, reason, eligibility, approval and return tracking. Receive returned goods into inspection/quarantine, not automatically available stock.
RPR-02: Inspection disposition supports restock, repair, replace, supplier return and scrap. Separate physical stock disposition from refund/credit status. Cap returns against eligible quantities and account for previous returns.
RPR-03: Warranty records include coverage dates, terms, exclusions, registration, serial and claim history. Repair order includes reported fault, diagnosis, technician, priority, promised date, estimate, customer approval, parts, labour, external service, quality check and handover evidence.
RPR-04: Track customer-owned goods held for service separately from company-owned saleable inventory and valuation. Record custody/location without inflating sellable stock. Consume spare parts, record labour and distinguish paid versus warranty expense/invoicing.
RPR-05: External service-centre transfers have custody tracking and return receipt. Replacement units preserve old/new serial linkage. Track deposits, approval of extra charges, repair report and collection/delivery notifications.
RPR-06: Include return_requests/lines, inspections, disposition_events, warranty_policies/registrations, repair_orders, repair_estimates, repair_parts, labour_entries and custody_movements. Reuse shared approvals, files and finance posting. Customer repairs are distinct from maintenance of company equipment.

Acceptance: returned serial is quarantined; refund alone creates no restock. Repair consumes parts once, customer property remains excluded from saleable valuation, and replacement/warranty history is traceable.

## 29. Expense management expansion

EXP-01: Support employee expense claims and company operating expenses, including receipt attachment, category, date, currency, tax treatment, payment method and business purpose.
EXP-02: Allocate costs to legal company, branch, department, project or cost centre; allocations total the expense. Support employee advances, petty cash and company-paid versus reimbursable items with distinct settlement treatment.
EXP-03: Draft -> submitted -> approved/rejected -> posted -> settled, with controlled corrections and resubmission. Validate policy limits, duplicate evidence, approval authority, period locks and reimbursement status. Flag suspected duplicates for review rather than rejecting every equal-value receipt.
EXP-04: Link supplier bills, company-card transactions, advances and claims representing the same cost to avoid duplicate postings. Matching and reconciliation must not erase audit history. Mobile capture and manager approval enforce the same rules.
EXP-05: Add expense_claims, expense_lines, expense_categories, expense_allocations and employee_advances, referencing shared documents, approvals, journal entries and payments.

Acceptance: company-paid expense is not reimbursed twice; an advance settles correctly; allocations balance; duplicate posting/reimbursement retries have no additional financial effect; employees cannot view colleagues' claims without authorization.

## 30. Database and warehouse device decisions

DB-01: Default is module-based PostgreSQL schemas with tenant-scoped tables: platform, catalog, inventory, sales, purchasing, commerce, manufacturing, restaurant, finance, tax, people, service, documents and integration. Vendor licensing/control-plane data and Keycloak persistence are separate. Do not create one schema per tenant by default.
DB-02: Enforce tenant-qualified uniqueness and foreign keys, company ownership, row-security policy and privileged-role discipline. Scope workers, caches and object storage as carefully as database access. Shared SaaS and dedicated/client-hosted databases use compatible migrations.
DB-03: Commerce storefronts/domains/publications/carts/customer accounts refer to shared catalogue and ERP orders. Verify domain ownership and host routing; isolate public storefront caches. Maintain one authoritative stock/tax/order model. Billing for the software vendor is separate from tenant-owned finance records.
DEV-01: Shared mobile app supports selected Android warehouse handhelds with integrated 2D scanners, phone camera and Bluetooth scanner paths; warehouse web screens support USB keyboard-wedge scanning. Hardware support is a tested compatibility matrix, not a claim that all scanner SDKs/printers work.
DEV-02: Explicit mode determines scan action: receiving, transfer, picking, count, loading or dispatch. Scan identifies product/location/document; quantity and UOM require validation/confirmation. Serialized scans and package scans have different quantity rules. Use sound/vibration and visible confirmation/error feedback.
DEV-03: Device/user registration, location permissions, scan audit and idempotent operation IDs are required. Offline count/transfer operations have visible pending/conflict state. Loading approval and release must follow configured online authorization requirements; offline scanning alone cannot bypass warehouse approval.

## 31. Prior additions retained in this revision

The retained requirements expand the baseline with licensed package activation, signed client-hosted grants, multi-branch fulfilment, one invoice with multiple sources, manager-controlled loading/dispatch, customer repairs/warranty, detailed expenses and scanner workflows. Include these in the traceability matrix and phase plans. Licensing and tenant enforcement belong in the foundation; complete operational additions alongside their corresponding vertical slices. This document is an implementation specification; no ERP repository has been modified or deployed by this document update.


## 32. Group permissions and individual overrides — Phase 1 foundation

AUTH-01: Implement tenant-owned editable permission groups, multiple group membership and per-user grants/denials. Supply editable templates for salesperson, sales manager, warehouse operator, warehouse manager, accountant, HR/payroll and client administrator. Separate vendor/platform administration from all tenant roles. Labels such as manager alone never imply unrestricted access.

AUTH-02: Permission keys identify resource/action, e.g. sales.order.create, sales.discount.approve, inventory.count.submit, inventory.adjustment.approve, shipment.loading.approve, shipment.dispatch.release, finance.cost.view, people.payroll.view and platform.permissions.manage. Include read/create/edit/cancel/approve/export and sensitive field visibility; do not infer authorization merely from a menu or URL.

AUTH-03: Each policy carries effect (allow/deny), company/branch/warehouse scope, own/team/all record scope where applicable, business conditions, effective/expiry dates and approval limits with currency. User overrides do not edit the shared group. Prefer flat groups initially; inheritance, if introduced, must reject cycles and have documented precedence.

AUTH-04: Evaluate in this order: authenticated active membership -> licensed action -> non-bypassable tenant/security/segregation rules -> matching explicit denials -> matching group/user grants with their conditions -> default deny. Any matching denial wins over a grant, including when another group grants it. An added user grant may extend a group's grant but cannot override a matching denial. Evaluate all applicable restrictions for the requested resource/action/context.

AUTH-05: Do not merge conditions from different grants into a broader privilege. Example: approve up to 5% in Dhaka and up to 10% in Chattogram does not allow 10% in Dhaka. A request must satisfy at least one complete allow policy and no applicable deny. Higher monetary thresholds do not cross currency boundaries without the defined conversion policy.

AUTH-06: Custom user examples: salesperson may gain an expiring discount-approval grant, be denied cost visibility and remain restricted to Dhaka. Warehouse manager may release Gazipur shipments without payroll access. A user in both sales and warehouse groups cannot approve their own shipment if separation-of-duties rules forbid it. Explicitly configure substitute approvers; never create silent admin bypasses.

AUTH-07: Provide group editor, membership management, individual override editor, scope/limit selector, expiry/reason fields, change preview and an effective-permissions inspector. The inspector explains grant/deny origin, licence restrictions and context. Protect it against exposing inaccessible company or user metadata.

AUTH-08: Permission administrators may grant only delegated permissions/scopes. Enforce this on group edits, assignments and overrides; bulk endpoints must not bypass it. Protect against self-escalation, removal of the last authorized admin and unauthorized changes to protected templates. Emergency support access is time-limited, explicitly authorized and audited.

AUTH-09: Backend endpoints, query filtering, field serialization, exports, background jobs and sockets use the same policy service. Hidden cost/payroll fields must not leak through aggregate reports or download endpoints. Go invokes ERP authorization; Flutter consumes effective capabilities without becoming the security authority.

AUTH-10: Maintain authorization revision and invalidate relevant caches on changes. Evaluate latest permissions for approvals and destructive actions; queued user-initiated work rechecks access before execution. Server-owned recurring jobs use a defined service identity rather than impersonating an employee indefinitely. Offline clients revalidate during sync and display rejected/conflicting actions.

AUTH-11: Tables: permission_definitions, permission_groups, group_policies, user_group_memberships, user_permission_overrides, authorization_revisions and permission_change_audit. Use tenant-qualified references, constrained effects, explicit scope references and UTC validity fields. Version policy changes enough to explain past approvals without using obsolete permission snapshots to grant current access.

AUTH-12: Tests must cover no-grant denial; multiple-group union; user allow; deny precedence; expired override; disjoint branch limits; disabled feature; cross-tenant identifiers; hidden fields; delegation limits; concurrent policy changes; revoked access in queued/offline actions; and prohibited self-approval. Verify the same results through ERP UI/API and later Flutter workflows.

## 33. Wholesale imports and landed costs — Phase 1

IMP-01: Import shipment groups supplier purchase-order lines and tracks shipment/container references, carrier, origin/destination, milestones, expected/actual arrival, partial receipts and customs status. Support several orders per shipment and one order arriving in several shipments. Track agreed commercial terms and ownership recognition policy; physical receipt and legal ownership are not always the same event.

IMP-02: Documents include commercial invoice, packing list, transport document, customs declaration and clearing/supporting bills with versions, access and links. Tariff/product classification and customs valuation inputs are configurable data requiring jurisdiction validation; no hard-coded global duty formula.

IMP-03: Cost lines cover freight, insurance, duty, clearing, port/storage, inland transport and other approved costs. Capture vendor/bill reference, original currency, exchange-rate source/date, amount, tax classification, estimated/actual status and capitalization decision. Recoverable tax, nonrecoverable tax and ordinary period expense are distinct configurable treatments, validated with accounting/localization requirements.

IMP-04: Landed-cost batch allocates eligible costs to receipt/item valuation layers by value, quantity, weight, volume or approved manual shares. Declare denominator units, source values, rounding/remainder policy and excluded items. Block zero/invalid denominators. Converted allocations plus rounding reconcile exactly to the approved allocable amount; never mix unrelated tenant/company inventory.

IMP-05: Preview -> reviewed -> approved -> posted -> adjusted/reversed. Freeze posted allocation inputs, cost method, exchange rates and policy version. Late invoices replace/reconcile estimates without adding the same charge twice. Duplicate provider events and posting retries must be idempotent.

IMP-06: Late cost adjustments follow the supported valuation method and actual disposition: remaining stock, sold stock/COGS, consumed materials/WIP/finished output as appropriate. Preserve cost-layer lineage; do not simply spread every late bill over whatever quantity remains on hand. Locked periods require an approved current-period adjustment policy. FX settlement differences are distinguished from inventory acquisition cost.

IMP-07: Imports integrate with supplier bills/payments, receipts, partial shipments, damaged/missing goods, claims, purchase returns and finance. Costs are assigned to actual eligible receipts with controls preventing allocation twice across shipments. Allocation preview must expose item unit cost before/after and postings before approval.

IMP-08: Model import_shipments, shipment_purchase_lines, containers/packages as needed, import_documents, import_charges, landed_cost_batches, landed_cost_allocations and valuation_adjustments. Reuse shared bills, tax snapshots, receipts and journal entries. Grant separate permissions to prepare, approve and post landed costs.

IMP-09: Example acceptance fixture, not a tax rule: 100 units costing 100,000 plus eligible freight 10,000 and duty 5,000 yield cost 115,000 or 1,150 per unit. Separately recoverable tax does not increase that fixture's inventory value. Test mixed products/weights, multiple currencies, partial receipts, zero denominator, rounding, estimated-to-actual reconciliation, returns, already-sold units, downstream production, closed periods and duplicate posting.

## 34. Flutter architecture and mobile-ready backend contracts

FLT-01: Flutter/Dart is mandatory for Phase 2. Use feature-organized presentation, application and data layers with typed API models and a shared authentication/network layer. Choose maintained packages after verifying official docs and licences; record the state-management, local database and OIDC package choices in an ADR. No React Native alternative remains in scope.

FLT-02: Phase 1 publishes account-directory contract, authenticated session/profile, company/branch access, effective capabilities, licence status, device enrollment, sync protocol and paginated domain APIs. Public directory responses contain only safe bootstrap metadata; detailed user capabilities are returned after sign-in. Test with API clients before building Flutter screens.

FLT-03: Define sync push with device/operation ID, tenant, resource version, operation type and dependency IDs. Responses distinguish applied, duplicate, rejected and conflict. Define pull cursors, deleted-record tombstones, scope changes, cursor expiry and full-resync recovery. Server time and canonical IDs win; local IDs map safely after acknowledgement. Never resolve stock/financial conflicts using blind last-write-wins.

FLT-04: Encrypt sensitive local data according to platform capability; keep encryption/token material in OS secure storage. Reset and account switching preserve pending-operation ownership and securely separate local stores. Do not send one deployment's access token to another endpoint. Record permission/licence changes in sync outcomes.

FLT-05: Native Android scanner adapters may need platform channels/vendor SDK integration; iOS and Android camera paths require permission/error UX. Test actual hardware, scan suffixes, burst duplicate handling, package units and offline scanning. Do not promise an unsupported hardware model.

FLT-06: Provide role-focused home screens, pending-sync indicators, accessible touch targets, Bangla/English layouts, clear errors and human-readable transaction references. Server-side capability changes update navigation without implying that hidden UI is enforcement. Push/deep-link navigation requires reauthorization.

FLT-07: Phase 2 extends web-tested E2E gates with physical Android/iOS tests and supported warehouse handhelds. Validate tenant switch, PKCE redirects, secure logout, permission expiry, scanner workflows, interrupted uploads, app process death, server upgrades and minimum-version rejection. App signing keys and store credentials are deployment secrets; publication follows explicit release authorization.

## 35. Coding-agent handoff and definition of done

Start by reading this entire document and repository instructions. Return an implementation map for exactly two major phases. Produce ADRs, ERD/table ownership, API contracts, permission matrix, import-cost rules requiring review, licensing lifecycle and a dependency-ordered Phase 1 backlog. Identify missing external credentials/regulatory decisions without inventing them. Preserve existing correct functionality and provide evidence-based estimates only after inspecting scope and code.

Once implementation is authorized, work through Phase 1 milestones in coherent vertical slices. Each completed feature includes migrations/constraints, real domain logic, API, usable web UI where required, authorization/entitlement enforcement, audit, retry/concurrency treatment, tests and operational documentation. Avoid production paths backed only by mock data. Schema changes include migration/upgrade impact and recovery notes. Before calling Phase 1 complete, verify the full catalogue and additions rather than only the core sales flow.

Do not begin production Flutter application implementation until the Phase 1 exit gate is met or the owner explicitly changes sequencing. Phase 1 mobile-ready contracts and hardware feasibility documentation are permitted and required. In Phase 2 reuse ERP business APIs; never recreate accounting, tax, stock or payroll authority on the device.

Deliver a phase status report listing implemented, verified, partial, blocked and deferred requirement IDs; test commands/results; screenshots or walkthrough evidence for business flows; deployment instructions; remaining risks; and proposed next milestone. This document specifies planned software and does not imply that any application has already been built.

## 36. Dynamic approval workflow engine — Phase 1 detailed specification

### Purpose and boundaries

WFL-01: Build a shared, tenant-configurable approval engine used by invoices, quotations, purchase orders, expenses, stock adjustments, loading/dispatch, payroll, repairs, document signing and other registered operations. This extends APR-01; individual modules must not each implement incompatible approval engines. Approval authorizes a specific action on a specific resource revision; it is not itself a journal posting, stock movement or signature.

WFL-02: Separate the engine from domain execution. The module validates the requested transition, requests approval, and later rechecks prerequisites when executing the approved action. No workflow can bypass licensing, tenant isolation, current authorization, financial period locks, stock constraints or mandatory segregation of duties. Saving a draft invoice is different from posting or issuing it.

### Definition model and admin builder

WFL-03: Initial UI is a form-based builder with a readable preview. Provide name, module/resource/action, company/branch applicability, trigger, conditions, priority, stages, approver selectors, quorum, rejection policy, deadlines, reminders, delegation/escalation rules and completion action. Drag-and-drop visualization may follow; do not make it a dependency for a functional workflow.

WFL-04: Workflow definitions have draft, published and retired states and immutable published versions. Validate before publishing: reachable terminal states, valid condition types, valid registered actions, stage dependencies, satisfiable group configuration, delegation cycles, timeouts and no unsupported executable code. Initial stage graph is acyclic; rework creates a new submission/revision rather than an unbounded graph loop.

WFL-05: Conditions use a restricted typed expression tree over approved fields: amount/currency, discount, document type, branch, company, customer classification or other registered fields. Allow comparisons and AND/OR groups with explicit null semantics. Do not use Python eval, raw SQL, arbitrary scripts or user-controlled method names. Monetary comparisons declare currency/conversion rules and freeze relevant rule inputs.

WFL-06: If several published definitions match, choose via documented priority/specificity or explicit ordered composition. Equal-priority ambiguity fails validation/submission; it must not silently select an arbitrary workflow. A required approval action with no matching configuration blocks with a configuration error. An optional action may proceed only under an explicit no-approval policy, never merely because resolution failed.

### Approval semantics

WFL-07: Support sequential stages, parallel stages, ALL, ANY and N-of-M quorum. Approvers can be named users or eligible groups filtered by company/branch, department, reporting relationship and permission. Only distinct authorized people count. Same person in two groups is one person, and repeated requests do not create extra votes.

WFL-08: Support alternative approval paths. For the invoice example, route A requires two distinct eligible salespeople; route B requires one eligible sales manager; either route may satisfy the stage. The creator cannot approve where self-approval is prohibited. A person meeting both roles must not receive artificial double credit. Model alternatives explicitly as OR of quorum clauses, not as an ambiguous threshold across all voters.

WFL-09: Proposed example rejection policy: any valid rejection closes the request as rejected; creator must revise/resubmit. Offer separately defined branch-only rejection where needed; if that policy leaves no satisfiable alternative, reject or enter an explicit exception state. Once a valid route completes, cancel remaining pending tasks atomically. Decisions arriving after terminal completion are rejected as stale. Serialize races between approve/reject so the first valid committed terminal transition wins; show the final state to later callers.

WFL-10: Snapshot workflow version, protected resource revision/hash, triggering facts and candidate assignment at submission. Recheck each approver's live authorization before accepting a decision. If candidates leave or lose access, an authorized reassignment/escalation records the change; do not silently approve or reinterpret historical votes. Define expiry of pending tasks.

WFL-11: Delegation is scoped, time-bound, authorized and audited. Verify delegate authority and self-approval restrictions, prevent cycles, and retain original/delegate identities. Timers may notify or escalate but must not auto-approve. Missing approvers enter an exception queue owned by an authorized workflow administrator.

WFL-12: Comments/reasons are required for rejection, cancellation, exceptional reassignment and manual intervention. Attachments follow the document service's permissions. All operations preserve evidence and cannot rewrite previous decisions.

### Runtime states, revision protection and execution

| Object | States and meaning |
|---|---|
| Request | pending, approved, rejected, cancelled, expired, invalidated, exception |
| Stage/task | waiting, active, approved, rejected, cancelled, expired, reassigned |
| Domain execution | not_requested, queued, running, succeeded, failed_retryable, failed_final |

WFL-13: Approved does not mean the domain action succeeded. Track execution separately and show failures. If posting prerequisites change after approval, block/revalidate or invalidate according to policy; do not post simply because a prior approval exists.

WFL-14: Protected fields are defined by each domain adapter. Invoice quantities/prices/taxes, payroll inputs, payment destination, shipment batches/serials and signing document bytes are protected examples. A material change invalidates pending/approved authorization for that revision. Harmless comments may be excluded explicitly. Resubmission starts a new request linked to its predecessor; completed history remains immutable.

WFL-15: Record approval decision and associated events transactionally. Use row locking or optimistic concurrency, a unique voter identity constraint and idempotency keys. Execute same-database actions atomically where appropriate; use outbox/consumer deduplication for asynchronous/external actions. A worker retry cannot post the same invoice or release stock twice.

WFL-16: Reminder/escalation workers use persisted due times and unique timer event keys. Only still-active tasks are eligible. Define tenant time zone, business hours, DST handling and overdue policy. A delayed reminder after approval is a no-op. Notifications are delivery aids, never authorization evidence.

### Logical schema and APIs

Use a module-owned workflow schema or clearly owned tables consistent with the repository:
- workflow_definitions: tenant, identity, module/resource/action, lifecycle.
- workflow_versions: immutable definition, predicates, precedence, published actor/time.
- workflow_stages/clauses: dependencies, selector and quorum definitions; may be normalized or validated version JSON.
- workflow_requests: tenant/company/branch, resource type/ID/revision/hash, version, initiator, state, timestamps.
- workflow_tasks: stage/clause, principal, role snapshot, status, due time, delegate/reassignment linkage.
- workflow_decisions: request/task, actor, decision, reason, idempotency and evidence timestamp.
- workflow_events: append-only assignment/decision/state history.
- workflow_timers: due event, unique identity, status.
- workflow_action_executions: approved action, idempotency identity, domain result and retry outcome.

WFL-17: Provide APIs for definition drafts/validation/publication/retirement; resource submit/cancel/resubmit; filtered inbox; request timeline; task approve/reject; authorized delegation/reassignment; preview/simulation; and execution status. Proposal: /api/v1/workflows/definitions, /requests, /tasks and /inbox. Adapt names to repository conventions. Never expose a generic endpoint that accepts arbitrary domain action names without a registry/permission check.

WFL-18: Decision requests carry decision, reason where required, expected request/resource revision and idempotency key. Return current state and a stable conflict code on stale approval. Preview must have no business side effects and must label hypothetical membership resolution. An inbox shows only permitted metadata, especially for payroll/finance documents.

WFL-19: Add workflow permissions for edit, publish, preview, submit, decide, delegate, reassign and audit. Permission-group editors cannot use workflow selectors to grant themselves domain approval rights. Phase 1 provides admin builder, requester status/timeline, approver inbox and exception queue. Phase 2 Flutter reuses these APIs.

### Required acceptance scenarios

- Two distinct authorized salespeople approve an invoice: stage completes exactly once.
- One salesperson alone does not meet the quorum; creator approval and duplicate vote are rejected.
- One authorized manager completes the alternative route and remaining tasks close.
- Stale/wrong-branch/deactivated-user decisions fail even if the user saw the task earlier.
- Concurrent second approval and rejection result in one consistent terminal state.
- Protected document changes invalidate approval; retries cannot post the new revision under the old request.
- Publication of a newer definition does not silently alter in-flight requests.
- No eligible approver and ambiguous workflow matches produce visible exceptions rather than auto-approval.
- Group membership, user deny overrides and licence rules apply consistently.
- A domain execution failure remains visible after approval and resumes idempotently.

## 37. DocuSign-style document signing — Phase 1 detailed specification

### Product scope and assurance

ENV-01: Implement an envelope-based document signing experience integrated with ERP workflows: prepare documents, assign recipients and fields, route signing, track progress, retain completed documents and evidence. This describes desired functionality, not affiliation with or complete feature equivalence to a named vendor.

ENV-02: Separate basic electronic signing, identity verification and certificate-backed digital signatures. Drawing/typing a signature and hashing a PDF do not alone prove identity or provide certificate-backed signing. Introduce provider adapters where stronger signing/verification is required. Do not claim legal suitability for every market; retain country/document-type validation as a release requirement.

ENV-03: Build our own envelope management and document-preparation UI. Support an explicitly described native electronic-signing mode and/or approved provider-backed mode, selected per policy. Expose supported capabilities; block a request requiring an assurance level unavailable in that deployment. Client-hosted provider mode may transmit documents externally only under configured authorization. Restricted installations must not pretend external signing occurred while disconnected.

### Preparation and envelope model

ENV-04: Upload PDFs or generate PDFs from versioned ERP templates. Malware-scan inputs, enforce size/page limits, handle encrypted/unsupported PDFs explicitly, and render page previews. Preserve immutable original bytes and a cryptographic digest. Conversion from other formats must produce a frozen reviewable PDF; conversion is not a licence to alter signed files.

ENV-05: Envelope contains one or more ordered document versions, recipients, field placements, subject/message, expiry/reminder rules, verification policy, routing and source business reference. Source a snapshot of an approved business document; do not point signers at mutable live invoice rendering.

ENV-06: Field designer supports signature, initials, signing date, text, checkbox and approved optional field types. Store document ID/page, normalized coordinates, page rotation/size, field type, required/read-only status, recipient assignment, validation and prefill provenance. Validate page bounds, missing recipients and required fields before send. Test rendering under zoom and different screen sizes.

ENV-07: Recipient roles include signer, internal countersigner and copy recipient. Copy recipients do not count as signers. Support sequential routing, parallel recipients within a stage and mixed stages. Default completion requires all required signers; exceptional optional-signature rules must be explicit. Workflow approval quorum does not imply signing quorum.

ENV-08: External signers need no ERP account, but secure invitation and configured verification are required. Use high-entropy expiring tokens stored as hashes, purpose-limited signing sessions, rate limits and replay controls. Token refresh/resend rotates or manages previous links according to policy. Never trust recipient identifiers supplied by the browser without session binding. Email link possession and OTP assurance must be described accurately; OTP to the same email is not automatically an independent authentication factor.

ENV-09: Signing UX shows sender/business identity, documents, consent text/version and required fields. Signer reviews, consents, completes fields and explicitly submits. Offer typed/drawn/uploaded signature appearance only as supported; appearance is distinct from identity assurance. Signer decline captures reason. Changes to recipient identity require an audited correction/new request policy and cannot reuse an old verified session silently.

### State and evidence handling

| Object | Lifecycle |
|---|---|
| Envelope | draft -> pending_internal_approval (when required) -> ready -> sending -> sent -> in_progress -> finalizing -> completed |
| Alternate envelope states | delivery_failed, declined, expired, voided, finalization_failed |
| Recipient | pending, notified, viewed, verification_pending, ready_to_sign, signed, declined, expired |
| Evidence/artifact | original, prepared, provider intermediate if applicable, completed, audit_report |

ENV-10: Viewing is a recipient event; one viewed document does not mean the envelope is signed. All required signatures initiate finalization. Mark completed only when final documents and evidence have been verified and durably stored. Provider callbacks may be delayed, duplicated or out of order; reconcile provider status and never overwrite a valid terminal state with a stale event.

ENV-11: Material content changes after approval require new approval. Changes after sending must follow a controlled void-and-replace or provider-supported correction policy preserving history. Completed signed originals are immutable; corrections create linked versions/envelopes. Once voided/expired, further signing must be rejected even through an old invitation link.

ENV-12: Record actor/recipient identity reference, assurance method/outcome, consent version, server timestamps, document digests, routing, delivery/view/sign/decline events, delegations/corrections and final artifact provenance. Collect IP/device metadata only under defined privacy/retention policy; it is supporting evidence, not conclusive identity. Evidence report includes verification instructions and does not call itself a qualified certificate unless that is actually provided.

ENV-13: For native mode, freeze all signer-entered values and bind each acceptance to a document-set digest and recipient action. Define deterministic assembly and custody rules. Appending later signature appearances must not obscure what earlier signers agreed to. For certificate-backed modes, use provider-supported incremental signing/validation; do not flatten, merge, stamp or regenerate final PDFs in a way that invalidates signatures. Store final provider originals unchanged.

ENV-14: Hashes detect changed bytes when compared to trusted evidence; hashes stored beside mutable files do not alone create an independent trust anchor. Protect audit storage and signing evidence with access controls, append-only practices and appropriate retention/immutability facilities. Track verification failures and artifact fetch failures explicitly.

### Workflow integration

ENV-15: Typical flow: ERP draft -> internal approval against frozen revision -> create/send envelope -> customer signature -> authorized internal countersignature -> finalized evidence -> domain completion event. Internal approval is not a legal signature, and a signature does not automatically authorize unrelated stock/financial operations.

ENV-16: Registered workflow actions may prepare/send an envelope or wait for completed/declined/expired events. Persist waiting state; do not hold a Celery process or database transaction open for days. On completed event, revalidate domain rules and use an idempotent action execution record. Prevent circular workflow-to-envelope triggers.

ENV-17: Reminders and expiry are persisted timers with tenant time-zone handling and provider ownership rules. Avoid duplicate reminders from provider and ERP. Recipient notification failure is visible and retryable. Notifications/OTP require the corresponding configured channel; no silent downgrade from required verification.

### Tables and service boundaries

- signing_templates and signing_template_versions: document/field/routing presets with immutable publication.
- signing_envelopes: tenant, business source/revision, policy, provider, status and idempotency identity.
- envelope_documents: ordered immutable document versions, hashes and storage references.
- envelope_recipients: role, stage, contact reference, verification policy, state.
- envelope_fields and field_values: geometry, type, assigned recipient, validations and frozen submitted values.
- signing_sessions: hashed invite/session references, scope, expiry and invalidation; no raw token logs.
- signature_acceptances: recipient, content digest, consent/version, verified session and timestamp.
- envelope_events: append-only lifecycle/evidence events.
- provider_transactions and provider_webhook_receipts: external IDs, deduplication and reconciliation.
- completed_artifacts: immutable PDF/evidence references, digest, fetch/validation outcome.

ENV-18: Provider interface supports capability discovery, envelope submission, recipient-session initiation where supported, status retrieval, voiding, final document/evidence retrieval and authenticated event normalization. Each adapter documents idempotency, rate limits, status mappings, verification method and limitations. Credentials are tenant/deployment scoped secrets; no provider secret ships in Flutter/browser clients.

ENV-19: Proposed internal APIs: templates/version publication; envelope create/update/validate/submit-for-approval/send/status/void/resend; recipient status; completion downloads and audit timeline. Proposed external APIs: token exchange, recipient-scoped document fetch, verification, consent, field submission, sign and decline. Do not expose global ERP APIs to external signers. Use short-lived authorized downloads; scope object-store access to specific artifacts.

ENV-20: Permissions include prepare, send, void, view audit, view original/final, manage templates, manage provider credentials and countersign. External access is restricted to explicitly assigned documents; hide other recipients' unnecessary personal information and internal approval comments. Copy-recipient delivery follows the configured completion stage.

### UI and acceptance

Phase 1 includes envelope dashboard, multi-document editor, recipient/routing editor, field placement designer, preview/validation, internal approval linkage, secure responsive external signing page, progress timeline, resend/void actions and final downloads. Phase 2 adds Flutter review, request tracking, authorized approval and a supported provider/native signing handoff; do not build a second independent signature engine in Flutter.

Tests must cover multi-page geometry/rotation, two PDFs and mixed routing, required/optional fields, external access isolation, expired/rotated tokens, repeated submit, parallel signers, wrong-recipient session, verification failure, declined/voided requests, approval invalidation, provider downtime, duplicate/out-of-order callbacks, failed artifact finalization, altered bytes, preserved certificate-backed PDFs where supported and exactly one domain completion action. Maintain evidence fixtures with no real personal data.

## 38. Integration milestones, traceability and review package

Add the workflow registry, policy validation, request/decision runtime and outbox integration to P1.1; deliver the first real invoice approval in P1.4 and reuse for expenses, stock, payroll and dispatch. Deliver envelope/template/editor/external signing and workflow integration in P1.7. Validate provider adapters and assurance claims before P1.9. Add mobile inbox, document tracking and supported signing handoff in P2.2; physical-device security and compatibility verification remain P2.5.

Coding-agent design package must include:
1. Workflow and envelope ERDs with tenant-qualified keys and ownership.
2. Exact state-transition tables, allowed actors, concurrency locks and error outcomes.
3. Permission/entitlement mapping for every action and field-sensitive view.
4. OpenAPI contracts and idempotency/optimistic-version conventions.
5. A domain adapter registry for approvals and a capability-based signing-provider interface.
6. Golden test definitions for two-salespeople-OR-manager approval and mixed document signing.
7. Threat review covering invite theft, cross-tenant access, stale approval, malicious configuration and provider replay.
8. Operator procedures for no-approver queues, failed posting, stuck envelopes, key/provider rotation and evidence export.

Do not turn these design deliverables into an indefinite planning exercise: once the implementation plan is authorized, build the first vertical slice (draft invoice -> policy selection -> quorum -> protected post), verify it, then extend the same engine. Build signing as a separate bounded capability connected by durable events. Keep the two-major-phase mandate and all existing requirements intact.

## 39. Revision 2.1 handoff

This document is the full consolidated coding specification. Sections 36–38 expand shared approval/signing requirements rather than replacing the existing ERP, licensing, import-cost, permission, warehouse, restaurant or Flutter requirements. Fixed choices are FastAPI ERP, Go website backend, Keycloak identity and Flutter Phase 2. Proposed libraries and infrastructure defaults must be verified against the repository and official documentation when implemented. No source repository implementation or deployment is implied by this documentation deliverable.

## 40. B2B customer account and self-service portal — Phase 1

B2B-01: A tenant's business customer can have its own portal account with multiple named users. Distinguish the ERP subscribing tenant/account from the tenant's B2B buyer organization; a buyer login does not create a new ERP tenant or grant employee access. Maintain separate buyer memberships and policies. Link identities by issuer/subject, never email alone.
B2B-02: Portal supports customer/company profile, approved delivery/billing addresses, authorized contacts, searchable permitted catalogue, wholesale pricing, quantity/pack rules, product-order submission, quotations, attachments/customer PO reference, draft orders, reorder and status tracking. Stock visibility is configurable; reservation and final price/credit checks remain server-owned.
B2B-03: Buyer roles include organization administrator, purchaser, approver and finance viewer/payer, with configurable access to buyer branches/cost centres. Optional buyer purchase approval precedes seller acceptance and must be a separately scoped workflow. Seller staff permissions cannot be inherited by customer users.
B2B-04: Show prior orders, order lines, invoices, credit notes, split deliveries, outstanding balances, overdue invoices, credit limit/available credit where authorized, deposits/unallocated credits, payment history, refunds and downloadable customer statements. Explain currency and as-of date. No single summed balance across currencies without an explicit converted presentation.
B2B-05: Balance is derived from posted receivable entries and allocations, not an editable profile field. Separate unconfirmed transfers from confirmed credit. Pro forma/order documents are not posted receivables. Define how reservations and unbilled orders affect credit exposure. Imported opening balances require provenance and authorization.
B2B-06: Authorized buyers pay invoices partially or in full, pay several invoices together, submit transfer references/evidence and view reconciliation progress. Uploading a bank receipt is evidence awaiting review, not automatic payment confirmation. Handle overpayments as controlled unallocated credit/refund rather than quietly changing invoice value.
B2B-07: Audit buyer user invitations, role changes, orders and payments. Enforce account suspension, credit holds and pending verification through direct APIs. Customer documents/downloads/search must be buyer-scoped within the seller tenant.

Tables: buyer_organizations, buyer_memberships, buyer_role_policies, buyer_addresses, customer_credit_policies and transfer_claims, linked to existing customer/order/receivable/payment models. Customer statements are projections of the ledger, not a second authoritative balance table.

## 41. Shared B2B/B2C payment architecture — Phase 1

PMT-01: Support local and international payment options through configurable provider adapters for B2B portal, B2C eCommerce and applicable POS flows. Manual bank transfer is a first-class method; online gateways, mobile wallets, cards and cash-on-delivery are enabled where supported by the selected merchant/provider arrangement.
PMT-02: Do not assume any named provider supports all countries, settlement currencies, subscriptions, refunds or payment methods. Before implementation verify official APIs, merchant onboarding, sandbox, signature checks, supported currencies, settlement files and refund/chargeback capabilities. Provider selection and commercial terms remain open; local/international support is an architecture requirement, not a claim of merchant eligibility.
PMT-03: Configure credentials and bank/settlement accounts per tenant/legal company. These are customer merchant payments, distinct from our software-subscription billing. Do not route all merchants' funds through the vendor account without a separately approved marketplace/payments model.
PMT-04: Use a canonical payment intent/attempt/transaction model, allocation ledger and settlement records. Track initiated, pending, authorized, captured/confirmed, failed, cancelled, partially_refunded, refunded and disputed states as appropriate; preserve provider-native status/events. Separate customer payment confirmation from provider payout to the merchant bank.
PMT-05: Server computes payable amount/currency and verifies all callbacks. Browser redirects do not mark an order paid. Use idempotency for initiate/capture/refund and unique provider transaction identities within merchant scope. Reconcile out-of-order/missing callbacks using supported status queries or settlement imports.
PMT-06: Hosted/tokenized checkout is preferred; do not store raw card numbers or security codes. Keep provider secrets server-side. Support server-authorized partial payments, invoice allocations, overpayments, fees, FX and partial refunds. A refund does not automatically restock goods or void an entire invoice.
PMT-07: Notify customers of pending/confirmed/failed payments with truthful status. Unknown payment outcomes require reconciliation, not an immediate new charge attempt. Set rules for stock reservation expiry followed by late successful payment.
PMT-08: Provide adapters/interfaces for create attempt, status query, refund where supported, authenticated webhook normalization and settlement import. Manual-transfer adapter relies on approved statement reconciliation. Each method advertises capabilities rather than pretending every provider supports webhooks or refunds.

## 42. Manual bank statements, reconciliation and later corrections — Phase 1

BNK-01: For launch banks/accounts without an available reliable API/webhook, operate through uploaded statements and controlled reconciliation. This is our configured operating assumption for those accounts, not a universal claim about all Bangladesh banks. Future API feeds must use the same canonical bank-transaction and matching model.
BNK-02: Start with agreed CSV/XLSX statement profiles and mapping preview for date/value date, debit/credit or signed amount, currency, description, bank reference and running balance where present. Preserve original file, checksum, source/account/period, uploader and parser version. PDF/OCR is optional and requires human verification before posting. Reject malformed files, unsafe content, invalid amounts and mismatched account/currency.
BNK-03: Import lifecycle: uploaded -> parsed -> validated -> reviewed -> committed, with rejected/partial-error states and explicit per-row outcome. Preview rows and errors; verify available opening/closing totals. Do not silently skip rows or overwrite previous transactions.
BNK-04: Detect duplicate files and overlapping statement periods. Prefer stable bank transaction ID within bank-account scope. When absent, use normalized references/amount/date and contextual evidence to propose duplicate candidates; identical amounts/dates can be legitimate separate transfers. Ambiguous duplicates require review; a hash-only heuristic cannot guarantee transaction uniqueness.
BNK-05: Normalize statement lines independently of customer allocation. Classify customer receipts, supplier payments, internal transfers, fees, interest, reversals and unknown items. Never treat every bank credit as a customer payment. Matching proposes customer/invoice based on trusted reference, amount, currency, account and available evidence; ambiguous matches remain unallocated.
BNK-06: Reviewer can split one bank receipt across invoices, combine several receipts for one invoice or leave unapplied credit. No allocation exceeds available receipt value or invoice balance without explicit overpayment/FX treatment. Segregate import, match and posting approval where configured; use dynamic workflow for thresholds/exceptions.
BNK-07: Distinguish a customer-declared transfer from a statement-supported receipt. Proposed matches do not update posted customer balances. Approved posting creates/link-confirms the payment and journal effects exactly once; only then do receivable allocations change. Unidentified bank money can use an approved clearing/suspense treatment without crediting an arbitrary customer.
BNK-08: When a newer statement or future API feed arrives, link overlapping evidence to the existing canonical transaction. Add genuinely new transactions; mark disputed/corrected evidence for review. Never create a second customer receipt simply because the same payment appears in a new file or API source.
BNK-09: Correct posted errors with an authorized reversal/unmatch/reallocation chain, preserving original records and audit. Apply period-lock policies. A removed line in a later statement is not automatic proof that a real transfer was reversed; explicit bank reversal/correction evidence and review are needed. Notify customer only after the resulting confirmed adjustment.
BNK-10: Reconcile gateway settlements and direct bank transfers differently. A net gateway payout links to gross customer payments less fees/refunds; it must not credit those customer invoices again. Internal bank-to-bank transfers require both sides without classifying revenue. Track reconciliation difference and aging unresolved items.
BNK-11: APIs/UI cover import profiles, preview/errors, duplicate review, statement lines, suggested matches, confirmed allocations, approval/posting, undo via controlled adjustment and reconciliation reports. Stable operation IDs, row/version checks and database constraints prevent duplicate allocations under concurrent reviewers.

Tables: bank_accounts, statement_imports, statement_lines, canonical_bank_transactions, transaction_source_links, reconciliation_matches, payment_allocations, reconciliation_adjustments and feed_cursors. Reuse existing payment/journal models; avoid parallel authoritative financial ledgers.

Acceptance: upload same file twice; upload overlapping months; import two genuine same-day same-amount transfers; allocate partial/multiple invoices; correct a wrong customer; handle a reversal; match a gateway net payout; introduce API records already seen in files. All cases preserve audit and produce no duplicate customer credits. Posted balance changes must reconcile to journals and allocations.

## 43. Wholesale/retail prices and customer-specific offers — Phase 1

PRC-01: Provide at least wholesale and retail price-list types with explicit customer assignment, company/storefront/channel, currency, UOM/packaging, quantity breaks and effective dates. B2B default is wholesale where assigned; B2C default is retail. A caller cannot switch a flag to obtain unauthorized wholesale prices.
PRC-02: Customer-specific contract prices and additional percentage/fixed discounts/offers have eligibility, product/category scope, quantity/minimum-spend conditions, validity, currency and approval/audit. Label account-specific negotiated prices distinctly from general promotions.
PRC-03: Define deterministic calculation precedence: select applicable permitted base/contract price, apply eligible adjustments in configured priority and stacking groups, resolve exclusive offers, then apply the jurisdiction-approved discount/tax calculation treatment. Explicitly state whether a contract price replaces the wholesale/retail base and whether customer/loyalty/coupon discounts stack. Do not silently apply every discount together.
PRC-04: Preview explains base, rule IDs, discount lines, tax treatment and final amount. Snapshot rule versions on accepted orders/invoices; later price changes do not rewrite history. Server revalidates checkout and quote expiry. Manual exceptions require delegated limits and workflow approval.
PRC-05: Protect cost/margin fields from customer/sales roles without permission. Configure price floors and discount limits as business policy; block or route exceptions. Test returns using original transaction discount/tax allocation rather than current promotions.

## 44. Tiered B2B and B2C loyalty — Phase 1

LOY-01: Support separate configurable programs for B2B buyer organizations and B2C customers, with multiple levels, qualification rules, earning/redemption, benefits and effective dates. Example tier names are not fixed commercial commitments. B2B ownership is the buyer organization by default, not personal rewards to its purchasing employee; authorize who can redeem on the organization's behalf.
LOY-02: Rules specify eligible spend/orders, qualification window, excluded tax/shipping/items, currencies, paid/fulfilled requirement, pending period, points expiry, upgrade/downgrade timing, caps and stacking with customer discounts. No implicit mixing of monetary values across currencies. Configure tiers independently from software subscription packages and wholesale/retail price lists.
LOY-03: Use append-only loyalty ledger entries for pending earnings, vested earnings, redemption reservations, committed redemptions, releases, expiry and reversals. Stable event IDs prevent double earning. Concurrent checkout cannot spend the same points twice. Returns/partial refunds proportionately reverse benefits using original rules; spent-point reversals follow a defined negative-balance/recovery policy.
LOY-04: Mark points earned from unconfirmed bank-transfer orders as pending when applicable. Vest only at the configured confirmed business milestone. Statement corrections can trigger controlled loyalty adjustments; never silently delete history.
LOY-05: Tier benefits can include eligible discounts, shipping offers or service benefits. ERP pricing engine evaluates monetary benefits consistently in portal, website and POS. Redemption treatment and associated accounting/liability policy require financial review, especially across countries; do not claim points are cash automatically.
LOY-06: Customer portal shows level, progress/window, available/pending points, expiry and history. Administrators manage versioned programs and audited adjustments. Fraud controls cover self-dealing, duplicate identities, abuse of returns and unauthorized B2B redemption.

Tables: loyalty_programs, program_versions, tiers, qualification_rules, memberships, loyalty_ledger, redemption_reservations and tier_history; link source order/payment/return events for reconciliation.

## 45. Customer email marketing, notifications and optional SMS — Phase 1

MSG-01: Email transactional notifications and email marketing are explicit scope; SMS is optional by tenant subscription/configuration and recipient eligibility. Examples: order acknowledgment, approval outcome, shipment updates, invoice, payment confirmation, statement availability, return/repair status and loyalty changes.
MSG-02: Distinguish service/transactional communication from marketing purpose. Marketing requires appropriate recorded consent/preference and unsubscribe/suppression handling under the applicable market rules. Disabling marketing must not indiscriminately suppress necessary permitted account/security messages. Do not label promotional messages transactional to bypass consent.
MSG-03: Versioned Bangla/English templates and tenant/company branding, sender identity verification, recipient locale, safe merge fields, previews and test sends. Do not place sensitive balances/payroll or access tokens in indiscriminate group messages; use authorized portal links as appropriate.
MSG-04: Event-driven outbox/jobs, recipient preferences, idempotent sends, rate limits, retries, bounce/complaint handling, delivery logs and provider callback verification. Network failure after send may create an uncertain result; reconcile where provider supports it instead of claiming universal exactly-once delivery.
MSG-05: Marketing campaigns support audience segmentation, scheduling, exclusions, customer-type/tier segments, approval, opt-out and delivery/conversion reports. Segmentation must obey tenant/customer access and consent; no cross-tenant lists. SMS shows configured usage/cost limits and requires an enabled provider, approved sender and opt-in where applicable.
MSG-06: Keep provider credentials tenant-scoped, validate webhooks and redact content/tokens in logs. Signing OTP and marketing are separate message purposes with separate security and preference rules.

## 46. Delivery mapping and new release gates

All features in sections 40–45 belong to Phase 1 web/ERP delivery. Add pricing foundation to P1.2, payment and bank reconciliation foundation to finance/P1.2–P1.4, B2B portal/shared checkout to P1.6, and loyalty/email campaigns to P1.8. Validate the complete integration at P1.9. Phase 2 Flutter uses these same services for approved staff tasks; B2B buyer access with web-portal feature parity is confirmed Phase 2 scope; only B2C consumer Flutter access remains undecided. Both B2B/B2C web portals are confirmed Phase 1 scope.

Required gates: B2B organization user cannot see another customer's orders/balance; wholesale pricing cannot be accessed by changing client parameters; customer offers and tier benefits follow explicit stacking; concurrent redemption is safe; bank reimports and future API overlap produce one canonical payment; customer transfer claim remains pending until authorized confirmation; provider redirects cannot mark paid; marketing unsubscribes suppress future campaigns; optional SMS disabled produces no SMS jobs. Publish reviewed pricing, statement and loyalty examples alongside tests.

Revision 2.2 incorporates these additions into the existing two-phase scope. Bank-statement reconciliation starts manually where required and is deliberately designed for later automated feeds without double posting. Selected payment/bank/message providers and their real statement formats must be supplied or verified during implementation, not invented by the coding agent.


## 47. Shared Flutter B2B customer workspace — confirmed Phase 2

BMA-01: The same Android/iOS app serves staff and B2B customer users. No separate buyer app or per-client build is required. The seller client account number resolves the ERP deployment; the individual buyer user authenticates through Keycloak and is authorized through buyer organization membership. Seller tenant account number and B2B buyer organization/customer number are distinct identifiers. A customer number alone never grants access.

BMA-02: After authentication, present only authorized workspaces. A buyer sees the permitted buyer organization(s), delivery locations and buyer functions. A person who legitimately has both staff and buyer memberships explicitly switches workspace; memberships do not merge into broader permissions. Tenant, buyer organization and workspace context must scope tokens/session context, caches, queued operations and notifications. Retain server-side authorization on every request.

BMA-03: Deliver the same business features as the Phase 1 B2B web portal: approved catalogue/search; wholesale/customer prices and offers; quantity/pack rules; drafts, quotations and order submission; customer PO attachments; reorder; buyer purchase approvals where configured; partial/split delivery tracking; invoices and credit notes; outstanding/overdue balances; credit exposure where authorized; payment/refund history; downloadable statements; returns/repair requests and tracking where enabled; buyer profile/addresses and delegated user administration; tier/points/reward history and redemption.

BMA-04: Payment flows include invoice selection, partial/multiple-invoice payment, supported local/international provider handoff, manual-transfer reference and evidence upload, and reconciliation status. Use provider-supported secure browser/SDK flows; verify outcomes on the ERP. Do not store card data or mark paid from a mobile redirect. Buyer receipt upload does not grant bank-statement import or finance reconciliation permission. Only authorized seller staff import/reconcile bank statements.

BMA-05: Show as-of timestamps and connectivity state for balances, credit availability, prices, points and order status. Permit offline browsing/draft entry only for explicitly cached authorized data. Final price/stock/credit checks, order acceptance, payments, loyalty redemption and buyer approvals require server validation. Revalidate drafts on reconnect and explain changes; do not silently submit changed totals.

BMA-06: Customer push/email/SMS preferences and notifications reuse the messaging services. Push/deep links are scoped to the correct seller/buyer workspace and reauthorize after opening. Display payment awaiting verification separately from paid. Logout and workspace/account switching must not disclose prior buyer documents or move draft/evidence uploads into a different organization.

BMA-07: Update P2.2 to include the full B2B customer workspace and portal parity; P2.4 covers isolated buyer drafts and safe reconnect; P2.5 includes buyer UAT. Compare mobile/web features using a parity matrix rather than assuming staff mobile screens satisfy customer needs. Reuse all pricing, tax, payments, balances, loyalty and workflow APIs; no parallel mobile business ledger.

Acceptance: one shared build signs in as seller staff and as two separate buyer organizations with different catalogues/prices and permissions; each buyer sees only its records. A buyer can order, reorder, track split fulfilment, view statements, pay through a supported provider, submit transfer evidence and use eligible rewards. Staff cost/stock-adjustment/payroll/reconciliation endpoints remain inaccessible to buyers. Duplicate submit/payment callbacks do not duplicate orders or credits. Switching account/workspace, stale offline price, expired permissions and notification deep links preserve isolation. Phase 2 cannot be marked complete while B2B portal parity is missing.

Revision 2.3 confirms B2B buyers in the shared Flutter application. B2C eCommerce web support remains confirmed; B2C consumer mobile shopping has not been added implicitly.
