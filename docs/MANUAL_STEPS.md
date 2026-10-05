# Manual steps

Everything here has to be done by a person, in a web browser or on your own computer. Claude can't do these steps: the work happens in accounts only you can sign in to, and the cloud sandbox can't reach DigitalOcean.

Do the sections **in order**. Plan on about **2 to 3 hours** for the first setup, spread over a day (waiting for DNS can take a few hours).

Keep a private note open (a password manager like 1Password or Bitwarden is ideal) and save every key, token and ID as you create it. Each one says **Save as:** with the name to use later.

> ✅ **Checkboxes**: tick each box as you go. If anything looks different from what's described, stop and ask before guessing.

---

## Phase 1: one-time setup

### 1. Accounts you need

- [ ] **DigitalOcean** (servers, database, file storage): https://cloud.digitalocean.com/registrations/new. Use a company email. Turn on two-factor sign-in: *Settings → Security → Two-factor authentication*.
- [ ] **Cloudflare**, free plan (protects the site, manages DNS): https://dash.cloudflare.com/sign-up. Turn on two-factor: *My Profile → Authentication*.
- [ ] **Sentry**, free Developer plan (emails us when the app hits an error): https://sentry.io/signup/
- [ ] **UptimeRobot**, free plan (an independent "is the site up?" check): https://uptimerobot.com/signUp
- [ ] You already have **GitHub** (this repository) and **GoDaddy** (where `maine-material.com` is registered).

### 2. Move DNS for maine-material.com to Cloudflare

The domain stays registered at GoDaddy, and you keep paying GoDaddy for it. Only the *nameservers* change, so Cloudflare answers DNS and can protect the DMS. Your website and **email must keep working**, so go slowly here.

1. [ ] In Cloudflare: **Add a site** → type `maine-material.com` → choose the **Free** plan.
2. [ ] Cloudflare scans your existing DNS records. **Before continuing**, compare its list with GoDaddy's: GoDaddy → *My Products → maine-material.com → DNS*. Take a screenshot of the GoDaddy page for safety.
   - [ ] Every **MX** record (email) is present, with the same priority numbers.
   - [ ] Every **TXT** record (SPF such as `v=spf1 ...`, DKIM, Google/Microsoft verification) is present.
   - [ ] The website records (`@` and `www`) are present.
   - [ ] Add anything missing by hand (*DNS → Records → Add record*).
3. [ ] For the **existing website records** (`@`, `www`) and anything related to email, click the orange cloud so it turns **grey ("DNS only")**. This keeps them exactly as they work today. Only the DMS records (created later by Terraform) will be orange (proxied).
4. [ ] Cloudflare shows two nameservers, like `ada.ns.cloudflare.com` and `bob.ns.cloudflare.com`. Write them down.
5. [ ] In GoDaddy: *My Products → maine-material.com → DNS → Nameservers → Change Nameservers → "I'll use my own nameservers"*. Enter the two Cloudflare nameservers and save.
6. [ ] Wait until Cloudflare emails you that the site is **Active** (usually under an hour, up to 24 hours).
7. [ ] Check that email still works: send a message to yourself from outside (e.g. a Gmail account) and reply to it. Check the website loads.
8. [ ] In Cloudflare, open the site's **Overview** page. In the right-hand column copy the **Zone ID**. **Save as:** `CLOUDFLARE_ZONE_ID`.
9. [ ] *SSL/TLS → Edge Certificates*: turn **Always Use HTTPS** on. (The DMS-specific "Full (strict)" setting is applied by Terraform only to the DMS addresses, so it can't affect your website.)

### 3. Cloudflare API tokens (two of them)

*My Profile → API Tokens → Create Token → Create Custom Token*.

1. [ ] **Token for the web server (certificates)**
   - Name: `mmh-caddy-dns`
   - Permissions: `Zone` · `DNS` · `Edit`
   - Zone Resources: `Include` · `Specific zone` · `maine-material.com`
   - **Save as:** `CADDY_CLOUDFLARE_API_TOKEN`
2. [ ] **Token for Terraform (infrastructure)**
   - Name: `mmh-terraform`
   - Permissions: `Zone` · `DNS` · `Edit`; `Zone` · `Config Rules` · `Edit`; `Zone` · `Cache Rules` · `Edit`; `Zone` · `Zone` · `Read`
   - Zone Resources: `Include` · `Specific zone` · `maine-material.com`
   - **Save as:** `TERRAFORM_CLOUDFLARE_API_TOKEN`

### 4. DigitalOcean tokens and the Terraform state bucket

1. [ ] *API → Tokens → Generate New Token*. Name `mmh-github`, expiration **1 year**, scope **Full Access**. **Save as:** `DIGITALOCEAN_TOKEN`. Put a calendar reminder 11 months out to renew it.
2. [ ] *Spaces Object Storage → Access Keys → Create Access Key*, choose **Full Access**, name `mmh-terraform`. Copy both values: **Save as:** `SPACES_ACCESS_KEY_ID` and `SPACES_SECRET_ACCESS_KEY` (the secret is shown only once).
3. [ ] *Spaces Object Storage → Create Bucket*: region **New York (NYC3)**, name **`mmh-terraform-state`**, **Restrict File Listing** on. This is where Terraform keeps track of what it built.

### 5. Your IP address and SSH keys

1. [ ] From the office network, open https://ifconfig.me. The number shown (e.g. `203.0.113.10`) is the office IP. **Save as:** `ADMIN_SSH_CIDRS` in this exact form: `["203.0.113.10/32"]`. Only this address can open an SSH connection to the servers.
2. [ ] On your computer, open *Terminal* (Mac) or *PowerShell* (Windows) and create two key pairs:

   ```bash
   # Your personal emergency key (press Enter to accept the location; DO set a passphrase)
   ssh-keygen -t ed25519 -C "owner@maine-material.com"

   # The GitHub deploy key (no passphrase; GitHub stores it)
   ssh-keygen -t ed25519 -N "" -C "github-actions-deploy" -f mmh-deploy
   ```

   - [ ] The text inside `~/.ssh/id_ed25519.pub` → **Save as:** `ADMIN_SSH_PUBLIC_KEY`
   - [ ] The text inside `mmh-deploy.pub` → **Save as:** `DEPLOY_SSH_PUBLIC_KEY`
   - [ ] The text inside `mmh-deploy` (no `.pub`, starts with `-----BEGIN OPENSSH PRIVATE KEY-----`) → **Save as:** `DEPLOY_SSH_PRIVATE_KEY`. Then delete the `mmh-deploy` file from your computer.

   The deploy key can **only** run the deploy program on the server. It can't open a shell.

### 6. The backup encryption key (very important)

Nightly backups are encrypted. **Without this key nobody, including us, can read a backup.** The server only has the public half, so a stolen server can't open old backups.

1. [ ] Install `age`. Mac: `brew install age`. Windows: download `age-*-windows-amd64.zip` from https://github.com/FiloSottile/age/releases and unzip it.
2. [ ] Run `age-keygen -o mmh-backup-key.txt`.
3. [ ] It prints `Public key: age1...`. **Save as:** `BACKUP_AGE_RECIPIENT`.
4. [ ] The file `mmh-backup-key.txt` holds the private key (`AGE-SECRET-KEY-1...`). **Save as:** `BACKUP_AGE_IDENTITY` in the password manager, **and** print it and put the paper in the office safe. Then delete the file from your computer.

### 7. Other secrets

1. [ ] **Django secret key**: on any computer with Python, run
   `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`. Do this **twice**: one for staging, one for production. **Save as:** `DJANGO_SECRET_KEY (staging)` and `DJANGO_SECRET_KEY (production)`.
2. [ ] **Sentry**: *Create Project → Django* named `mmh-dms`. Copy the **DSN** (looks like `https://abc123@o123.ingest.us.sentry.io/456`). **Save as:** `SENTRY_DSN`.
3. [ ] **GitHub token so the server can download the app**: GitHub → your photo → *Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)*. Note `mmh-ghcr-read`, expiration 1 year, tick **only** `read:packages`. **Save as:** `GHCR_READ_TOKEN`. Also note your GitHub username: **Save as:** `GHCR_USER`.

### 8. Put everything into GitHub

In this repository: *Settings → Environments → New environment*. Create **four** environments:

| Environment | Settings |
|---|---|
| `staging` | Deployment branches: **Selected branches → `main`** |
| `production` | **Required reviewers: you**. Deployment branches: `main` |
| `restore-test-staging` | Deployment branches: `main` |
| `restore-test-production` | Deployment branches: `main` |

Now open each environment and add the values below. **Secrets** are hidden after saving; **variables** stay visible.

**`staging` and `production`** (same names in both; use the matching Django key for each):

| Type | Name | Value |
|---|---|---|
| Secret | `DIGITALOCEAN_TOKEN` | from step 4 |
| Secret | `SPACES_ACCESS_KEY_ID` | from step 4 |
| Secret | `SPACES_SECRET_ACCESS_KEY` | from step 4 |
| Secret | `TERRAFORM_CLOUDFLARE_API_TOKEN` | from step 3 |
| Secret | `CADDY_CLOUDFLARE_API_TOKEN` | from step 3 |
| Secret | `DJANGO_SECRET_KEY` | from step 7 (different for each!) |
| Secret | `SENTRY_DSN` | from step 7 |
| Secret | `GHCR_READ_TOKEN` | from step 7 |
| Secret | `DEPLOY_SSH_PRIVATE_KEY` | from step 5 |
| Secret | `SSH_KNOWN_HOSTS` | *added in step 10* |
| Variable | `APP_ENV` | `staging` or `production` |
| Variable | `CLOUDFLARE_ZONE_ID` | from step 2 |
| Variable | `ADMIN_SSH_PUBLIC_KEY` | from step 5 |
| Variable | `DEPLOY_SSH_PUBLIC_KEY` | from step 5 |
| Variable | `ADMIN_SSH_CIDRS` | from step 5, like `["203.0.113.10/32"]` |
| Variable | `ALERT_EMAILS` | like `["owner@maine-material.com"]` |
| Variable | `ACME_EMAIL` | an email for certificate notices |
| Variable | `BACKUP_AGE_RECIPIENT` | from step 6 (`age1...`) |
| Variable | `GHCR_USER` | your GitHub username |

The **restore-test** environments are filled in step 11.

### 9. Build the infrastructure (Terraform)

*Actions tab → **Terraform** → Run workflow*. Run these one after another and wait for each to finish (green tick):

1. [ ] environment `staging`, action `plan`. Open the run and read the summary at the bottom: it should say about **20 to add, 0 to change, 0 to destroy**.
2. [ ] environment `staging`, action `apply`. Takes 10 to 15 minutes (the database is the slow part).
3. [ ] environment `production`, action `plan`, then `apply`. You'll be asked to approve, because production is protected.
4. [ ] environment `shared`, action `apply`. This applies the Cloudflare rules for the DMS addresses only.

This creates, for each environment: a VPC, the Droplet (server) with a fixed IP, the firewall, the managed PostgreSQL database with a connection pool, two Spaces buckets (files in New York, backups in San Francisco), the DNS record, uptime checks and alerts.

### 10. Trust the new servers' SSH fingerprints

GitHub needs to know each server's fingerprint so a fake server can't receive the deploy.

1. [ ] DigitalOcean → *Droplets*: note the IP of `mmh-staging-app` and `mmh-production-app` (the *reserved* IPs, shown under *Networking*).
2. [ ] Wait 10 minutes after Terraform finished (the server installs itself), then **from the office** run:

   ```bash
   ssh-keyscan -t ed25519 <staging-ip>
   ssh-keyscan -t ed25519 <production-ip>
   ```

3. [ ] Each prints one line starting with the IP. Put the staging line in the `staging` environment as secret `SSH_KNOWN_HOSTS`, and the production line in `production` as `SSH_KNOWN_HOSTS`.

> If a server is ever rebuilt, its fingerprint changes and deploys stop with "host key verification failed". Repeat this step for that server.

### 11. Set up the monthly restore test

For each environment (staging and production):

1. [ ] DigitalOcean → *Spaces Object Storage → Access Keys → Create Access Key → Limited Access*. Name it `mmh-<env>-restore-test`. Pick bucket `mmh-<env>-backups` with permission **Read**. Copy both values.
2. [ ] GitHub → *Settings → Environments → `restore-test-<env>`* and add:

| Type | Name | Value |
|---|---|---|
| Secret | `RESTORE_SPACES_KEY_ID` | key from step 1 |
| Secret | `RESTORE_SPACES_SECRET` | secret from step 1 |
| Secret | `BACKUP_AGE_IDENTITY` | the `AGE-SECRET-KEY-1...` line from step 6 |
| Variable | `BACKUP_BUCKET` | `mmh-<env>-backups` |
| Variable | `BACKUP_ENDPOINT` | `https://sfo3.digitaloceanspaces.com` |

### 12. First deploy

1. [ ] GitHub → *Settings → Secrets and variables → Actions → Variables → New repository variable*: `DEPLOY_ENABLED` = `true`.
2. [ ] *Actions → **Deploy** → Run workflow* (branch `main`). It builds the app, deploys to **staging**, then waits.
3. [ ] Open https://staging-dms.maine-material.com. You should see the sign-in page.
4. [ ] Back in the workflow run, click **Review deployments → production → Approve**. A minute later https://dms.maine-material.com shows the sign-in page.

From now on every merged pull request deploys to staging automatically and waits for your approval before production.

### 13. Create the first admin account

Repeat for staging and production. From the office:

```bash
ssh mmhadmin@<server-ip>
sudo -u deploy /opt/mmh/current/manage.sh createsuperuser
# Email, first name, last name, password (12+ characters)
exit
```

1. [ ] Sign in at the site. You'll be sent straight to **two-factor setup**: scan the QR code with an authenticator app (Google Authenticator, Microsoft Authenticator or 1Password), type the 6-digit code, and **save the recovery codes** in the password manager.
2. [ ] Add your staff under *Admin → Users*. Give each person the smallest role that fits.

### 14. Second uptime monitor (UptimeRobot)

1. [ ] UptimeRobot → *Add New Monitor*: type **Keyword**, URL `https://dms.maine-material.com/readyz`, keyword `"status": "ok"` (alert when **not** present), interval 5 minutes.
2. [ ] Alert contacts: your email, plus SMS or the mobile app for after-hours alerts.

### 15. Final checks

- [ ] https://dms.maine-material.com/healthz shows `{"status": "ok", ...}`.
- [ ] Sign in as admin, open *Dashboard → System health*: everything green except "Last backup" until the first night passes.
- [ ] The next morning, "Last backup" shows **OK**.
- [ ] *Actions → **Restore test** → Run workflow* (after the first backup exists). Both jobs pass.
- [ ] DigitalOcean → *Monitoring → Uptime* shows both checks green.

---

## Phase 2: customers and forklift units

Nothing new to set up. Customers and units use the same database and Spaces bucket as Phase 1.

- [ ] **Only if you already ran Terraform for Phase 1**: run *Actions → **Terraform** → Run workflow* with `apply` for **staging**, then **production**. It shows "Changes to Outputs" only (two new outputs the deploy uses to run migrations as the database owner). No servers change.
- [ ] After the deploy, sign in and check that *Customers* and *Units* appear in the menu.
- [ ] Optional: add one real unit card by hand (*Units → Add unit*) to try it before the batch import in Phase 3.

---

## Phase 3: batch import of the unit cards

Nothing to set up. When the cards are scanned and typed up:

- [ ] In the DMS go to **Imports → Download template**. Open it in Excel or Google Sheets.
- [ ] Before typing, select the serial number columns (`unit_serial`, `engine_serial`, …) and set them to **Text** (Excel: right-click → Format Cells → Text), so Excel doesn't change them.
- [ ] Type one row per card, exactly as written. Leave anything you can't read blank. Put the scan's file name (e.g. `card-0412.jpg`) in `source_image_filename`.
- [ ] Save as **CSV UTF-8 (Comma delimited)**.
- [ ] **Imports → New import**: choose the CSV and the scans, press **Check file**, read the preview, then **Import**.
- [ ] Afterwards: *Units → Filters → Only units that need review* lists cards that had something unclear.

Tip: try 10 cards first. If anything looks wrong, **Undo this import**, fix the spreadsheet and import again.

Full column list: `docs/IMPORT_FORMAT.md`. The scanning-app API needs a key from **Admin → API keys** (only when that app exists).

## Phase 4: work orders

Nothing to set up. Make sure each mechanic has a user with the **Service** role (*Admin → Users*); only service and admin users can be assigned work or log time.

---

## Ongoing

| When | What |
|---|---|
| Each merged pull request | Approve the production deploy in *Actions* when you're ready. |
| Monthly (automatic) | Restore test runs on the 3rd. A failure opens a GitHub issue labelled `urgent` and emails you. |
| Yearly | Renew `DIGITALOCEAN_TOKEN` and `GHCR_READ_TOKEN` (calendar reminders). |
| Staff changes | Remove leavers under *Admin → Users* the same day. |
| Office IP changes | Update `ADMIN_SSH_CIDRS` in both environments, then run Terraform `apply` for staging and production. |
