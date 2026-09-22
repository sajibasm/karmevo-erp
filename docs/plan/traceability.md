# Requirement Traceability Matrix

Generated from `ERP_Coding_Agent_Requirements.md` v2.3 on 2026-09-21. One row per requirement ID. Update the **Implementation** and **Test evidence** columns as slices land; status values: `planned`, `in-progress`, `implemented`, `verified`, `partial`, `blocked`, `deferred` (deferral requires explicit scope agreement).

Total IDs: 276

| ID | Requirement (first clause) | Milestone | Implementation | Test evidence | Status |
|---|---|---|---|---|---|
| ARC-01 | Organize FastAPI into platform, catalogue, sales, purchasing, inventory, manufacturing, restaurant, tax, fi… | P1.1 | `erp/core/modules.py`, `erp/module_catalog.py`, `erp/modules/*/module.py` | `tests/core/test_modules.py` | partial |
| ARC-02 | Keep authoritative pricing, tax, reservations, orders, stock, payroll and accounting logic in the ERP. | P1.1 | — | — | planned |
| ARC-03 | Use database transactions for business changes requiring atomicity. | P1.1 | `erp/modules/integration/outbox.py` | `tests/outbox/test_outbox.py` | partial |
| ARC-04 | Separate business runtime from SaaS administration. | P1.1 | — | — | planned |
| ARC-05 | Extract services only for demonstrated independent scaling, ownership or isolation needs. | P1.1 | — | — | planned |
| ARC-06 | Version REST APIs and publish OpenAPI schemas. | P1.1 | `erp/core/errors.py`, `erp/shared/schemas.py`, `erp/modules/platform/controller.py` | `tests/core/test_errors.py`, `tests/shared/test_schemas.py`, `tests/platform/test_context_api.py` | partial |
| TEN-01 | Model tenant/business account, legal company, branch, warehouse and user membership separately. | P1.1 | `erp/modules/platform/registry_models.py`, `models.py` | `tests/platform/test_registry.py` | partial |
| TEN-02 | SaaS may use a shared database with tenant-scoped constraints and row-level security. | P1.1 | `erp/modules/platform/provisioning.py`, `tenant_db.py`, `migrations/tenant/*` | `tests/platform/test_provisioning.py`, `tests/platform/test_tenant_isolation.py`, `tests/core/test_db_roles.py` | partial |
| TEN-03 | Scope database queries, cache keys, object storage access, jobs, exports, search, sockets, notifications an… | P1.1 | `erp/modules/platform/context.py`, `dependencies.py` | `tests/platform/test_context_api.py` | partial |
| IAM-01 | Keycloak handles authentication, SSO, MFA, reset and federation. | P1.1 | — | — | planned |
| IAM-02 | Validate issuer, signature, audience, expiry and appropriate token claims; | P1.1 | `erp/core/security.py` | `tests/core/test_security.py` | partial |
| IAM-03 | Define realm strategy in an ADR; | P1.1 | — | — | planned |
| IAM-04 | Enforce permissions on the server as well as the UI. | P1.1 | `erp/modules/platform/audit.py` | `tests/platform/test_audit.py` | partial |
| MOB-01 | Ship one application per supported mobile platform, usable by all clients; | P2.1 | — | — | planned |
| MOB-02 | Sign-in journey: enter account number -> resolve trusted deployment configuration -> display business ident… | P1.1 (contract) / P2.1 | — | — | planned |
| MOB-03 | Use Authorization Code with PKCE through the platform authentication session/system browser. | P2.1 | — | — | planned |
| MOB-04 | Provide an account directory for SaaS and registered client-hosted deployments. | P1.1 (directory) / P2.1 | — | — | planned |
| MOB-05 | Client-hosted servers must be reachable through approved HTTPS, VPN or local connectivity. | P1.9 / P2.1 | — | — | planned |
| MOB-06 | Store refresh credentials in OS secure storage, never passwords. | P2.1 | — | — | planned |
| MOB-07 | Mobile functions delivered by phase: dashboards, approvals, product lookup, barcode/QR scans, receiving/cou… | P2.2 | — | — | planned |
| MOB-08 | Explicitly label offline-capable operations. | P2.4 | — | — | planned |
| MOB-09 | Tenant-isolate push registrations and deep links. | P1.9 / P2.5 | — | — | planned |
| PLT-01 | Companies, branches, departments, warehouses, locations, business calendars, fiscal periods, currencies, la… | P1.2 | — | — | planned |
| PLT-02 | Shared contacts support customer/supplier roles, addresses, tax registrations and contacts without conflati… | P1.2 | — | — | planned |
| PLT-03 | Products support goods, services, ingredients, prepared stock and manufactured goods; | P1.2 | — | — | planned |
| PLT-04 | Unit conversion has explicit dimensions and precision. | P1.2 | — | — | planned |
| PLT-05 | Configurable document numbering, templates, notifications, approvals, custom fields, import/export and audit. | P1.2 | `erp/modules/platform/module_state.py`, `dependencies.ModuleGuard`, `app.py` | `tests/platform/test_tenant_modules.py`, `tests/platform/test_module_gating.py` | partial |
| PLT-06 | Use decimal quantities/money; | P1.2 | `erp/shared/money.py` | `tests/shared/test_money.py`, `tests/core/test_errors.py` | partial |
| INV-01 | Flexible hierarchy: warehouse -> zone -> aisle -> rack -> shelf -> bin. | P1.3 | — | — | planned |
| INV-02 | Distinguish physical storage, receiving, dispatch, production, transit, quarantine and scrap. | P1.3 | — | — | planned |
| INV-03 | Stock ledger tracks product variant, company, warehouse/location, quantity/unit, batch/serial, stock status… | P1.3 | — | — | planned |
| INV-04 | Support on-hand, reserved, available, incoming, in-transit and quarantined quantities with documented formu… | P1.3 | — | — | planned |
| INV-05 | Receiving, put-away, reservation, picking, packing, dispatch, transfers, returns, replenishment, opening ba… | P1.3 | — | — | planned |
| INV-06 | A product can occupy many bins and a bin can contain permitted products/batches. | P1.3 | — | — | planned |
| INV-07 | Support bin/shelf/rack/zone/warehouse count sessions, blind counts, assigned counters, recounts, batch/seri… | P1.3 | — | — | planned |
| INV-08 | Cycle-count scheduling, discrepancy reports, capacity checks and location occupancy. | P1.3 | — | — | planned |
| INV-09 | Inventory valuation method is explicitly selected and version-controlled by supported scope. | P1.3 | — | — | planned |
| BAR-01 | Support EAN/UPC, internal Code 128, GS1-128, GS1 DataMatrix, ordinary QR and GS1 Digital Link parsing/gener… | P1.3 | — | — | planned |
| BAR-02 | Store multiple identifiers per product/variant/packaging. | P1.3 | — | — | planned |
| BAR-03 | Separate identifier recognition from business action. | P1.3 | — | — | planned |
| BAR-04 | Label templates for materials, finished goods, bins, cartons and pallets. | P1.3 | — | — | planned |
| BAR-05 | Test keyboard-wedge scanners, mobile cameras and selected 2D scanners. | P1.3 | — | — | planned |
| PUR-01 | Requisitions, RFQs, supplier offers, purchase orders, approval limits, agreements/tenders, partial receivin… | P1.3 | — | — | planned |
| PUR-02 | Supplier price lists, lead times, packaging, minimum quantities, replenishment proposals and landed-cost al… | P1.3 | — | — | planned |
| WHO-01 | B2B accounts, negotiated price lists, quantity breaks, quotations, minimum orders, credit limits, payment t… | P1.4 | — | — | planned |
| WHO-02 | Customer portal for quotations, orders, invoices, balances and reorder; | P1.6 | — | — | planned |
| MFG-01 | Versioned BOMs, units, routings, work centres, capacity, material requirements and production orders. | P1.5 | — | — | planned |
| MFG-02 | Plan, reserve and issue raw materials; | P1.5 | — | — | planned |
| MFG-03 | Material, labour and overhead costing with defined posting points and variance handling. | P1.5 | — | — | planned |
| MFG-04 | Subcontracting, production scheduling and multi-level BOM planning are phased capabilities; | P1.5 | — | — | planned |
| MFG-05 | PLM includes engineering changes, version approvals and effective dates. | P1.5 | — | — | planned |
| SAL-01 | Leads/opportunities, activities, quotations, sales orders, discounts, price lists, reservations, deliveries… | P1.4 | — | — | planned |
| POS-01 | Touch-friendly checkout, barcode scans, variants/packaging, customer selection, promotions, tax, split tend… | P1.4 | — | — | planned |
| POS-02 | Controlled refunds/exchanges, original-sale lookup, permissions, reason codes and treatment of damaged vers… | P1.4 | — | — | planned |
| POS-03 | Offline order queue, device IDs, stable transaction IDs, cached catalogue/rule versions and retry-safe sync… | P1.4 | — | — | planned |
| POS-04 | Cash can follow approved offline policy. | P1.4 | — | — | planned |
| POS-05 | Receipt templates include seller details, items/modifiers, quantities, discounts, tax breakdown, service ch… | P1.4 | — | — | planned |
| SAL-02 | Subscriptions include recurring billing, renewals, cancellations and failed-payment handling. | P1.8 | — | — | planned |
| RES-01 | Menus, availability, sizes, variants, modifiers, kitchen stations, tables, floor plans, seats, table transf… | P1.5 | — | — | planned |
| RES-02 | Versioned recipe per menu item/size with ingredients, quantities, UOM, yield and modifier deltas. | P1.5 | — | — | planned |
| RES-03 | Made-to-order items reserve ingredients at acceptance and consume at a configured preparation milestone. | P1.5 | — | — | planned |
| RES-04 | Trimming, cooking yield, substitutions, portions, spoilage and waste need explicit records. | P1.5 | — | — | planned |
| RES-05 | Track dry store, freezer, kitchen, outlet and other locations using the shared inventory hierarchy. | P1.5 | — | — | planned |
| RES-06 | Customer receipt and kitchen ticket are distinct documents. | P1.5 | — | — | planned |
| WEB-01 | Website builder/content management, themes, pages, navigation, media, custom domains, responsive design, Ba… | P1.6 | — | — | planned |
| WEB-02 | Catalogue, search/filter, variants, customer-specific visibility/prices, cart, checkout, shipping/pickup, c… | P1.6 | — | — | planned |
| WEB-03 | ERP owns order/payment state. | P1.6 | — | — | planned |
| WEB-04 | Courier and payment adapters, cash-on-delivery collection/settlement reconciliation, fraud controls and pro… | P1.6 | — | — | planned |
| WEB-05 | Blog publishing, moderated forum, eLearning courses/progress and live chat are phased modules. | P1.8 | — | — | planned |
| TAX-01 | Dedicated shared tax engine for purchasing, sales, POS, restaurants and commerce. | P1.2 | — | — | planned |
| TAX-02 | Support inclusive/exclusive pricing, multiple and compound taxes, exemptions, zero-rated and out-of-scope d… | P1.2 | — | — | planned |
| TAX-03 | Rule selection may consider company, seller/buyer location, delivery location, transaction type and registr… | P1.2 | — | — | planned |
| TAX-04 | Freeze tax inputs/results on posted documents. | P1.2 | — | — | planned |
| FIN-01 | Chart of accounts, journals, balanced double-entry posting, receivables/payables, bank/cash reconciliation,… | P1.2 | — | — | planned |
| FIN-02 | Posted journals are corrected through authorized reversals/adjustments. | P1.2 | — | — | planned |
| LOC-01 | Bangladesh package supplies validated defaults, Bangla/English templates, BDT and Asia/Dhaka defaults and l… | P1.2 / P1.9 | — | — | planned |
| LOC-02 | Country packages are separately versioned with effective dates, migration notes and golden calculation tests. | P1.2 / P1.9 | — | — | planned |
| HR-01 | Employee profiles, departments, jobs, contracts, onboarding/offboarding, document permissions, recruitment… | P1.7 | — | — | planned |
| ATT-01 | Shift plans, overnight shifts, holidays, clock-in/out, breaks, lateness, overtime, leave balances and appro… | P1.7 | — | — | planned |
| PAY-01 | Effective-dated salary structures, allowances, deductions, approved attendance/overtime inputs, payroll per… | P1.7 | — | — | planned |
| PAY-02 | Freeze payroll inputs and calculation version at approval. | P1.7 | — | — | planned |
| HR-02 | Employee self-service on web/mobile includes leave requests, attendance corrections, own documents and own… | P1.7 | — | — | planned |
| DOC-01 | Permissioned files/folders, tags, versions, retention, previews, malware scanning and links to business rec… | P1.7 | — | — | planned |
| SIG-01 | Templates, signature/initial/date fields, sequential/parallel signers, request expiry, reminders, decline/c… | P1.7 | — | — | planned |
| SIG-02 | Preserve document hashes, evidence, timestamps, consent and immutable completed versions. | P1.7 | — | — | planned |
| SIG-03 | Connect sales, purchasing and HR records to signing requests. | P1.7 | — | — | planned |
| APR-01 | Reusable approvals with conditions, thresholds, delegation, escalation, rejection reasons and audit. | P1.1 | — | — | planned |
| EXT-01 | Marketing includes audience rules, consent/unsubscribe, templates, scheduling, delivery status and deduplic… | P1.8 | — | — | planned |
| EXT-02 | Projects include tasks/dependencies, timesheets and billing; | P1.8 | — | — | planned |
| EXT-03 | Discuss/Knowledge support permissions and business-record links. | P1.8 | — | — | planned |
| EXT-04 | IoT adapters authenticate devices and validate measurements. | P1.8 | — | — | planned |
| EXT-05 | AI is optional, permission-aware and provider-configurable; | P1.8 | — | — | planned |
| JOB-01 | Celery executes Python jobs; | P1.1 | — | — | planned |
| JOB-02 | PostgreSQL stores authoritative job status, progress, attempts and business results. | P1.1 | — | — | planned |
| JOB-03 | One active scheduler per schedule scope. | P1.1 | — | — | planned |
| JOB-04 | Outbox publishing can repeat; | P1.1 | `erp/modules/integration/outbox.py` | `tests/outbox/test_outbox.py` | partial |
| JOB-05 | Go requests ERP-owned jobs through the API. | P1.1 | — | — | planned |
| INT-01 | Define adapters for payments, banking files, couriers, email/SMS, signing, attendance devices, printers, ta… | P1.1 (contract) / per-adapter milestone | — | — | planned |
| OPS-01 | Same versioned container images and migrations for SaaS/client hosting. | P1.1 (skeleton) / P1.9 | — | — | planned |
| OPS-02 | Per-environment secrets, TLS, private data services, least-privilege accounts, restricted CORS and CSRF pro… | P1.1 (skeleton) / P1.9 | — | — | planned |
| OPS-03 | Document backup ownership, encrypted backups, PostgreSQL point-in-time recovery where supported, file/ident… | P1.9 | — | — | planned |
| OPS-04 | Structured logs, traces, metrics, health/readiness checks and alerts. | P1.1 (skeleton) / P1.9 | — | — | planned |
| OPS-05 | Releases include compatibility notes, checksums, migrations, upgrade preflight, backup requirements and rec… | P1.9 | `erp/cli.py` (`Cli` `upgrade-tenants`) | `tests/platform/test_provisioning.py`, `tests/platform/test_cli.py` | partial |
| OPS-06 | Offline/client-hosted licensing and telemetry are explicit policies. | P1.1 (skeleton) / P1.9 | — | — | planned |
| OPS-07 | Select supported library versions during implementation using official documentation, then pin dependencies… | P1.1 (pinning) / P1.9 (load tests) | — | — | planned |
| LIC-01 | Separate authentication (Keycloak), purchased entitlements (licensing) and user authorization (ERP). | P1.1 | — | — | planned |
| LIC-02 | Central control plane owns plans, immutable published plan versions, subscription contracts, add-ons, deplo… | P1.1 | — | — | planned |
| LIC-03 | Resolve plan version + active add-ons + explicit overrides into one deterministic effective snapshot. | P1.1 | — | — | planned |
| LIC-04 | Quotas specify unit, scope and counting policy: active named users versus concurrent sessions, enabled bran… | P1.1 | — | — | planned |
| LIC-05 | Use a standard signed envelope and maintained cryptographic library; | P1.1 | — | — | planned |
| LIC-06 | Private signing keys never ship in images, repositories or client deployments. | P1.1 | — | — | planned |
| LIC-07 | Distinguish licence validity from renewal/check-in interval. | P1.1 | — | — | planned |
| LIC-08 | Subscription states: trial, active, grace, restricted, cancelled-at-term and expired, with explicit effecti… | P1.1 | — | — | planned |
| LIC-09 | Verified payment settlement or an authorized contract approval activates access. | P1.1 (manual contract) / P1.9 (billing adapter) | — | — | planned |
| LIC-10 | Connected deployments periodically refresh signed grants with authenticated deployment credentials, retries… | P1.1 | — | — | planned |
| LIC-11 | Upgrade activation and downgrade scheduling have explicit effective dates. | P1.1 | — | — | planned |
| LIC-12 | Before expiry, notify administrators. | P1.1 | — | — | planned |
| LIC-13 | Enforcement is an ERP application service invoked by endpoints and jobs, with feature key, action, actor, t… | P1.1 | — | — | planned |
| LIC-14 | Shared mobile/POS clients obtain capabilities from the selected deployment. | P1.4 (POS) / P2 | — | — | planned |
| LIC-15 | Provide administrative screens for plans, versions, subscriptions, deployment inventory, expiring licences,… | P1.1 / P1.9 | — | — | planned |
| FUL-01 | Tenant -> legal company -> branch is an organizational hierarchy. | P1.4 | — | — | planned |
| FUL-02 | One sales order and one permitted invoice can include quantities sourced from several locations. | P1.4 | — | — | planned |
| FUL-03 | Split a single line by quantity, source, reservation and shipment. | P1.4 | — | — | planned |
| FUL-04 | Add warehouse workflow: confirmed -> reserved -> picked -> awaiting loading approval -> loading approved ->… | P1.4 | — | — | planned |
| FUL-05 | Sales permission does not grant dispatch approval. | P1.4 | — | — | planned |
| FUL-06 | Loading operators scan approved products/packages. | P1.4 | — | — | planned |
| FUL-07 | Picking moves goods to staging through an internal movement; | P1.4 | — | — | planned |
| FUL-08 | Add allocation, shipment revision, pick task, loading scan, approval and release-event entities. | P1.4 | — | — | planned |
| RPR-01 | Return authorization (RMA) references sale/order/invoice and serial/batch where available; | P1.4 | — | — | planned |
| RPR-02 | Inspection disposition supports restock, repair, replace, supplier return and scrap. | P1.4 | — | — | planned |
| RPR-03 | Warranty records include coverage dates, terms, exclusions, registration, serial and claim history. | P1.4 | — | — | planned |
| RPR-04 | Track customer-owned goods held for service separately from company-owned saleable inventory and valuation. | P1.4 | — | — | planned |
| RPR-05 | External service-centre transfers have custody tracking and return receipt. | P1.4 | — | — | planned |
| RPR-06 | Include return_requests/lines, inspections, disposition_events, warranty_policies/registrations, repair_ord… | P1.4 | — | — | planned |
| EXP-01 | Support employee expense claims and company operating expenses, including receipt attachment, category, dat… | P1.7 | — | — | planned |
| EXP-02 | Allocate costs to legal company, branch, department, project or cost centre; | P1.7 | — | — | planned |
| EXP-03 | Draft -> submitted -> approved/rejected -> posted -> settled, with controlled corrections and resubmission. | P1.7 | — | — | planned |
| EXP-04 | Link supplier bills, company-card transactions, advances and claims representing the same cost to avoid dup… | P1.7 | — | — | planned |
| EXP-05 | Add expense_claims, expense_lines, expense_categories, expense_allocations and employee_advances, referenci… | P1.7 | — | — | planned |
| DB-01 | Default is module-based PostgreSQL schemas with tenant-scoped tables: platform, catalog, inventory, sales,… | P1.1 | `migrations/registry/*`, `migrations/tenant/*` | `tests/core/test_migrations.py`, `tests/platform/test_tenant_isolation.py` | partial |
| DB-02 | Enforce tenant-qualified uniqueness and foreign keys, company ownership, row-security policy and privileged… | P1.1 | `migrations/registry/*`, `migrations/tenant/*` | `tests/core/test_migrations.py`, `tests/platform/test_tenant_isolation.py` | partial |
| DB-03 | Commerce storefronts/domains/publications/carts/customer accounts refer to shared catalogue and ERP orders. | P1.1 | — | — | planned |
| DEV-01 | Shared mobile app supports selected Android warehouse handhelds with integrated 2D scanners, phone camera a… | P1.3 (USB wedge) / P2.3 | — | — | planned |
| DEV-02 | Explicit mode determines scan action: receiving, transfer, picking, count, loading or dispatch. | P1.3 (web) / P2.3 (native) | — | — | planned |
| DEV-03 | Device/user registration, location permissions, scan audit and idempotent operation IDs are required. | P1.3 (web) / P2.3 (native) | — | — | planned |
| AUTH-01 | Implement tenant-owned editable permission groups, multiple group membership and per-user grants/denials. | P1.1 | — | — | planned |
| AUTH-02 | Permission keys identify resource/action, e.g. | P1.1 | — | — | planned |
| AUTH-03 | Each policy carries effect (allow/deny), company/branch/warehouse scope, own/team/all record scope where ap… | P1.1 | — | — | planned |
| AUTH-04 | Evaluate in this order: authenticated active membership -> licensed action -> non-bypassable tenant/securit… | P1.1 | — | — | planned |
| AUTH-05 | Do not merge conditions from different grants into a broader privilege. | P1.1 | — | — | planned |
| AUTH-06 | Custom user examples: salesperson may gain an expiring discount-approval grant, be denied cost visibility a… | P1.1 | — | — | planned |
| AUTH-07 | Provide group editor, membership management, individual override editor, scope/limit selector, expiry/reaso… | P1.1 | — | — | planned |
| AUTH-08 | Permission administrators may grant only delegated permissions/scopes. | P1.1 | — | — | planned |
| AUTH-09 | Backend endpoints, query filtering, field serialization, exports, background jobs and sockets use the same… | P1.1 | — | — | planned |
| AUTH-10 | Maintain authorization revision and invalidate relevant caches on changes. | P1.1 | — | — | planned |
| AUTH-11 | Tables: permission_definitions, permission_groups, group_policies, user_group_memberships, user_permission_… | P1.1 | — | — | planned |
| AUTH-12 | Tests must cover no-grant denial; | P1.1 | — | — | planned |
| IMP-01 | Import shipment groups supplier purchase-order lines and tracks shipment/container references, carrier, ori… | P1.3 | — | — | planned |
| IMP-02 | Documents include commercial invoice, packing list, transport document, customs declaration and clearing/su… | P1.3 | — | — | planned |
| IMP-03 | Cost lines cover freight, insurance, duty, clearing, port/storage, inland transport and other approved costs. | P1.3 | — | — | planned |
| IMP-04 | Landed-cost batch allocates eligible costs to receipt/item valuation layers by value, quantity, weight, vol… | P1.3 | — | — | planned |
| IMP-05 | Preview -> reviewed -> approved -> posted -> adjusted/reversed. | P1.3 | — | — | planned |
| IMP-06 | Late cost adjustments follow the supported valuation method and actual disposition: remaining stock, sold s… | P1.3 | — | — | planned |
| IMP-07 | Imports integrate with supplier bills/payments, receipts, partial shipments, damaged/missing goods, claims,… | P1.3 | — | — | planned |
| IMP-08 | Model import_shipments, shipment_purchase_lines, containers/packages as needed, import_documents, import_ch… | P1.3 | — | — | planned |
| IMP-09 | Example acceptance fixture, not a tax rule: 100 units costing 100,000 plus eligible freight 10,000 and duty… | P1.3 | — | — | planned |
| FLT-01 | Flutter/Dart is mandatory for Phase 2. | P2.1 | — | — | planned |
| FLT-02 | Phase 1 publishes account-directory contract, authenticated session/profile, company/branch access, effecti… | P1.1 / P1.9 (contracts) | — | — | planned |
| FLT-03 | Define sync push with device/operation ID, tenant, resource version, operation type and dependency IDs. | P1.1 / P1.9 (contracts) | — | — | planned |
| FLT-04 | Encrypt sensitive local data according to platform capability; | P2.4 | — | — | planned |
| FLT-05 | Native Android scanner adapters may need platform channels/vendor SDK integration; | P2.3 | — | — | planned |
| FLT-06 | Provide role-focused home screens, pending-sync indicators, accessible touch targets, Bangla/English layout… | P2.1–P2.5 | — | — | planned |
| FLT-07 | Phase 2 extends web-tested E2E gates with physical Android/iOS tests and supported warehouse handhelds. | P2.5 | — | — | planned |
| WFL-01 | Build a shared, tenant-configurable approval engine used by invoices, quotations, purchase orders, expenses… | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-02 | Separate the engine from domain execution. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-03 | Initial UI is a form-based builder with a readable preview. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-04 | Workflow definitions have draft, published and retired states and immutable published versions. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-05 | Conditions use a restricted typed expression tree over approved fields: amount/currency, discount, document… | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-06 | If several published definitions match, choose via documented priority/specificity or explicit ordered comp… | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-07 | Support sequential stages, parallel stages, ALL, ANY and N-of-M quorum. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-08 | Support alternative approval paths. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-09 | Proposed example rejection policy: any valid rejection closes the request as rejected; | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-10 | Snapshot workflow version, protected resource revision/hash, triggering facts and candidate assignment at s… | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-11 | Delegation is scoped, time-bound, authorized and audited. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-12 | Comments/reasons are required for rejection, cancellation, exceptional reassignment and manual intervention. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-13 | Approved does not mean the domain action succeeded. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-14 | Protected fields are defined by each domain adapter. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-15 | Record approval decision and associated events transactionally. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-16 | Reminder/escalation workers use persisted due times and unique timer event keys. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-17 | Provide APIs for definition drafts/validation/publication/retirement; | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-18 | Decision requests carry decision, reason where required, expected request/resource revision and idempotency… | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| WFL-19 | Add workflow permissions for edit, publish, preview, submit, decide, delegate, reassign and audit. | P1.1 (engine) / P1.4 (invoice) | — | — | planned |
| ENV-01 | Implement an envelope-based document signing experience integrated with ERP workflows: prepare documents, a… | P1.7 | — | — | planned |
| ENV-02 | Separate basic electronic signing, identity verification and certificate-backed digital signatures. | P1.7 | — | — | planned |
| ENV-03 | Build our own envelope management and document-preparation UI. | P1.7 | — | — | planned |
| ENV-04 | Upload PDFs or generate PDFs from versioned ERP templates. | P1.7 | — | — | planned |
| ENV-05 | Envelope contains one or more ordered document versions, recipients, field placements, subject/message, exp… | P1.7 | — | — | planned |
| ENV-06 | Field designer supports signature, initials, signing date, text, checkbox and approved optional field types. | P1.7 | — | — | planned |
| ENV-07 | Recipient roles include signer, internal countersigner and copy recipient. | P1.7 | — | — | planned |
| ENV-08 | External signers need no ERP account, but secure invitation and configured verification are required. | P1.7 | — | — | planned |
| ENV-09 | Signing UX shows sender/business identity, documents, consent text/version and required fields. | P1.7 | — | — | planned |
| ENV-10 | Viewing is a recipient event; | P1.7 | — | — | planned |
| ENV-11 | Material content changes after approval require new approval. | P1.7 | — | — | planned |
| ENV-12 | Record actor/recipient identity reference, assurance method/outcome, consent version, server timestamps, do… | P1.7 | — | — | planned |
| ENV-13 | For native mode, freeze all signer-entered values and bind each acceptance to a document-set digest and rec… | P1.7 | — | — | planned |
| ENV-14 | Hashes detect changed bytes when compared to trusted evidence; | P1.7 | — | — | planned |
| ENV-15 | Typical flow: ERP draft -> internal approval against frozen revision -> create/send envelope -> customer si… | P1.7 | — | — | planned |
| ENV-16 | Registered workflow actions may prepare/send an envelope or wait for completed/declined/expired events. | P1.7 | — | — | planned |
| ENV-17 | Reminders and expiry are persisted timers with tenant time-zone handling and provider ownership rules. | P1.7 | — | — | planned |
| ENV-18 | Provider interface supports capability discovery, envelope submission, recipient-session initiation where s… | P1.7 | — | — | planned |
| ENV-19 | Proposed internal APIs: templates/version publication; | P1.7 | — | — | planned |
| ENV-20 | Permissions include prepare, send, void, view audit, view original/final, manage templates, manage provider… | P1.7 | — | — | planned |
| B2B-01 | A tenant's business customer can have its own portal account with multiple named users. | P1.6 | — | — | planned |
| B2B-02 | Portal supports customer/company profile, approved delivery/billing addresses, authorized contacts, searcha… | P1.6 | — | — | planned |
| B2B-03 | Buyer roles include organization administrator, purchaser, approver and finance viewer/payer, with configur… | P1.6 | — | — | planned |
| B2B-04 | Show prior orders, order lines, invoices, credit notes, split deliveries, outstanding balances, overdue inv… | P1.6 | — | — | planned |
| B2B-05 | Balance is derived from posted receivable entries and allocations, not an editable profile field. | P1.6 | — | — | planned |
| B2B-06 | Authorized buyers pay invoices partially or in full, pay several invoices together, submit transfer referen… | P1.6 | — | — | planned |
| B2B-07 | Audit buyer user invitations, role changes, orders and payments. | P1.6 | — | — | planned |
| PMT-01 | Support local and international payment options through configurable provider adapters for B2B portal, B2C… | P1.2 (model) / P1.4 / P1.6 | — | — | planned |
| PMT-02 | Do not assume any named provider supports all countries, settlement currencies, subscriptions, refunds or p… | P1.2–P1.4 | — | — | planned |
| PMT-03 | Configure credentials and bank/settlement accounts per tenant/legal company. | P1.2–P1.4 | — | — | planned |
| PMT-04 | Use a canonical payment intent/attempt/transaction model, allocation ledger and settlement records. | P1.2–P1.4 | — | — | planned |
| PMT-05 | Server computes payable amount/currency and verifies all callbacks. | P1.2–P1.4 | — | — | planned |
| PMT-06 | Hosted/tokenized checkout is preferred; | P1.2–P1.4 | — | — | planned |
| PMT-07 | Notify customers of pending/confirmed/failed payments with truthful status. | P1.2–P1.4 | — | — | planned |
| PMT-08 | Provide adapters/interfaces for create attempt, status query, refund where supported, authenticated webhook… | P1.2–P1.4 | — | — | planned |
| BNK-01 | For launch banks/accounts without an available reliable API/webhook, operate through uploaded statements an… | P1.4 | — | — | planned |
| BNK-02 | Start with agreed CSV/XLSX statement profiles and mapping preview for date/value date, debit/credit or sign… | P1.4 | — | — | planned |
| BNK-03 | Import lifecycle: uploaded -> parsed -> validated -> reviewed -> committed, with rejected/partial-error sta… | P1.4 | — | — | planned |
| BNK-04 | Detect duplicate files and overlapping statement periods. | P1.4 | — | — | planned |
| BNK-05 | Normalize statement lines independently of customer allocation. | P1.4 | — | — | planned |
| BNK-06 | Reviewer can split one bank receipt across invoices, combine several receipts for one invoice or leave unap… | P1.4 | — | — | planned |
| BNK-07 | Distinguish a customer-declared transfer from a statement-supported receipt. | P1.4 | — | — | planned |
| BNK-08 | When a newer statement or future API feed arrives, link overlapping evidence to the existing canonical tran… | P1.4 | — | — | planned |
| BNK-09 | Correct posted errors with an authorized reversal/unmatch/reallocation chain, preserving original records a… | P1.4 | — | — | planned |
| BNK-10 | Reconcile gateway settlements and direct bank transfers differently. | P1.4 | — | — | planned |
| BNK-11 | APIs/UI cover import profiles, preview/errors, duplicate review, statement lines, suggested matches, confir… | P1.4 | — | — | planned |
| PRC-01 | Provide at least wholesale and retail price-list types with explicit customer assignment, company/storefron… | P1.2 | — | — | planned |
| PRC-02 | Customer-specific contract prices and additional percentage/fixed discounts/offers have eligibility, produc… | P1.2 | — | — | planned |
| PRC-03 | Define deterministic calculation precedence: select applicable permitted base/contract price, apply eligibl… | P1.2 | — | — | planned |
| PRC-04 | Preview explains base, rule IDs, discount lines, tax treatment and final amount. | P1.2 | — | — | planned |
| PRC-05 | Protect cost/margin fields from customer/sales roles without permission. | P1.2 | — | — | planned |
| LOY-01 | Support separate configurable programs for B2B buyer organizations and B2C customers, with multiple levels,… | P1.8 | — | — | planned |
| LOY-02 | Rules specify eligible spend/orders, qualification window, excluded tax/shipping/items, currencies, paid/fu… | P1.8 | — | — | planned |
| LOY-03 | Use append-only loyalty ledger entries for pending earnings, vested earnings, redemption reservations, comm… | P1.8 | — | — | planned |
| LOY-04 | Mark points earned from unconfirmed bank-transfer orders as pending when applicable. | P1.8 | — | — | planned |
| LOY-05 | Tier benefits can include eligible discounts, shipping offers or service benefits. | P1.8 | — | — | planned |
| LOY-06 | Customer portal shows level, progress/window, available/pending points, expiry and history. | P1.8 | — | — | planned |
| MSG-01 | Email transactional notifications and email marketing are explicit scope; | P1.4 (transactional) / P1.8 (campaigns) | — | — | planned |
| MSG-02 | Distinguish service/transactional communication from marketing purpose. | P1.4 (transactional) / P1.8 (campaigns) | — | — | planned |
| MSG-03 | Versioned Bangla/English templates and tenant/company branding, sender identity verification, recipient loc… | P1.4 (transactional) / P1.8 (campaigns) | — | — | planned |
| MSG-04 | Event-driven outbox/jobs, recipient preferences, idempotent sends, rate limits, retries, bounce/complaint h… | P1.4 (transactional) / P1.8 (campaigns) | — | — | planned |
| MSG-05 | Marketing campaigns support audience segmentation, scheduling, exclusions, customer-type/tier segments, app… | P1.8 | — | — | planned |
| MSG-06 | Keep provider credentials tenant-scoped, validate webhooks and redact content/tokens in logs. | P1.4 (transactional) / P1.8 (campaigns) | — | — | planned |
| BMA-01 | The same Android/iOS app serves staff and B2B customer users. | P2.2 | — | — | planned |
| BMA-02 | After authentication, present only authorized workspaces. | P2.2 | — | — | planned |
| BMA-03 | Deliver the same business features as the Phase 1 B2B web portal: approved catalogue/search; | P2.2 | — | — | planned |
| BMA-04 | Payment flows include invoice selection, partial/multiple-invoice payment, supported local/international pr… | P2.2 | — | — | planned |
| BMA-05 | Show as-of timestamps and connectivity state for balances, credit availability, prices, points and order st… | P2.2 | — | — | planned |
| BMA-06 | Customer push/email/SMS preferences and notifications reuse the messaging services. | P2.2 | — | — | planned |
| BMA-07 | Update P2.2 to include the full B2B customer workspace and portal parity; | P2.2 | — | — | planned |
| E2E-01 | Tenant A cannot read/write/export tenant B records through IDs, caches, jobs, files, search, mobile or notifications. | Gate (see master plan §7) | — | — | planned |
| E2E-02 | Receive materials into bins, transfer to production, manufacture, label finished goods, sell through POS, produce receipt and reconcile stock/accounting. | Gate (see master plan §7) | — | — | planned |
| E2E-03 | Two channels compete for final available stock: reservation policy holds with no accidental oversell. | Gate (see master plan §7) | — | — | planned |
| E2E-04 | Count during movement follows chosen freeze/reconciliation policy; replayed approval creates no duplicate adjustment. | Gate (see master plan §7) | — | — | planned |
| E2E-05 | Recipe and batch-preparation tests prove correct consumption, modifiers, waste and cancellation/refund behaviour. | Gate (see master plan §7) | — | — | planned |
| E2E-06 | Inclusive/exclusive, compound, exempt, rounded and effective-dated tax cases match reviewed golden examples; historical documents stay unchanged. | Gate (see master plan §7) | — | — | planned |
| E2E-07 | Offline POS/mobile reconnects with duplicate submissions and changed prices/permissions; conflicts are visible and no duplicate financial effects occur. | Gate (see master plan §7) | — | — | planned |
| E2E-08 | Payment webhook duplicates, delayed success, refund failure and out-of-order events reconcile without false paid status. | Gate (see master plan §7) | — | — | planned |
| E2E-09 | Payroll rerun preserves approved inputs and creates no duplicate posting/export; employee payslip privacy is enforced. | Gate (see master plan §7) | — | — | planned |
| E2E-10 | Signed document alteration is detectable; completion preserves original bytes and evidence. | Gate (see master plan §7) | — | — | planned |
| E2E-11 | Shared mobile app switches SaaS accounts and client-hosted deployment with isolation and safe endpoint resolution. | Gate (see master plan §7) | — | — | planned |
| E2E-12 | Broker/worker crash between commit, publish and acknowledgement recovers through outbox and idempotency. | Gate (see master plan §7) | — | — | planned |
| E2E-13 | Restore a real backup and perform a supported version upgrade for both hosting profiles. | Gate (see master plan §7) | — | — | planned |
| E2E-14 | Bangla text prints correctly on selected receipts/labels/documents; supported barcodes scan on target hardware. | Gate (see master plan §7) | — | — | planned |

## Owner additions (not in spec v2.3)

| ID | Requirement | Milestone | Implementation | Test evidence | Status |
|---|---|---|---|---|---|
| OWN-01 | Restaurant customer self-service: ordering kiosks (plus spec RES-06 QR table ordering), unattended registered devices, orders through normal pricing/stock/kitchen rules; see `module-dependencies.md` §3b | P1.5 | — | — | planned (open decisions) |
| OWN-02 | Class-based / object-oriented code structure (controllers, services, repositories as classes); see ADR-0011 | P1.1a onward | all of `erp/` (class-based layers) | `tests/core/test_class_based.py` | partial |
