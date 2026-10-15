# Runbook

How to run, test, deploy and fix the Maine Material Handling DMS. Recovery targets and the uptime goal are in [RELIABILITY.md](RELIABILITY.md). One-time setup is in [MANUAL_STEPS.md](MANUAL_STEPS.md).

## Local development

Requirements: Docker with Compose. For running tests outside Docker you also need Python 3.12, Node 22, `age` and the PostgreSQL 16 client.

```bash
make up          # Postgres, MinIO, Django (with demo data), worker, Vite
open http://localhost:5173
make down        # stop (data is kept in Docker volumes)
```

Demo accounts (password `Forklift-Demo-2026!`):

| Email | Role | Notes |
|---|---|---|
| `admin@mmh.test` | admin | 2FA on. Authenticator secret `JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP` |
| `newadmin@mmh.test` | admin | Must set up 2FA on first sign-in |
| `sales@mmh.test` | sales | |
| `service@mmh.test` | service | |
| `parts@mmh.test` | parts | |
| `viewer@mmh.test` | read only | |

`seed_dev` refuses to run in staging or production.

MinIO console (stands in for DigitalOcean Spaces): http://localhost:9001, `minioadmin` / `minioadmin`. The official MinIO images are no longer published, so Compose uses the community build `pgsty/minio`; the backend creates the buckets on start (`manage.py ensure_buckets`, development only).

Demo data (`seed_dev`) also loads 6 customers and 12 forklift units with placeholder photos and a sample scanned card, including units that were sold, traded back in and repossessed (Phase 7). It is safe to run again: existing rows are left alone. It also switches on feature flags for finished phases.

## Checks (what CI runs)

```bash
make lint             # ruff, eslint, shellcheck, terraform fmt
make typecheck        # mypy --strict, tsc --strict
make migrations-lint  # makemigrations --check, django-migration-linter
make test             # pytest (coverage gate 85%), vitest
make e2e              # Playwright against a production-like server
./infra/scripts/check-help-updated.sh origin/main  # the "Help docs" PR check (PR_BODY=... for the opt-out line)
make screenshots      # docs/screenshots/phase-N at 3 widths x light/dark (SCREENSHOT_PHASE=N, default: current phase)
make deploy-test      # run the real blue/green scripts against local Docker
```

CI also builds the production image, checks it runs as non-root on a read-only filesystem, scans it with Trivy, scans dependencies (`pip-audit`, `npm audit`), scans for committed secrets (gitleaks), and validates and plan-tests the Terraform with mocked providers.

## Deploying

- **Staging**: automatic on every merge to `main` (*Actions → Deploy*).
- **Production**: the same run waits for approval. Open the run, *Review deployments → production → Approve*.

What a deploy does on the server (`infra/deploy/deploy.sh`):

1. Pull the new image.
2. Run migrations. They are expand-only, so the running version keeps working.
3. Start the idle color (blue or green) and wait for `/readyz`.
4. Switch Caddy to it (a reload, with no dropped connections).
5. Smoke test through Caddy with the real certificate: `/readyz`, the status API, the app page and a static file.
6. Restart the worker on the new image and stop the old color, keeping it for rollback.

If step 3 or 5 fails, traffic stays on (or returns to) the old version and the workflow fails.

### Roll back

*Actions → **Rollback** → Run workflow → pick the environment*. This brings the previous version back in about a minute. The database is not rolled back, which is safe because migrations are expand/contract.

### Nobody can reach the site (and it should be reachable)

The DMS only accepts visitors from the office address (the VPN exits there). If the office's internet address changed, everyone, including you, sees a Cloudflare "blocked" page. Fix: update `ADMIN_SSH_CIDRS` in the `production` environment, then run *Actions → Terraform* for `shared`, `staging` and `production` with `apply`. In an emergency, turn off the rule **DMS office-only access** in Cloudflare (*Security → WAF → Custom rules*).

### Give someone more than one role

*Admin → Users →* the person *→ Roles*. Tick any mix of **Sales**, **Service** and **Parts** (for example a service writer who also handles parts). **Admin** and **Read only** can't be combined with anything else: untick them first if you want to switch. People with several roles can do everything any one of their roles can do. Nobody gets admin by combining other roles.

### Run a management command on a server

From the office (only the office IP may SSH in):

```bash
ssh mmhadmin@<server-ip>
sudo -u deploy /opt/mmh/current/manage.sh <command>
# examples:
sudo -u deploy /opt/mmh/current/manage.sh createsuperuser
sudo -u deploy /opt/mmh/current/manage.sh reset_2fa person@maine-material.com
sudo -u deploy /opt/mmh/current/manage.sh run_backup --force
cat /opt/mmh/state.env            # which version and color are live
docker ps                          # containers
docker compose -p mmh -f /opt/mmh/current/docker-compose.prod.yml logs --tail 200 app-blue
```

### Database users

Two database users, on purpose:

| User | Used by | Can do |
|---|---|---|
| `doadmin` (owner) | The migrate step of each deploy only. Its URL lives in `/opt/mmh/admin.env`, which no app container loads. | Everything, including schema changes |
| `mmh_app` | The web app and the worker | Read, add, change and (soft) remove rows. Cannot create, alter or drop tables. |

After migrating, the deploy runs `manage.py grant_app_privileges mmh_app`, so new tables are usable by the app straight away. If the app ever logs `permission denied for table ...`, run that command by hand (with `admin.env` loaded) and redeploy.

The deploy **stops** (and keeps the old version running) in two cases that would weaken this split:

- `ADMIN_DATABASE_URL is missing ... refusing to migrate as the app user`: `/opt/mmh/admin.env` is empty or missing. Re-run the deploy; if it repeats, check the `ADMIN_DATABASE_URL` output in Terraform.
- `mmh_app owns <tables>`: a migration once ran as the app user, so it could drop those tables. From the office, connect as `doadmin` (see [MANUAL_STEPS](MANUAL_STEPS.md), "Security audit", step 5) and run `REASSIGN OWNED BY mmh_app TO doadmin;`, then redeploy.

### Customers and units are switched off by mistake

Back office (`/django-admin/`) → *Feature flags* → `customers-units`: tick *Enabled* and save. (Feature flags aren't on the in-app Site settings page.) While it is off, those pages and their API answer "not found"; no data is touched.

### Two units have the same serial

The database refuses it, so this can only be a near-miss (for example `O` vs `0`). Open both, decide which is right, fix the serial on the other or remove it. Removed units keep their serial reserved; restore the removed one instead of adding it again.

### Imports

- An import that **failed part-way** keeps the rows already imported. Open it under *Imports* and press **Try again**; rows already done are skipped.
- An import **stuck on "Waiting" or "Importing"** for more than a few minutes: big files run in the worker on the `imports` queue. Check the worker is running (`docker ps`, `docker compose … logs --tail 200 worker`).
- **Wrong data imported**: open the import and **Undo this import**. Units someone edited after the import are left alone and listed; fix those by hand.
- **Format docs out of date** after changing `backend/apps/imports/columns.py`: run `python manage.py write_import_docs` and commit the files it writes.
- **Scanning app gets 401**: its API key was revoked, or the admin who made it was removed or lost the admin role. Make a new key under *Admin → API keys*. A 429 means more than 30 requests a minute.

### Work orders

- A work order is never deleted, only cancelled (and can be reopened). Only an admin can remove one; removed ones come back with *restore*.
- Planned maintenance counts from each unit's latest hour meter reading. If a plan looks wrongly overdue by hours, check the unit's hour readings for a typo (e.g. 99,999).
- A plan done outside the system (e.g. by another shop): edit the plan and set *Last done on* and *Hour meter then*.
- A wrong hour meter reading on a work order: correct the number in the work order's details. The old reading is replaced (and kept in the change history).

### Printouts

- Work order and spec sheet PDFs are made on request (nothing is stored). If one fails, the error is in Sentry with the work order or unit id.
- The letterhead address and phone come from `COMPANY_ADDRESS` and `COMPANY_PHONE` (GitHub environment variables, see MANUAL_STEPS).
- Pictures of sample PDFs for the docs: `infra/scripts/pdf-to-png.sh docs/screenshots/phase-6` (needs `pdftoppm` from poppler).

### Units changing hands

- A unit is always one record (one serial), however often it is sold and comes back. *Change owner* on the unit page records why (sold, trade-in, repossession, bought back, lease return, bought used, sold between customers, other), the price, the hour meter and the invoice #.
- Coming back to our stock sets *In prep* and *Used*, makes what we paid the unit's cost, and empties the asking and sale price. Selling sets *Sold* and the sale price. Each deal keeps its own price (and, for a sale, the cost at the time) on its ownership record, so the next sale never overwrites the last.
- **Wrong reason, price or invoice #**: admin or sales click the pencil on that record in *Ownership history*. Correcting the current record's price also updates the unit's cost or sale price if it still matched.
- **Wrong owner or date**: an admin undoes the latest change (the undo arrow on the newest record), then records it again. Stock status, condition and prices go back to what they were, except fields changed by hand since (the undo says which). Only the newest change can be undone; the undone record stays in the audit log.
- Sales recorded before Phase 7 have no price on their record. When such a unit comes back, its sale price and cost are copied onto the old sale first.
- *Bought and sold* (admin, sales, read only) lists every change with totals; money is shown to admin and sales only. Switch it off with the `units-changing-hands` flag; *Change owner* keeps working.

### Quotes and sales

- Quotes and sales are admin and sales only. Switch them off with the `sales` flag.
- **Record sale won't go**: the dialog lists why (a unit isn't in our stock, is already sold, or a trade-in serial is already one of our units: pick that unit on the trade-in instead). Fix the quote and try again; nothing changes until every check passes.
- **A sale was recorded by mistake**: an admin opens the quote and clicks *Void sale*. It only works while none of the units has changed hands since; if one has, undo that change on the unit first.
- Sales tax defaults to `SALES_TAX_RATE` (5.5) for new quotes; each quote keeps its own rate.
- Quote numbers come from `sales_quote_number_seq` (Q-30001 up) and sale numbers from `sales_sale_number_seq` (S-40001 up). Gaps are normal (a failed save still uses a number).

### Parts catalog

- Parts staff and admins keep the catalog; everyone can look parts up. Switch it off with the `parts` flag.
- **"Already in the catalog" but nobody can find it**: the part was removed. Open *Parts*, tick *Show replaced parts* and search, or ask an admin to restore it (*django-admin*), rather than adding it again.
- **Search doesn't find a number**: add it as another brand's number on the part (*Edit part → Other brands' numbers*). Search ignores dashes, spaces and case.
- **A maker changed a number**: add the new part, then edit the old one and set *Replaced by*. Don't edit the old number in place; history and invoices refer to it.
- A bin can't be removed while parts are in it; move them to another bin first.

### Parts stock

- Stock is an append-only ledger: lines are never edited or deleted. Switch the stock features off with the `parts-stock` flag (the catalog keeps working).
- **A count is wrong**: count the shelf (*part page → Count*). The difference is recorded as an adjustment.
- **Something was entered by mistake** (received twice, wrong part): reverse the line in the part's *Stock history*. Parts put on a work order by mistake: *Return* them from the work order.
- **"Only N on hand"** when using a part: the record says fewer than the shelf has. Count the shelf first, then add the part.
- **A work order can't be cancelled**: return its parts to stock first.
- **The stock check found differences** (red box on *Low stock*, a Sentry error "stock drift"): the stored count of a part no longer matches its history. Nothing is changed automatically. Run `python manage.py check_stock` to see them again. Find out why (a direct database edit, or a bug) before fixing; then fix the stored count in a database shell with `UPDATE parts_partstock SET on_hand = <ledger value> WHERE part_id = '<id>';` (the ledger is the truth), and run `check_stock` again until it reports no differences.

### Parts invoices

- Admin and parts staff upload invoices under *Parts invoices*; sales can look. Switch it off with the `parts-invoices` flag (receiving by hand on the part page keeps working).
- **Stuck on "Reading the invoice…"**: the worker isn't running or is behind. Check the `worker` container and its log. The job is safe to retry; reading only happens while the invoice is still marked as reading. In development, set `INVOICE_READ_INLINE=true` to read during the upload instead.
- **"The invoice reader isn't installed on the server"**: Tesseract is missing from the image. It is installed by the `Dockerfile`; rebuild and redeploy. PDFs with text still read without it.
- **Read badly**: check against the paper and fix the lines, or *Read again* after uploading a clearer photo (flat, well lit, the whole page). Lines can always be typed in.
- **"Already entered"**: the same supplier invoice number exists. Open the other one; cancel whichever is the mistake (only possible before anything is received from it).
- **Received the wrong amount**: reverse that line in the part's *Stock history*; the quantity goes back on the invoice line, then receive the right amount.
- Try the reader with `python manage.py make_sample_invoice /tmp/sample.pdf` (or `.png`).

### Dashboard and reports

- Dashboard numbers and reports are counted live from the records; nothing is cached or stored, so they always match the rest of the app. Switch the reports off with the `reports` flag (the dashboard keeps its tiles).
- **A number looks wrong**: open the report behind the tile (click it) and the rows that make it up. Fix the underlying record (a unit's cost, a part's cost, a work order's labor); the report follows.
- **A report is slow**: narrow the dates. Ranges are limited to five years.
- **CSV opens with odd characters**: it is UTF-8 with a byte-order mark, which Excel reads correctly when the file is double-clicked.
- Who sees what is set in `apps/reports/definitions.py` (`roles=` on each report and column); change it there and the tests in `tests/test_reports.py` will say whether every role still gets what it should.

### Working when the system is down

- **Devices**: open the app as usual. If it can't reach the system it says so and offers *Open the saved copy* (stock and recent units with spec cards, read-only). A device only has a copy if someone signed in on it while online in the last 14 days. Switch saving off with the `offline` flag; copies are wiped the next time each device reaches the system.
- **Paper**: *Admin > Paper backup* has last night's files. If the site itself is down: sign in at cloud.digitalocean.com → *Spaces Object Storage* → the bucket ending in `-backups` → `paper/production/` → the latest date → download `paper-backup.zip` (or a PDF) and print. Staging files are under `paper/staging/`.
- **A paper backup failed** (red row in System health, error in Sentry): open *Admin > Paper backup* for the error, then *Make one now*. It is safe to run again. Locally: `python manage.py shell -c "from apps.ops.paper import run_paper_backup; print(run_paper_backup(force=True).status)"`.
- **Someone sees an old app after a release**: the app updates itself once all its tabs are closed; closing and reopening the browser is enough.

## Read-only mode and the maintenance banner

*Admin → Site settings*. Read-only mode blocks every change for everyone (sign-in still works) and shows a notice on every screen. Use it during database maintenance or a restore. The banner can show any message in information, warning or critical style, including on the sign-in page.

## In-app help

Signed-in users read how-to articles under **Help** (`/help`), from the **?** button at the top of every page, and in the global search. The articles are Markdown files in `backend/apps/help/articles/`, served by `/api/v1/help` with role-only sections removed on the server. They ship with each release, so a fix to an article goes out like any other change: a pull request, then a deploy.

- **An article is wrong or missing**: edit or add the file (format in [HELP_ARTICLES](HELP_ARTICLES.md)), run `pytest tests/test_help.py` and `npx vitest run src/app/helpCoverage.test.ts`, and open a pull request.
- **Someone can't find an article by searching**: add the words they used to its `keywords:` (or to `SYNONYMS` in `backend/apps/help/search.py`), and pin the search in `test_finds_what_people_type`.
- **Switch Help off**: back office (`/django-admin/`) → *Feature flags* → `help`. The menu item, the **?** button and the Help results in search disappear.
- **Keeping it accurate**: CLAUDE.md requires the help to change with every user-facing change. The **Help docs** check on pull requests enforces it (see [HELP_ARTICLES](HELP_ARTICLES.md), "What enforces this").

## Incidents

### The site is down or `/readyz` fails

1. Check https://dms.maine-material.com/healthz. If it answers, the app is running and the problem is the database: check DigitalOcean → *Databases* for maintenance or failover. The app reconnects by itself when the database comes back.
2. If nothing answers: DigitalOcean → *Droplets → mmh-production-app*. Is it running? Look at *Graphs* (CPU, memory, disk).
3. SSH in (see above), run `docker ps` and look at the logs of the active color (from `/opt/mmh/state.env`).
4. If the latest deploy caused it, roll back.
5. If the Droplet is broken beyond repair, rebuild it (below).

### Rebuild the server from scratch (target: under 1 hour)

No data lives on the Droplet, so it can be replaced.

1. *Actions → Terraform → Run workflow*: environment `production`, action `apply`, replace `module.app.digitalocean_droplet.app`. Approve it. The reserved IP and DNS stay the same.
2. Wait 10 minutes, then redo [MANUAL_STEPS](MANUAL_STEPS.md) step 10 (new SSH fingerprint).
3. *Actions → Deploy → Run workflow*. Approve production.
4. Check `/readyz` and sign in.

### Restore the database

Pick the gentlest option that covers the problem.

**A. Point-in-time recovery (minutes of data loss at most).** For "someone deleted or broke data at 2:15 PM":

1. Turn on **read-only mode** and post a banner.
2. DigitalOcean → *Databases → mmh-production-pg → Backups → Restore from backup*. Choose **a new cluster** and the time just before the problem. Never overwrite the live one.
3. Compare or copy the affected rows from the restored cluster (we'll write a script for the specific case), or switch the app to the restored cluster. To switch: point Terraform at it, or in an emergency put its connection details in the GitHub secrets and redeploy.
4. Turn read-only mode off. Delete the extra cluster when you're sure.

**B. From a nightly encrypted dump (second region).** For the case where DigitalOcean's own backups are unavailable:

```bash
# On a computer with age, the AWS CLI and psql/pg_restore 16:
aws s3 ls --endpoint-url https://sfo3.digitaloceanspaces.com s3://mmh-production-backups/db/production/ --recursive | tail
aws s3 cp --endpoint-url https://sfo3.digitaloceanspaces.com s3://mmh-production-backups/<key>.dump.age .
age --decrypt --identity mmh-backup-key.txt --output restore.dump <key>.dump.age
createdb -h <new-db-host> -U doadmin mmh_restored
pg_restore --no-owner --no-privileges --exit-on-error -h <new-db-host> -U doadmin -d mmh_restored restore.dump
python3 infra/scripts/verify_restore.py <key>.counts.json "postgres://doadmin:...@<new-db-host>:25060/mmh_restored?sslmode=require"
```

The private key (`BACKUP_AGE_IDENTITY`) is in the password manager and on paper in the office safe.

**C. From the locked off-site copy (Backblaze B2).** See the next section.

### Restore from the locked off-site copy (Backblaze B2)

Use this when the DigitalOcean copies are gone or can't be trusted (ransomware, or someone used our DigitalOcean keys to delete things). Nothing in the B2 bucket can be deleted or changed for 30 days, so the last 30 days of copies are always there.

1. **Contain first.** Put the DMS in read-only mode, or shut the servers off if they're compromised. Rotate every secret (below), the DigitalOcean password and 2FA, and the GitHub tokens. Don't restore into an environment the attacker can still reach.
2. Sign in to backblaze.com (owner account, with its 2FA). *B2 Cloud Storage → Buckets → (the offsite bucket) → Browse Files*. Open `production/db/` and the newest date. Download the newest `.dump.age` and its `.counts.json`.
3. Decrypt and restore exactly as in **B** above (`age --decrypt ...`, then `pg_restore` into a new database, then `verify_restore.py`).
4. **Photos and scans.** In B2, *App Keys → Add a New Application Key*: name `mmh-restore`, bucket = the offsite bucket, access **Read Only**. Then, on a computer with the AWS CLI:

   ```bash
   export AWS_ACCESS_KEY_ID=<keyID> AWS_SECRET_ACCESS_KEY=<applicationKey>
   aws s3 sync --endpoint-url https://<the bucket's S3 endpoint> \
     s3://<offsite bucket>/production/media/ ./media/
   # Then upload ./media/ into the (new) media bucket with the Spaces keys:
   aws s3 sync --endpoint-url https://nyc3.digitaloceanspaces.com ./media/ s3://<media bucket>/
   ```

   Delete the `mmh-restore` key in B2 when done.
5. Rebuild the servers from Terraform (rebuild section above), point them at the restored database, deploy, test, then turn read-only mode off.

A file that ransomware encrypted on our side is never copied over the good one: the nightly job only sends files it hasn't sent before, so the first (good) copy is the one in B2.

### The server's logs (log archive)

The app, worker and Caddy containers log to the server's journal, and the `logship` container (Vector) sends the journal, including SSH sign-ins, `sudo` and fail2ban, to the locked B2 bucket every 5 minutes: `<environment>/logs/YYYY/MM/DD/*.ndjson.gz`. They can't be deleted from there, so they show what happened even if someone wiped the server.

- **Reading them:** in B2, *Browse Files → production/logs/<date>/*, download a file, and open it with any tool that reads `.gz` (each line is one log entry). On the server, `docker logs <container>` and `journalctl` still work as usual.
- **"WARNING: the log archive (logship) did not start"** in a deploy log, or the daily Backup check saying logs stopped: on the server, `docker compose -p mmh -f /opt/mmh/current/docker-compose.prod.yml --profile logship logs --tail 50 logship`. If it says the journal is missing, run `sudo mkdir -p /var/log/journal && sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald`, then redeploy. If it's an access error, check the `OFFSITE_*` values in GitHub (*Settings → Environments*).

### Backup or restore test failed

- A **GitHub issue labelled `urgent`** is opened automatically when the monthly restore test fails, or when the **daily backup check** (*Actions → Backup check*) finds the newest backup more than 30 hours old or backups missing. The admin dashboard also shows "Last backup" in red if the nightly backup failed.
- The Backup check also fails if last night's copy didn't reach the **locked B2 bucket**, or **server logs stopped arriving there** for more than 3 hours. Logs stopping can mean someone switched off the record of what they're doing: check the server (*The server's logs* above) before assuming it's a fault.
- **Backups missing (not just late) is treated as a possible attack.** Before anything else: check *DigitalOcean → Settings → Security → Security history* and the GitHub audit log for activity you don't recognise. If anything looks wrong, rotate every secret (below) and the DigitalOcean password, then restore from point-in-time recovery.
- Common causes: an expired `DIGITALOCEAN_TOKEN` or Spaces key, a changed age key, or the backup bucket being unreachable.
- Check the worker log on the server (`docker compose ... logs worker`), then run a backup by hand: `manage.sh run_backup --force`.
- Re-run *Actions → Restore test*. Close the issue once it passes.

### Media copy refused ("files that already had a backup copy changed")

The nightly copy of photos and scans to the second region stops, and copies nothing, when many files that were already backed up have changed at once. Uploads always get new names, so this normally never happens; ransomware encrypting the files would look exactly like this. The backup copies are left as they were.

1. Open a few unit photos in the app. If they don't open or look wrong, treat it as an incident: put the site in read-only mode, rotate the Spaces keys, and restore the files from the backup bucket (its older versions are kept 90 days).
2. If the change was deliberate (for example, files were re-processed on purpose), run the copy once by hand: `manage.sh run_backup --force --media --allow-mass-change`.

### A temporary SSH rule was left open

Each deploy opens SSH to the GitHub runner for a few minutes and closes it again. If closing fails, the run turns red with "Could not remove the temporary SSH rule". In *DigitalOcean → Networking → Firewalls → mmh-production (or staging) → Inbound rules*, delete every SSH (port 22) rule except your office address(es). Running Terraform `apply` for that environment also resets the rules.

### Someone is locked out

- **Too many wrong passwords** (locked for 15 minutes): an admin can clear it at *Admin → Users → ⋯ → Unlock sign-in*.
- **Lost phone (2FA)**: they can use a recovery code. Otherwise an admin clicks *Reset two-factor*: their old authenticator and recovery codes are deleted, they are signed out on every device, and they set 2FA up again at next sign-in. Do this straight away for a **stolen** phone or laptop too.
- **Never reset 2FA because of a phone call, text or email alone.** "I lost my phone, can you reset my code?" is exactly how attackers get in. Reset only after seeing the person, or after hanging up and calling them back on a number we already had (not one they just gave you). The app asks which one you did, and every admin sees the reset on their dashboard for two weeks.
- **The only admin lost their phone and their recovery codes**: SSH in and run `manage.sh reset_2fa their@email`.

### Rotate a secret

1. Create the new value (see [MANUAL_STEPS](MANUAL_STEPS.md) for where each comes from).
2. Update it in GitHub (*Settings → Environments → staging / production*).
3. *Actions → Deploy → Run workflow*. The server's environment file is rewritten on every deploy.
4. Revoke the old value at its source.

Rotating `DJANGO_SECRET_KEY` signs everyone out.

## Where things are

| What | Where |
|---|---|
| App code | `backend/` (Django), `frontend/` (React) |
| Server setup | `infra/cloud-init/droplet.yaml` |
| Deploy scripts | `infra/deploy/` (shipped inside the image) |
| Infrastructure | `infra/terraform/` (`envs/staging`, `envs/production`, `envs/shared`) |
| CI/CD | `.github/workflows/` |
| In-app help articles | `backend/apps/help/articles/` (guide: `docs/HELP_ARTICLES.md`) |
| On the server | `/opt/mmh/.env` (secrets, 0600), `/opt/mmh/state.env` (live version), `/opt/mmh/current` (deploy scripts) |
