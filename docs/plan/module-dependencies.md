# Module Dependency Graph — 50 Catalogue Apps

Status: **Proposed, not decided** · Drafted 2026-09-22 · Related: ADR-0009 (module system), spec §17, PLT-05, LIC-03/13

This is the working proposal for how the 50 catalogue apps (spec §17), plus the spec's explicit additions, depend on each other. **Nothing here is final.** The open decisions in §5 must be settled by the owner before the graph is encoded in `erp/module_catalog.py`. Until then, only the platform and integration core modules exist in code.

## 1. Principles

1. **Keep hard dependencies to a minimum.** A *hard* dependency (`depends_on`) means the app cannot function at all without the other app. Anything that only adds value when another app is present is a *soft integration* (`integrates_with`): the feature appears when the other app is enabled and hides otherwise. Few hard edges keep apps independently switchable.
2. **Put shared master data in an always-on foundation.** Contacts, products, tax and journal posting are needed by many apps. Making each app depend on "Accounting" or "Inventory" instead would chain the whole catalogue together.
3. **Make an edge hard only if the spec's workflow truly cannot run without it.** For example, POS decrements stock (needs Inventory); eCommerce publishes through the Website.
4. **Disabling never deletes data** (PLT-05). A hard edge only controls which enable/disable operations are allowed.

## 2. Layer 0 — foundation (always on, not switchable)

These are core modules (`core=True`). Tenants cannot disable them, and many are invisible when unused.

| Foundation service | Why it is always on |
|---|---|
| Platform (companies, branches, users, settings, numbering, audit) | Everything runs on it |
| Access & permissions | Every request is authorized (AUTH-01..12) |
| Licensing | Every request is entitlement-checked (LIC-13) |
| Workflow engine | Shared by invoices, POs, expenses, payroll, dispatch (WFL-01) |
| Integration (jobs, outbox, webhooks) | Used by almost every app (ARC-03, JOB-01..05) |
| Notifications (transactional email) | Order, payment, approval and HR notices (MSG-01) |
| File storage & attachments | Receipts, contracts, images everywhere (DOC-01) |
| Contacts (customers/suppliers) | Shared by sales, purchase, HR, marketing (PLT-02) |
| Product catalogue, units, currencies | Shared by sales, purchase, stock, POS, web, manufacturing (PLT-03/04) |
| Tax engine | Explicitly one shared engine (TAX-01) |
| Ledger core (chart of accounts, journals, fiscal periods, FX) | Stock valuation, POS, payroll and expenses post journals even when the Accounting app is off (FIN-01/02) |
| Calendar | Time off, planning, appointments, CRM meetings |
| Localization packages (Bangladesh first) | Tax, templates and defaults per country (LOC-01/02) |

## 3. The apps

Legend:
- **Requires**: hard `depends_on`, which must be enabled first.
- **Requires any of**: at least one of the listed apps must be enabled.
- **Integrates with**: soft, runtime-checked, optional.
- **Bold** entries in the *Integrates with* column are soft edges that are an **open decision** (§5).

### Finance (7)
| App | Requires | Integrates with |
|---|---|---|
| Invoicing | — | Sales, Purchase, POS |
| Accounting (bank reconciliation, reports, assets, budgets) | Invoicing | Payroll, Inventory valuation |
| Expenses | Employees | Accounting, Project |
| Documents (document-management app UI) | — | every app's attachments |
| Spreadsheets | — | any app as a data source |
| Sign | — | Documents, Sales, Purchase, Employees |
| ESG | — | Inventory, Fleet, Accounting data |

### Sales (5)
| App | Requires | Integrates with |
|---|---|---|
| CRM | — | Sales, VoIP, Email Marketing |
| Sales | Invoicing | **Inventory** (deliveries, reservations, split-source fulfilment), CRM |
| Point of Sale | Inventory, Invoicing | Loyalty, Restaurant, IoT |
| Subscriptions | Sales | Accounting |
| Rental | Sales, Inventory | — |

### Inventory & manufacturing (6)
| App | Requires | Integrates with |
|---|---|---|
| Inventory | — | Purchase, Sales, Quality |
| Purchase (incl. imports/landed costs) | Invoicing | **Inventory** (receiving; the imports/landed-cost feature requires it) |
| Manufacturing | Inventory | Quality, Maintenance, PLM |
| PLM | Manufacturing | Documents, Sign |
| Quality | Inventory | Manufacturing, Purchase |
| Maintenance | — | Manufacturing (work-centre downtime) |

### Website (6)
| App | Requires | Integrates with |
|---|---|---|
| Website | — | all Website apps |
| eCommerce | Website, Sales | **Inventory** (stock availability), Loyalty |
| Blog | Website | — |
| Forum | Website | eLearning |
| eLearning | Website | eCommerce (paid courses) |
| Live Chat | Website, Discuss | Helpdesk |

### HR (7) + Attendance
| App | Requires | Integrates with |
|---|---|---|
| Employees | — | all HR apps |
| Recruitment | Employees | Sign, Survey |
| Time Off | Employees | Payroll, Planning |
| Appraisals | Employees | Survey |
| Payroll | Employees | Attendance, Time Off, Accounting |
| Referral | Recruitment | — |
| Fleet | — | Employees, ESG |
| Attendance *(spec addition)* | Employees | Payroll, IoT (attendance devices) |

### Marketing (6)
| App | Requires | Integrates with |
|---|---|---|
| Email Marketing | — | CRM, Sales, Events |
| SMS Marketing | — | CRM, Sales, Events |
| Marketing Automation | **Requires any of:** Email Marketing, SMS Marketing | CRM, Website |
| Social Marketing | — | Website |
| Events | — | Website (registration), eCommerce (tickets) |
| Survey | — | Recruitment, Appraisals, Events |

### Services (6)
| App | Requires | Integrates with |
|---|---|---|
| Project | — | Sales (billing), Documents |
| Timesheet | Project, Employees | Sales, Helpdesk, Payroll |
| Field Service | Project | Inventory (materials), Timesheet, Sign |
| Helpdesk | — | Timesheet, Sales, Live Chat |
| Planning | Employees | Project, Time Off |
| Appointments | — | Website, CRM |

### Productivity (6) + Customization (1)
| App | Requires | Integrates with |
|---|---|---|
| Discuss | — | Live Chat, record messaging |
| Approvals (generic request app; the engine itself is foundation) | — | — |
| Internet of Things | — | POS, Manufacturing, Attendance |
| VoIP | — | CRM, Helpdesk |
| Knowledge | — | — |
| AI | — | any app, permission-aware (EXT-05) |
| Studio | — | any app (metadata-driven customization only, EXT-04) |

### Spec additions not in the 50
| App | Requires | Integrates with |
|---|---|---|
| Restaurant | Point of Sale | Manufacturing, Loyalty, IoT |
| ↳ Restaurant self-service *(owner addition OWN-01)*: feature `restaurant.self_service` | Restaurant | Loyalty, IoT (kiosk printers, card terminals), eCommerce payments |
| Repairs & Warranty | Inventory, Invoicing | Sales, Helpdesk |
| B2B Portal | Sales | eCommerce, Loyalty |
| Loyalty | **Requires any of:** Sales, Point of Sale, eCommerce | — |

## 3a. Returns, service and repairs — who owns what

A return touches several apps, so ownership is split. Each app owns its own documents, and the steps are linked by events and interfaces (never shared tables):

| Flow | Owning app | Other apps involved | Spec |
|---|---|---|---|
| Sales return authorization (RMA): eligibility, quantity cap vs. previous returns, approval, tracking | **Sales** | Workflow engine (approval), Invoicing (credit note) | RPR-01/02, FUL-03 |
| POS refund / exchange: original-sale lookup, reason codes, damaged vs. resellable | **Point of Sale** | Invoicing (refund payment), Inventory (restock) | POS-02 |
| eCommerce / B2B portal return request | **eCommerce** / **B2B Portal** (customer-facing request) → creates a Sales RMA | Sales | WEB-02, B2B-02, BMA-03 |
| Returned goods receipt into inspection/quarantine; disposition: restock, repair, replace, supplier return, scrap | **Inventory** | Quality (inspection, optional), Repairs | RPR-01/02, INV-02/05 |
| Refund / credit note: separate from physical stock disposition; follows original tax and discount | **Invoicing** | Loyalty (reverses earned points) | POS-02, RPR-02, PRC-05, TAX-04, LOY-03 |
| Purchase return to supplier | **Purchase** | Inventory, Invoicing (supplier credit) | PUR-01 |
| Warranty policies, registrations, claims | **Repairs & Warranty** | Sales (serial sale history) | RPR-03 |
| Customer repair orders: fault, diagnosis, estimate + approval, parts, labour, QC, handover; customer-owned goods kept out of sellable stock and valuation; external service-centre custody; replacement serial linkage | **Repairs & Warranty** | Inventory (parts consumption, custody locations), Invoicing (paid repairs), Helpdesk (ticket origin) | RPR-03/04/05/06 |
| Field service (onsite jobs, materials, completion evidence) | **Field Service** | Project, Inventory, Timesheet, Sign | EXT-02 |
| Helpdesk tickets, SLAs, customer access | **Helpdesk** | Timesheet, Repairs | EXT-02 |
| Maintenance of the **company's own** equipment (distinct from customer repairs) | **Maintenance** | Manufacturing | MFG-05, RPR-06 |

Rules that hold across these flows:
- A refund never restocks automatically.
- A restock never refunds automatically.
- Returned goods enter quarantine, not available stock.

These must remain true whichever apps a tenant enables.

**Open (owner):** whether returns are allowed in a tenant with Sales but no Inventory (e.g. service refunds only) follows from decision D1.

## 3b. Restaurant self-service (owner addition OWN-01, 2026-09-22)

Restaurants will offer customer self-service. The spec already covers **QR menu / table ordering** (RES-06): validate the table context and route orders through normal pricing, stock and kitchen rules. **Self-service ordering kiosks are new scope** added by the owner. Proposed shape:

- A feature of the Restaurant app (`restaurant.self_service`), licensable separately, with three channels:
  - in-store kiosks (touch web app `kiosk-web`, installable PWA)
  - QR table ordering (RES-06)
  - optional pay-at-table
- Orders from every channel enter the same restaurant order flow:
  - server-side pricing, modifiers and tax (ARC-02)
  - ingredient reservation at acceptance and consumption at the configured preparation milestone (RES-03)
  - kitchen tickets (RES-01)
  - customer receipt separate from kitchen ticket (RES-06)
- Kiosks are registered, tenant-scoped devices (DEV-03 style) bound to a branch and outlet. They are unattended: no staff login, a restricted capability set, and no access to staff APIs.
- Payment options depend on the chosen provider/hardware (POS-04, PMT-02): pay at kiosk (card terminal / QR wallet), pay at counter (order held until paid), or pay later (dine-in tab). Unknown payment outcomes follow the reconciliation rules (PMT-07); the kitchen only receives the order once the configured payment condition is met.

**Open (owner):**
- which channels are needed at launch (kiosk, QR table, both)
- kiosk hardware and card-terminal/wallet providers
- payment timing per channel (before kitchen vs. dine-in tab)
- whether the kiosk must keep working offline (it affects payment and stock policy, as with POS-03)
- upsell/loyalty sign-in at the kiosk
- Bangla/English and accessibility requirements for unattended screens

## 4. Module-system extensions this graph needs

ADR-0009 and the P1.1a plan currently implement only plain `depends_on`. This graph needs three more mechanisms. **They are not yet in the P1.1a plan**; add them once the graph is agreed.

1. **`requires_any` groups.** At least one member must be enabled (Loyalty; Marketing Automation). Disabling the last enabled member of a group that an enabled app needs is blocked.
2. **`integrates_with` declarations.** Documented soft edges. Code checks `TenantModules.enabled()` at runtime and degrades gracefully. Declaring the edges keeps them visible and testable, e.g. "Sales hides the Deliveries tab when Inventory is off".
3. **Feature-level requirements inside an app.** For example, `purchase.landed_costs` requires Inventory even though Purchase does not. These feature keys line up with licence feature keys (§26), so a subscription package can include or exclude them independently.

## 5. Open decisions (owner)

| # | Question | Proposal | Why it matters |
|---|---|---|---|
| D1 | Sales → Inventory: hard or soft? | **Soft.** Service businesses (consulting, agencies, subscriptions) sell without stock; fulfilment features switch on when Inventory is enabled. | The owner's earlier example assumed hard. Hard forces every Sales tenant to run Inventory. |
| D2 | Ledger core always on, with Invoicing and Accounting as apps on top? | **Yes.** | The alternative makes Accounting a hard dependency of POS, Payroll, Inventory and more, forcing almost every client to enable it. |
| D3 | Purchase → Inventory and eCommerce → Inventory: soft? | **Soft**, with imports/landed costs and stock availability as Inventory-dependent features. | Service procurement and digital/service stores work without stock. |
| D4 | POS → Inventory: hard? | **Hard**, unless a services-only POS (e.g. salons) must be supported. | Determines whether POS can be sold alone. |
| D5 | Contacts and product catalogue as foundation (not switchable)? | **Yes.** An HR-only tenant has them present but hidden. | Avoids nearly every app depending on a "Contacts" or "Products" app. |
| D6 | Workflow engine as foundation, with "Approvals" as a separate optional app for generic request types? | **Yes.** | Invoice, PO, expense and payroll approvals must keep working if the Approvals app is off. |
| D7 | Discuss: optional app or foundation? | **Optional.** Record-level messaging (comments on documents) lives in the foundation. | Live Chat requires Discuss; other apps should not. |
| D8 | Commercial packaging: which apps and features each subscription plan includes | Out of scope here; decided with licensing (§26) | Enablement (tenant's choice) and entitlement (what they bought) are separate checks; both must pass. |

## 6. When the graph is agreed

1. Update this document's status to *Accepted*, and record each decision with its date.
2. Extend ADR-0009 with `requires_any`, `integrates_with` and feature requirements.
3. Add those mechanisms, with tests, to the module-system task. That is P1.1a Task 11 if it has not run yet, otherwise P1.1b.
4. Encode each app's manifest as it is built (its `module.py` `depends_on` must match this table). Add a test that compares the installed catalog against this graph, so drift is caught.
