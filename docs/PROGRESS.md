# Progress

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation | Merged |
| 2 | Customers and forklift units | Merged |
| 3 | Batch import | Merged |
| 4 | Work orders | Merged |
| 5 | Planned maintenance | Merged |
| 6 | Printouts (work order and spec sheet PDFs) | Merged |
| 7 | Units changing hands (sales, trade-ins, repos) | Merged |
| 8 | Quotes and sales | Merged |
| 9 | Parts catalog | Merged |
| 10 | Parts stock ledger | **In review** |
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

**Tests**: 244 backend tests (92% coverage), 36 Vitest, 37 Playwright end-to-end tests.

## Phase 6: Printouts

**Built**
- [x] Work order PDF (*Print* on any work order): customer, unit, hour meter, complaint / cause / correction, labor with totals, parts used; while the job is open it leaves boxes and lines to write on, plus technician and customer signatures
- [x] Unit spec sheet PDF (*Spec sheet* on any unit): main photo, key specs, components, mast, tires, forks, battery and charger, attachments, special equipment. Admin and sales can choose a version with the asking price. Cost and internal notes are never printed
- [x] Shared letterhead (company name, address, phone, website; a marked slot for the Authorized Hyundai Dealer badge) and a footer with what was printed and when
- [x] ReportLab (pure Python, BSD licence) generates the PDFs; no new system packages
- [x] Sample PDFs and pictures of their pages in `docs/screenshots/phase-6/`

**Tests**: 253 backend tests, 36 Vitest, 39 Playwright end-to-end tests.

## Phase 7: Units changing hands

A unit can be sold, come back and be sold again any number of times. It stays one unit record (one serial), with its ownership history as the timeline.

**Built**
- [x] **Why it changed hands** on every change: sold, sold between customers, trade-in, repossession, bought back, lease return, bought used, other. The database refuses a reason that doesn't fit the new owner
- [x] **Change owner** asks what happened (sold to a customer / came back to our stock / between customers), why, the date (not in the future), price, hour meter at handover and invoice #, and shows *What will change* before saving
- [x] **Stock status and condition follow the owner**: a sale sets *Sold*; coming back sets *In prep* and *Used*
- [x] **Each deal keeps its own numbers**: a sale keeps its sale price and the unit's cost at the time (so its margin); a unit coming back keeps what we paid, which becomes the unit's cost. The unit's cost, asking and sale price are now "this time in stock" and start afresh when it comes back. Sale prices recorded before this phase are copied onto the old sale when the unit comes back
- [x] Ownership history on the unit page shows each reason, the deal's money (admin and sales only), invoice # and hours
- [x] Correct a recorded deal (admin, sales); admins can undo the latest change. Undo puts stock status, condition and prices back, except fields changed by hand since (it lists them); the undone record stays in the audit log
- [x] **Bought and sold** page (admin, sales, read only): every change, filters for direction, reason, dates and search, totals for sales, margin and what we paid (money for admin and sales only); tables become cards on phones and tablets
- [x] Customers show *Units they used to own*
- [x] Behind the `units-changing-hands` feature flag (on) for the list; demo data has a unit sold new and traded back in, and a repossession

**Migrations**: `units/0004_ownership_deals` (new nullable or defaulted columns and checks every existing row passes; no index built on the live table), `units/0005_feature_flag`.

**Tests**: 283 backend tests (93% coverage), 42 Vitest, 43 Playwright end-to-end tests.

**Known limitations**: only the latest change can be undone; to fix an older owner or date, undo back to it or ask an admin to correct it in the Django admin. Quotes, invoices and trade-ins as part of a sale come in Phase 8.

## Phase 8: Quotes and sales

**Built**
- [x] Quotes numbered Q-30001 upwards and sales S-40001 upwards (database sequences)
- [x] A quote has a customer, attention, customer PO, date and valid-until date (shown as *Expired* after it), salesperson, printed terms and internal notes
- [x] Items: units from our stock (priced at their asking price to start), attachments and options, delivery, service and warranty, other items, and discounts; each taxed or not
- [x] Trade-ins: one of the customer's units we know, or one described on the quote (make, model, serial, year), with hours, allowance, payoff and who it's owed to, and condition notes
- [x] Totals worked out the same way on the screen and the server, to the cent: subtotal, less trade-in allowance, plus payoff, plus Maine sales tax (5.5% by default, per quote) on taxed items less the allowance; tax-exempt customers with their certificate #
- [x] Status: draft, sent, accepted, declined, cancelled (reopen); a declined, cancelled or sold quote is locked
- [x] Quote PDF for the customer with a line to sign; internal notes and our cost are never printed
- [x] **Record sale**: checks every unit first (in our stock, not sold, trade-in serial not already ours), then in one transaction sells each unit to the customer (reason *sold*, the line's price) and takes each trade-in into our stock (reason *trade-in*, the allowance); a described trade-in is added as a unit. Totals are kept as they were on the day. Shows up in *Bought and sold* with the sale number
- [x] Admins can **void a sale** while its units haven't changed hands since; everything goes back and the quote reopens as accepted
- [x] Sales page (open, sold, declined, all; search by quote or sale #, invoice #, customer, serial, model or PO; "Mine"), *Quote this unit* on stock units, *New quote* on customers, quotes in global search
- [x] Admin and sales only (quotes carry prices), behind the `sales` feature flag (on); demo data has a draft, a sent quote with a trade-in and payoff, an accepted quote, and a recorded sale with a described trade-in

**Migrations**: `sales/0001_initial` (new tables and the two number sequences), `sales/0002_db_guards` (no hard deletes; the sale-to-ownership links are append-only), `sales/0003_feature_flag`.

**Tests**: 310 backend tests (93% coverage), 47 Vitest, 47 Playwright end-to-end tests.

**Known limitations**: a sale's unit price is the line price; a quote-wide discount isn't spread over the units on the sale records. Sales tax follows the rule above; check it with your accountant. No deposits, payments or invoices yet (invoice # is typed in). Quotes can't be emailed from the app yet.

## Phase 10: Parts stock ledger

**Built**
- [x] **Append-only stock ledger**: every change to a part's stock is a line (opening count, received, used on a work order, returned from a work order, count adjustment, reversal) with who, when, how many, the count after, cost and price. The database refuses edits and deletes; a mistake is put right with a reversing line
- [x] **On hand** is kept with each line in the same transaction and can never go below zero (checked by the app and the database). "Only 2 on hand. If the shelf has more, count it first."
- [x] **Receive** (how many, our cost from the invoice, invoice #) and **Count** (enter what's on the shelf; the first count is the opening count, later ones record the difference) on the part page, for parts staff and admins
- [x] **Stock history** on the part page, newest first, with a reverse button for parts staff and admins
- [x] **Parts on work orders**: service, parts staff and admins add parts to an open work order (the picker shows how many are on hand) and return unused ones. Parts are priced at the list price when taken; the work order page and its printout list them with a total. A work order with parts on it can't be cancelled until they're returned
- [x] **Low stock**: a page (and menu item) listing parts at or below their reorder point by bin, with how many to order and the supplier; the parts list shows *On hand* and filters by low, in stock and out of stock
- [x] **Nightly stock check** (07:00 UTC, Procrastinate): recomputes every part's count from its history and compares. Any difference is recorded, shown at the top of *Low stock*, and logged as an error so Sentry alerts. Nothing is changed automatically. Admins can run it now with *Check now*; `manage.py check_stock` does the same
- [x] A part with stock on hand can't be removed (count it to zero first)
- [x] Mechanics, sales and read-only see quantities and history but not our cost
- [x] Behind the `parts-stock` feature flag (on); demo data has opening counts, one delivery, parts on the three open demo work orders, and five parts low
- [x] Test fix: the end-to-end browser now runs in Eastern time like the server (tests failed between 8 pm and midnight)

**Migrations**: `parts/0004_stock_ledger` (new tables), `parts/0005_stock_guards` (append-only ledger, no hard deletes of stock rows), `parts/0006_stock_flag`.

**Tests**: 344 backend tests (93% coverage), 48 Vitest, 52 Playwright end-to-end tests.

**Known limitations**: receiving is by hand until invoices arrive (Phase 11). No transfer between bins or stores. Prices on a work order are list prices; no discounts or markups per customer yet. Parts on a work order aren't billed anywhere yet (no invoicing).

## Phase 9: Parts catalog

**Built**
- [x] Parts with maker, part number (kept as written), description, category, unit (each, pair, set, kit, box, foot, quart, gallon), list price, our cost, bin, reorder point and quantity, supplier and the supplier's number, the models it fits, and notes
- [x] Part numbers match without case, spaces or dashes ("31n4 01050" finds 31N4-01050). One record per maker and number, enforced by the database, removed parts included (restore instead); a live warning while typing
- [x] **Bins**: shelf codes (unique, kept upper case) with a description and a part count; a bin with parts in it can't be removed
- [x] **Reorder point and quantity**, ready for the low-stock list when the stock ledger arrives (Phase 10)
- [x] **Supersessions**: a part can be replaced by a newer one; the page shows what replaced it and the current part at the end of the chain, and what it replaces. Chains can't loop; replaced parts are hidden from the list unless asked for
- [x] **Cross references**: other brands' numbers for the same part, found by the parts search and the global search
- [x] Parts page (search, category and bin filters), part page, add and edit form, bins page; Parts is in the menu (no more "Soon")
- [x] Parts staff and admins edit; everyone can look parts up. List prices for everyone, our cost for admin, sales and parts only
- [x] Behind the `parts` feature flag (on); demo data has 9 bins and 14 parts with cross references and one replaced part (made-up numbers, marked as demo)

**Migrations**: `parts/0001_initial` (new tables), `parts/0002_db_guards` (no hard deletes), `parts/0003_feature_flag`.

**Tests**: 327 backend tests (93% coverage), 47 Vitest, 50 Playwright end-to-end tests.

**Known limitations**: no quantities on hand yet (Phase 10). No parts import from a spreadsheet yet; parts are added one at a time. One bin per part.

