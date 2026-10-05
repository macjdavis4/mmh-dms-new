# Progress

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation | Merged |
| 2 | Customers and forklift units | Merged |
| 3 | Batch import | **In review** |
| 4 | Service | Not started |
| 5 | Sales | Not started |
| 6 | Parts inventory | Not started |
| 7 | Dashboard, reports and continuity | Not started |
| 8 | Offline work orders (optional) | Ask before starting |

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
