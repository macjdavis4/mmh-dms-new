# Progress

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation | Merged |
| 2 | Customers and forklift units | Merged |
| 3 | Batch import | Merged |
| 4 | Work orders | Merged |
| 5 | Planned maintenance | **In review** |
| 6 | Printouts (work order and spec sheet PDFs) | Not started |
| 7 | Units changing hands (sales, trade-ins, repos) | Not started |
| 8 | Quotes and sales | Not started |
| 9 | Parts catalog | Not started |
| 10 | Parts stock ledger | Not started |
| 11 | Receiving parts invoices | Not started |
| 12 | Dashboard and reports | Not started |
| 13 | Continuity (offline-ready app, paper fallback) | Not started |
| 14 | Offline work orders (optional) | Ask before starting |

From Phase 4 on, phases are smaller (one usable piece each) so each pull request stays easy to review.

| Phase | Delivers |
|---|---|
| 4 | Work orders: create, assign, status, complaint / cause / correction, labor hours, hour meter at service, service history on the unit |
| 5 | Planned maintenance by hours or calendar, due-soon list, work order from a due item |
| 6 | Work order PDF and unit spec sheet PDF |
| 7 | Why a unit changed hands, status and condition following the owner, buy and sell records with their own prices |
| 8 | Quotes, quote PDF, sales with trade-ins |
| 9 | Parts, bins, reorder points, supersessions, cross references |
| 10 | Append-only stock ledger, parts used on work orders, nightly drift check, low-stock list |
| 11 | Invoice upload, text extraction / OCR, review, partial receipts and backorders |
| 12 | Dashboard tiles and reports (including parts valuation) |
| 13 | Offline-ready app for recent units and the parts catalog; nightly CSV/PDF paper-fallback exports |

## Phase 1: Foundation

**Built**
- [x] Repo scaffold; Docker Compose dev stack (Postgres 16, MinIO, Django, worker, Vite); Makefile
- [x] Django 5.2 LTS + DRF; dependencies pinned with hashes
- [x] Custom user with roles; Argon2; database sessions; CSRF; login lockout (django-axes) and rate limits
- [x] TOTP 2FA with recovery codes: required for admins (enforced by middleware), optional for others
- [x] Audited and soft-delete base models; append-only audit log; Postgres triggers block hard deletes and audit edits
- [x] Site settings: read-only mode and maintenance banner; feature flags
- [x] `/healthz`, `/readyz`; Sentry (backend and frontend); JSON logs with request IDs; CSP and security headers
- [x] React app shell: branding, role-aware navigation, global search (press `/`), light and dark mode, phone drawer
- [x] Screens: sign in, 2FA code, 2FA setup with recovery codes, dashboard, users, site settings, audit log, my account, coming soon, 404
- [x] Procrastinate worker: nightly encrypted `pg_dump` with row-count manifest, nightly media copy, job cleanup
- [x] CI: ruff, mypy, ESLint, tsc, pytest, Vitest, Playwright, migration lint, pip-audit, npm audit, Trivy, gitleaks, ShellCheck, Terraform validate and test
- [x] Terraform for staging and production (Droplet, firewall, reserved IP, managed Postgres + pool, Spaces, Cloudflare DNS and rules, uptime and alerts)
- [x] Blue/green deploy with smoke tests and automatic rollback; rollback workflow; monthly restore test
- [x] Docs: MANUAL_STEPS, RUNBOOK, RELIABILITY, ARCHITECTURE

**Waiting on the owner** (see [MANUAL_STEPS](MANUAL_STEPS.md)): accounts, tokens, Terraform apply, and the first deploy of the empty shell to staging and production.

## Phase 2: Customers and forklift units

**Built**
- [x] Customers (business or individual) with any number of contacts and addresses; one main contact and one main address each; account numbers unique (ignoring case)
- [x] Forklift units with every field on the Eagle 1-84 card: header, eight components (make, model, serial; spools on the control valve), mast, lift cylinder, forks (several, dimensions kept as written and parsed when clean), carriage, backrest, tilt, tires, battery and charger, attachments (several), special equipment, field modifications, notes
- [x] Hour meter readings as dated history (warns when a reading goes backwards); ownership history (customer or our stock) with "change owner"
- [x] Photos and scanned cards: stored in Spaces (MinIO locally), checked by content, thumbnails made on upload, streamed through the app with permission checks; set the main photo; remove with undo
- [x] Stock status, cost, asking price, sale price, needs-review flag and note
- [x] Unit serials unique in the database, ignoring case, spaces and dashes, including removed units; live duplicate warning while typing
- [x] Prices hidden server side from service, parts and read-only (fields removed, price filters and sorting ignored), with role-matrix tests
- [x] Inventory: in stock / customer units / all; photo cards or table; filters for new/used, make, model, fuel, capacity, lift height, price, status, needs review; filters kept in the link
- [x] Unit detail page, full unit card form (add and edit), customer pages; dashboard shows the live stock count
- [x] Global search finds customers (by name, account, phone, contact, town) and units (any serial on the unit, stock number, make and model)
- [x] Everything behind the `customers-units` feature flag (on)
- [x] Production migrations now run as the database owner; the app connects as `mmh_app`, which can read and write rows but not change the schema
- [x] Demo data: 6 customers and 10 units using real card values, with placeholder photos and a sample scanned card

**Tests**: 168 backend tests (88% coverage), 23 Vitest, 25 Playwright end-to-end tests, local blue/green deploy test.

**Waiting on the owner**: nothing new beyond Phase 1's [MANUAL_STEPS](MANUAL_STEPS.md) (see "Phase 2" there).

## Phase 3: Batch import

**Built**
- [x] Import format: one CSV row (or JSON object) per unit card, every card field. Documented in [IMPORT_FORMAT.md](IMPORT_FORMAT.md) with a template, a sample, a JSON Schema and a sample API request, all generated from one spec (a test fails if they drift)
- [x] Template and sample downloadable in the app (*Imports → Download template*)
- [x] Upload a CSV (Excel's CSV UTF-8 or plain CSV; semicolons accepted; an .xlsx is explained, not accepted) with optional scans of the cards
- [x] Preview before anything changes: each row marked new / update / no changes / can't import, with errors, warnings and the fields that would change
- [x] Units matched on serial (ignoring case, spaces and dashes), else stock number; importing the same file again changes nothing
- [x] Customers matched by name ("Co." = "Company"); near-duplicates flagged; new customers added once per file
- [x] Values that don't parse (e.g. "5 ton") kept as written in the notes; units with warnings flagged *Needs review*
- [x] Blank cells never erase data; the owner of a known unit is never changed by an import
- [x] Scanned cards attached to their unit by file name (`source_image_filename`)
- [x] Import, retry after a failure, discard, and undo a whole batch (units edited since are kept and listed)
- [x] Large files (over 300 rows) import in the background worker; the page follows progress
- [x] Versioned JSON API (`/api/v1/import/v1/…`) with API keys (stored hashed, shown once, revocable), dry runs, per-key rate limit
- [x] Admin page for API keys; dashboard "Import unit cards" action
- [x] Everything behind the `batch-import` feature flag (on); every import change is in the audit log, tagged with its batch

**Tests**: 206 backend tests (90% coverage), 28 Vitest, 31 Playwright end-to-end tests, local blue/green deploy test.

**Waiting on the owner**: nothing to set up. Fill in the template when the cards are scanned (see [MANUAL_STEPS](MANUAL_STEPS.md), "Phase 3").

## Phase 4: Work orders

**Built**
- [x] Work orders numbered WO-20001 upwards (a database sequence; old cards' 4-digit numbers can't clash)
- [x] Unit, customer (taken from the unit's current owner), type, shop or field, mechanic, due date, customer PO, on-site contact, notes
- [x] Status: open → in progress → on hold (with what it's waiting for) → completed, or cancelled; reopen. Completing needs the correction, also enforced by the database
- [x] Complaint / cause / correction; labor lines (mechanic, date, hours, what was done), remove with undo
- [x] Hour meter at service saved as a dated reading on the unit (warns if lower than before)
- [x] Service list (open, completed, cancelled, all; "Mine"; search), service history on the unit page, dashboard tile and quick action
- [x] Global search finds work orders by number and units by the work order number on an old card
- [x] Roles: admin and service edit; sales, parts and read-only can look; only admin removes
- [x] Demo work orders in the seed data; behind the `service` feature flag (on)

**Tests**: 221 backend tests (92% coverage), 31 Vitest, 35 Playwright end-to-end tests.

## Phase 5: Planned maintenance

**Built**
- [x] Maintenance plans per unit: every N hours and/or every N days, whichever comes first, counted from when it was last done; common presets (250 / 500 / 1000-hour service, annual inspection); pause or remove with undo
- [x] Due list: overdue, or due within 30 days / 50 hours (never more than a quarter of the interval in days or a fifth in hours, so a monthly check isn't always "due soon"), most urgent first; option to show every plan
- [x] One click makes a planned-maintenance work order with the plan's tasks; completing it marks the plan done (date and hour meter), reopening puts it back
- [x] Plans on the unit page; "Maintenance due" in the menu and on the Service page; dashboard "PM due in 30 days" tile is live
- [x] The menu highlights only the most specific item (Maintenance due, not also Service)
- [x] Database checks: a plan needs an interval, and counting by hours needs a starting reading
- [x] Demo plans in the seed data (overdue by hours, overdue by date, due soon, up to date)

**Tests**: 245 backend tests, 36 Vitest, 37 Playwright end-to-end tests.

## Planned for Phase 7: units that come back

A unit can be sold, come back (repossession, trade-in, buy-back, lease return, bought used) and be sold again, any number of times. It always stays one unit record (one serial), with its ownership history as the timeline. Phase 7 adds:

- **Why it changed hands** on every ownership change: sold, trade-in, repossession, bought back, lease return, other.
- **Stock status and condition follow the owner**: coming back to our stock sets *In prep* and *Used*; a sale sets *Sold*.
- **A record per sale and per acquisition**, each with its own price and cost, so a second sale never overwrites the first. The unit's cost and prices become "this time in stock".
