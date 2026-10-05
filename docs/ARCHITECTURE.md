# Architecture

```
          Staff (tablets, phones, desktops)
                       │ HTTPS
                       ▼
   Cloudflare (DNS, proxy, WAF, DDoS)  dms.maine-material.com · staging-dms.maine-material.com
                       │ 443 from Cloudflare IPs only (DO Cloud Firewall + UFW)
                       ▼
 ┌───────────── Droplet (Ubuntu 24.04, Docker Compose, no data) ─────────────┐
 │  Caddy (Let's Encrypt via Cloudflare DNS challenge, HSTS, gzip/zstd)      │
 │     │ active.caddy → app-blue or app-green                               │
 │  app-blue / app-green: Gunicorn + Django + built React (WhiteNoise)       │
 │  worker: Procrastinate (nightly backups, media copy, job cleanup)         │
 └──────────────┬──────────────────────────────────────────┬──────────────────┘
   private VPC, TLS (sslmode=require + DO CA)               │ S3 API
                ▼                                           ▼
   DO Managed PostgreSQL 16                     Spaces NYC3: media (versioned)
   web via PgBouncer (transaction mode)         Spaces SFO3: backups (versioned,
   worker/migrations direct                       30-day expiry), media copy
   daily backups + 7-day PITR
```

## Decisions

| Topic | Choice | Why |
|---|---|---|
| Framework | Django 5.2 LTS, DRF | Security support until April 2028 |
| Job queue | Procrastinate (Postgres) | No Redis. Row locks, retries, periodic jobs, queueing locks for idempotency |
| Primary keys | UUID | Safe for imports, the scanning-app API and future offline sync |
| Deletes | Soft delete + Postgres trigger | "Nothing is hard deleted", enforced by the database |
| Audit | Written in the same transaction as the change; append-only trigger | Can't be skipped or edited |
| Bulk ORM `update()`/`delete()` | Blocked on audited models | They would bypass the audit log |
| Sessions, cache, throttling | Postgres | The app stays stateless |
| Frontend serving | Built by Vite into Django static files, served by WhiteNoise | Same origin as the API: no CORS, simple CSP |
| CSP | `script-src 'self'`; inline styles allowed | Radix and Sonner inject small style tags; scripts stay strict |
| TLS at origin | Let's Encrypt via the Cloudflare DNS-01 challenge | Works behind Cloudflare's proxy; Cloudflare "Full (strict)" for DMS hosts only |
| Deploy access | A `deploy` SSH key that may only run the deploy entry point; CI opens port 22 to its own IP for the length of the job | Keeps "SSH only from a named IP" as the standing rule |
| Deploy scripts | Shipped inside the app image | The server always runs the scripts that match the code |
| Secrets | GitHub environment secrets → `/opt/mmh/.env` (0600), rewritten each deploy | Nothing secret in the repo or the image |
| Backups | `age`-encrypted to a public key | A stolen server or bucket key can't read old backups |

## Request flow and security headers

1. Cloudflare terminates TLS for visitors and forwards to Caddy over TLS (Full strict).
2. Caddy trusts `CF-Connecting-IP` **only** from Cloudflare IP ranges (refreshed every 12 hours) and passes it as `X-Real-IP`. It forwards the Cloudflare ray ID as `X-Request-ID`.
3. Django middleware, in order: health checks (before host validation), request context and JSON access log, security headers, CSP, sessions, CSRF, authentication, django-otp, audit actor, **admin 2FA gate**, **read-only mode**, django-axes.
4. DRF: session authentication with CSRF, and role permissions on every endpoint (`HasRole`). Each endpoint has a role-matrix test.

## Roles

`admin`, `sales`, `service`, `parts`, `read_only`. Admins must use TOTP two-factor; for everyone else it is optional. Cost and prices are visible to `admin` and `sales` only (`PRICE_ROLES`, enforced in serializers from Phase 2).

## Repository layout

```
backend/            Django project (config/, apps/core, apps/accounts, apps/search, apps/ops, tests/)
frontend/           React + TypeScript (src/app, src/components, src/features, e2e/)
infra/caddy/        Caddy image and Caddyfile
infra/cloud-init/   Droplet bootstrap and the deploy entry point
infra/deploy/       Blue/green deploy, rollback, production compose (copied into the image)
infra/scripts/      Env builder, restore verifier, local deploy test, e2e runner
infra/terraform/    modules/{app,database,storage,dns,monitoring}, envs/{shared,staging,production}
.github/workflows/  ci, deploy, rollback, terraform, restore-test
docs/               This documentation and phase screenshots
```
