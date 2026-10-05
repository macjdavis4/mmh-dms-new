# Maine Material Handling DMS

The dealer management system for Maine Material Handling (Bangor, Maine): customers, forklift unit records, service work orders, sales and parts inventory. Staff only, at `dms.maine-material.com`.

- **Start here for setup:** [docs/MANUAL_STEPS.md](docs/MANUAL_STEPS.md)
- **Day-to-day operations and incidents:** [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **Uptime goal and backups:** [docs/RELIABILITY.md](docs/RELIABILITY.md)
- **How it fits together:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **What's done:** [docs/PROGRESS.md](docs/PROGRESS.md)
- **Project rules:** [CLAUDE.md](CLAUDE.md)

## Quick start (development)

```bash
make up                     # http://localhost:5173
# sign in as sales@mmh.test / Forklift-Demo-2026!
make test && make e2e
```

Stack: Django 5.2 LTS · DRF · PostgreSQL 16 · Procrastinate · React · TypeScript · Vite · Tailwind · shadcn/ui · TanStack Query and Table · Caddy · Terraform on DigitalOcean · Cloudflare.
