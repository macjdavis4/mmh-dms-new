# Progress

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation | **In review** |
| 2 | Customers and forklift units | Not started |
| 3 | Batch import | Not started |
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
