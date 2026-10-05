# Reliability

## Service level objective

**99.0% monthly availability** for https://dms.maine-material.com, measured by the DigitalOcean Uptime check on `/readyz` (the database is reachable and migrations are current).

That allows about **7 hours 18 minutes** of downtime a month. Planned maintenance counts toward it. Use read-only mode and the banner to give notice.

**Data integrity is not negotiable.** We will accept downtime to avoid losing or corrupting data.

## Recovery targets

| Failure | Data loss at most (RPO) | Back in service (RTO) | How |
|---|---|---|---|
| Bad deploy | none | 2 minutes | Automatic rollback during deploy, or *Actions → Rollback* |
| App server lost | none (it holds no data) | 1 hour | Terraform rebuild, then redeploy ([RUNBOOK](RUNBOOK.md#rebuild-the-server-from-scratch-target-under-1-hour)) |
| Database lost or corrupted | minutes | 1 to 2 hours | DigitalOcean point-in-time recovery (7 days) |
| DigitalOcean backups unavailable | 24 hours | 2 to 4 hours | Nightly encrypted `pg_dump` in a second region (30 days) |
| Primary region outage | 24 hours | half a day | Restore dump and media copy into a new region with the same Terraform |
| Uploaded file overwritten or deleted | none | minutes | Spaces versioning, plus the nightly second-region copy |

## Safeguards built in

**Data**
- Postgres constraints (foreign keys, unique, check, NOT NULL) so the database itself refuses bad data.
- Nothing is hard-deleted. A database trigger refuses `DELETE` on soft-delete tables.
- An append-only audit log (who, what, when, before and after values). A trigger refuses edits and deletes.
- Multi-step writes run in transactions.
- Migrations are expand/contract only, linted in CI (`django-migration-linter`).

**Backups**
- DigitalOcean Managed PostgreSQL: daily backups and 7-day point-in-time recovery.
- Nightly at about 2 AM: an encrypted (`age`) `pg_dump` of a consistent snapshot to the backup bucket in **San Francisco**. Row counts are recorded from the same snapshot and kept 30 days. Deleted or overwritten backups are kept another 30 days by bucket versioning.
- Nightly copy of all uploaded files to the second region. The media bucket is versioned too.
- Droplet backups (daily) for production, as a convenience. The Droplet holds no data.
- **Monthly restore test** (GitHub Actions, the 3rd of each month): restores the newest dump into a scratch database, checks every table's row count against the backup's manifest, and fails if the newest backup is more than 48 hours old. A failure opens an `urgent` issue and emails the admins.

**Availability**
- Blue/green deploys with readiness checks and smoke tests; automatic rollback on failure. Tested locally with zero failed requests during a switch.
- `/healthz` (process alive) and `/readyz` (database and migrations) health checks.
- The app reconnects cleanly after a database restart (`CONN_HEALTH_CHECKS`, connection timeouts, and a closed connection after a failed check).
- Containers restart automatically, and Docker's `live-restore` keeps them running through Docker upgrades.
- Unattended security updates, with an automatic reboot at 3:30 AM when needed.

**Monitoring and alerts**
- DigitalOcean Uptime on `/readyz` from two regions (down after 2 minutes, plus certificate expiry), by email.
- UptimeRobot as an independent second check.
- DigitalOcean Monitoring: CPU above 85%, memory above 90%, disk above 80%.
- Sentry for application errors, backend and frontend.
- JSON logs with a request ID on every line (the Cloudflare ray ID when present).
- The admin dashboard shows database, schema, background job and last-backup status.

## Known single points of failure (accepted for cost)

- **One Droplet**: an outage there means downtime, but no data loss. Rebuild takes under an hour.
- **Single-node database**: DigitalOcean replaces a failed node automatically (minutes to an hour). A standby node would add about $30 a month.
- **Cloudflare**: if Cloudflare is down, the DMS is unreachable. Cloudflare's own uptime is far higher than our SLO.
