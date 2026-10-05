# CLAUDE.md: Maine Material Handling DMS

This file defines the stack, architecture, data model, and rules for this project. Follow it on every task. If something here conflicts with a request, stop and ask.

## Project context
- **What:** A dealer management system (DMS) for Maine Material Handling, an authorized Hyundai Material Handling forklift dealer in Bangor, Maine. We sell new and used forklifts and service them.
- **Domain:** `dms.maine-material.com`
- **Users:** owners, salespeople, mechanics, and parts staff. Not technical. Mechanics use tablets in the shop and phones in the field.
- **Priorities, in order:** data integrity, security, reliability, usability, features, speed of delivery.

## Working environment
You are Claude Code on the web, working in this GitHub repo from a cloud sandbox.
- All work goes through branches, commits, and pull requests. One PR per phase.
- You cannot SSH into servers or use the DigitalOcean console. Infrastructure is code (Terraform) and deploys run through GitHub Actions. Secrets live in GitHub Actions secrets and DigitalOcean, never in the repo.
- Your sandbox may block outbound access to DigitalOcean and other services. Do not depend on it. Anything I must do by hand goes in `docs/MANUAL_STEPS.md`, step by step for a non-specialist.
- The full app must run in the sandbox with Docker Compose (local Postgres, MinIO in place of Spaces) so you can run every test before each PR.

## Stack
Mature, widely supported technology with long security support. Do not add new frameworks or services without asking.
- **Backend:** Python, Django (current LTS release), Django REST Framework. Pin dependencies with hashes.
- **Database:** PostgreSQL only.
- **Background jobs:** Postgres-backed queue (Procrastinate or django-q2 with the ORM broker). No Redis.
- **Frontend:** React, TypeScript (strict), Vite, Tailwind CSS, shadcn/ui, TanStack Query, TanStack Table. Built to static files and served from the same origin as the API.
- **Web server:** Gunicorn behind Caddy (automatic Let's Encrypt).
- **Auth:** Django auth, Argon2 hashing, database-backed secure session cookies, TOTP 2FA required for admins and optional for others.
- **File storage:** DigitalOcean Spaces (S3 compatible). MinIO locally.
- **Testing:** pytest, Vitest, Playwright (end-to-end tests and UI screenshots for every phase).
- **Observability:** Sentry, structured JSON logs, DigitalOcean Monitoring, DigitalOcean Uptime plus one third-party monitor on `/readyz`.

## Infrastructure (Terraform, DigitalOcean)
- **DNS:** Cloudflare, proxied, for DDoS protection and WAF. HTTPS only, HSTS.
- **App:** one Droplet running Docker Compose. The app is stateless: no files or sessions on the Droplet disk, so it can be rebuilt from Terraform and the image in under an hour. Droplet backups enabled.
- **Database:** DigitalOcean Managed PostgreSQL, single node, daily backups and point-in-time recovery, `sslmode=require` with the DO CA certificate, trusted sources limited to the Droplet, DO connection pooler. The app must reconnect cleanly after a database restart.
- **Files:** Spaces with versioning on and a nightly copy to a bucket in a second region.
- **Extra backups:** nightly encrypted `pg_dump` to Spaces in a second region, kept 30 days, plus an automated monthly restore test into a scratch database that checks row counts and alerts on failure.
- **Staging:** smallest Droplet and database sizes, same Terraform modules. Every merge deploys to staging first. Production deploys need manual approval in GitHub.
- **Hardening:** web traffic on 80/443 only (from Cloudflare), SSH key-only from a named IP, UFW and DO Cloud Firewall, unattended security updates, fail2ban, non-root containers, read-only container filesystems where possible, login rate limiting and lockout, CSP and security headers, dependency and image vulnerability scanning in CI.

## Reliability rules
- **SLO:** 99.0% monthly uptime. Document it and the recovery procedures in `docs/RELIABILITY.md`.
- **Data must never be lost.** Uptime is negotiable; data integrity is not.
- **Deploys:** blue/green on the Droplet. Start the new container, wait for `/readyz`, switch Caddy, run smoke tests, stop the old one. Roll back automatically on failure.
- **Migrations:** expand and contract only. Every migration must work with the code currently running. Never rename or drop a column in the same release that stops using it. Lint migrations in CI (django-migration-linter).
- **Health checks:** `/healthz` (process alive) and `/readyz` (database reachable, migrations current).
- **Read-only mode** and a maintenance banner, switchable by an admin.
- Feature flags for large features.

## Data rules
- Use real database constraints: foreign keys, unique, check, NOT NULL. The database should refuse bad data on its own.
- Wrap every multi-step write in a transaction.
- Nothing is hard deleted. Soft delete everything and keep an audit log (who, what, when, before and after values).
- Money is stored as integer cents or `Decimal`, never floats.
- Unit serial numbers are unique, enforced in the database.
- Store hand-entered and imported values as entered. Normalize into separate fields only when the value parses cleanly.
- Parts quantities come from an append-only stock movement ledger. On-hand is always derivable from the ledger. A nightly job checks for drift and alerts.
- Background jobs must be idempotent and safe to retry.

## Roles and permissions
Roles: `admin`, `sales`, `service`, `parts`, `read_only`. Enforce permissions server side on every endpoint. Cost, asking price, and sale price are visible to `admin` and `sales` only. Every new endpoint gets tests proving each role can do only what it should.

## Data model: forklift unit (from our paper "Eagle 1-84" cards)
Every field on the card must exist.

- **Header:** customer, card date, mechanic, work order #, condition (new / used), hour meter (stored as dated readings).
- **Components** (each has make, model, serial): unit, engine, generator/alternator, electrical controller, ignition system, fuel system, hydraulic pump, control valve (plus spools: 2SP / 3SP / 4SP), transmission.
- **Mast:** manufacturer, type, size.
- **Lift cylinder #:** free text.
- **Forks:** dimensions as text (e.g. `1.75 x 4 x 48 STD`), multiple allowed.
- **Carriage.**
- **Backrest:** height, width.
- **Tilt:** forward degrees, back degrees, reference #.
- **Tires:** type, drive size, steer size, free text extras (e.g. rim size).
- **Electrics:** battery manufacturer, model, serial, volts, amp-hours, size (W x L x H), weight; charger make, model, serial.
- **Attachments** (multiple): manufacturer, type, model, serial, date code, hose reel (bool), internal hose (bool), reel #, side (LH / RH).
- **Special equipment, field modifications, notes:** free text.
- **Also:** photos, scanned original card, ownership history (customer or our stock), stock status (available, on hold, sold, in prep), cost, asking price, sale price, `needs_review` flag.

Example values seen on real cards: units Hyundai 35LN-9A and Doosan G25N-7; engines Hyundai L4KB and Nissan K25; mast Hyundai TF470, size 69MN-T4715; attachment Cascade SS/FP 65K-FPS-8169-C; tires 8.15-15 drive, 6.50-10 steer, solid.

## Import format
- CSV, one row per unit, snake_case headers with component prefixes, e.g. `customer_name, card_date, mechanic, work_order_number, condition, hour_meter, unit_make, unit_model, unit_serial, engine_make, engine_model, engine_serial, ..., mast_make, mast_type, mast_size, forks, tire_type, tire_drive_size, tire_steer_size, battery_mfg, ..., attachment_1_mfg, attachment_1_type, attachment_1_model, attachment_1_serial, ..., special_equipment, field_modifications, notes, source_image_filename`.
- Same data as JSON through a versioned, API-key authenticated, rate-limited endpoint.
- Documented in `docs/IMPORT_FORMAT.md` with a JSON Schema, a CSV template, and a sample file.
- Imports are idempotent (match on unit serial), logged, and reversible by batch.

## Design rules
- Clean and modern, in the spirit of the Hyundai Material Handling website: white and light gray surfaces, deep navy primary, one bright accent for calls to action, bold sans-serif headings, card layouts, large equipment photos.
- Never copy Hyundai's site, logos, or trademarks. Use Maine Material Handling branding, with a placeholder slot for an "Authorized Hyundai Dealer" badge.
- Tablet and phone first: large tap targets, tables collapse to cards on small screens, fast on slow connections.
- Global search (customer, serial, work order, part number) on every page.
- Light and dark mode. WCAG 2.1 AA.
- Plain labels, sensible defaults, inline validation, confirmation before destructive actions, undo where possible.

## Phase workflow (follow exactly, every phase)
1. **Start clean.** Pull the latest `main` and create a branch named `phase-N-short-name` (e.g. `phase-2-customers-units`).
2. **Build** the phase. Commit in small, logical steps with conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
3. **Verify.** Lint, typecheck, migration lint, and the full test suite must pass locally. Fix anything failing; never skip or disable a test to get green.
4. **Screenshots.** Run the app with seed data and use Playwright to capture every new or changed screen at desktop (1440px), tablet (1024px), and phone (390px) widths, in light and dark mode, plus key states (empty, error, loading, filled form). Save them to `docs/screenshots/phase-N/` with clear names (e.g. `unit-detail-tablet-dark.png`) and show them to me in the chat.
5. **Docs.** Update `docs/PROGRESS.md`, `docs/RUNBOOK.md`, `docs/MANUAL_STEPS.md`, and seed data.
6. **Pull request.** Push and open a PR titled `Phase N: <name>`. The description includes: what was built, screenshots embedded from `docs/screenshots/phase-N/`, test results and coverage, migrations added, any manual steps for me, and known limitations.
7. **CI must be green.** Wait for all GitHub Actions checks on the PR. If any fail, fix and push until every check passes.
8. **Summarize and stop.** Give me a short summary with the PR link. Do not start the next phase until I tell you the PR is merged. If I request changes, make them on the same branch, re-run steps 3 to 7, and stop again.
