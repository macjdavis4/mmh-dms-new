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
   - Permissions: `Zone` · `DNS` · `Edit`; `Zone` · `Config Rules` · `Edit`; `Zone` · `Cache Rules` · `Edit`; `Zone` · `Zone WAF` · `Edit`; `Zone` · `Zone` · `Read`
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

> Since the October 2026 security audit, the full-access keys (`DIGITALOCEAN_TOKEN`, `SPACES_*`, `TERRAFORM_CLOUDFLARE_API_TOKEN`) live in a separate `terraform` environment and `staging` / `production` hold limited ones. See "Security audit, Part 3" below.

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

## Phase 5: planned maintenance

Nothing to set up. For each customer unit on a service contract, open the unit and **Add plan** (the common ones are one click). Set *Last done on* and *Hour meter then* from the last service sticker or invoice, so the due dates start right.

## Phase 6: printouts

Optional: put your address and phone number on printed work orders and spec sheets.

1. [ ] GitHub → your repository → *Settings → Secrets and variables → Actions → Variables* tab.
2. [ ] For **staging** and **production** (environment variables), add:
   - `COMPANY_ADDRESS`, e.g. `123 Main Street, Bangor, ME 04401` (no apostrophes)
   - `COMPANY_PHONE`, e.g. `207-555-0100`
3. [ ] They take effect on the next deploy. Until then printouts say "Bangor, Maine".

When you have the official "Authorized Hyundai Dealer" badge artwork, send it over; the printouts have a marked slot for it.

---

## Phase 7: units changing hands

Nothing to set up. Two things worth doing once it's deployed:

1. [ ] For units already sold, open each one and click the pencil on the sale in *Ownership history* to add why it changed hands and the invoice #. (Prices typed on the unit card before are kept automatically.)
2. [ ] Tell sales staff: from now on, record a sale or a trade-in with **Change owner** on the unit's page rather than editing the stock status by hand. That keeps each deal's numbers.

---

## Phase 8: quotes and sales

Nothing to set up. Worth checking:

1. [ ] Ask your accountant whether sales tax should be on the price **less the trade-in allowance** (how the app works now) and whether 5.5% is right for everything you sell. Tell me if not and I'll change it.
2. [ ] Read the standard terms printed on quotes (*Sales → New quote → Terms*) and send me your wording if you want different terms by default. Each quote can still be edited.
3. [ ] Optional: if the default tax rate ever changes, set the GitHub variable `SALES_TAX_RATE` (e.g. `5.5`) for staging and production.

---

## Phase 9: parts catalog

Nothing to set up. To get ready for the stock ledger (Phase 10):

1. [ ] Write down your bin codes (aisle-shelf-level, e.g. A-03-2) and add them under *Parts → Bins*.
2. [ ] If you have a parts list in a spreadsheet (part number, description, price, bin), send it to me: a parts import is quicker than typing them in, and I can add one.

## Phase 10: parts stock ledger

Nothing to set up; the nightly stock check runs on its own. To start using it:

1. [ ] For each part, open it and press *Count*, entering what's on the shelf. Do the busiest parts first; parts never counted show as out of stock.
2. [ ] Set a *Reorder at* and *Order this many* on the parts you want to watch (*Edit part*). Those at or below it appear under *Low stock*.
3. [ ] When parts arrive, open the part and press *Receive*.

## Phase 11: parts invoices

Nothing to set up: the reader (Tesseract) is built into the app's server image, and nothing is sent to an outside service. To start using it:

1. [ ] When parts arrive, open *Parts invoices* and press *Upload invoice* (or *Take a photo* on a phone). Lay the paper flat in good light, with the whole page in the picture.
2. [ ] Check the lines against the paper, pick our part where one is missing, then press *Receive into stock* and enter what's actually in the box.
3. [ ] Look at the *Backorders* tab now and then; press *Arrived* when they come, or *Won't come* if the supplier cancels.

## Phase 12: dashboard and reports

Nothing to set up. Each person's dashboard shows the numbers for their job. Reports are under *Reports* in the menu. Use *Download CSV* to open one in Excel.

## Phase 13: continuity

No new bucket or service is needed: the paper backups go into the backup bucket set up in Phase 1, in a `paper/` folder.

1. [ ] When you run the Phase 1 Terraform steps (or if you already have), run `terraform apply` again for staging and production once this is merged. It adds the rule that deletes paper backups after 30 days. Nothing else changes.
2. [ ] Once the system is live, open *Admin > Paper backup*, press *Make one now*, and print `open-work-orders.pdf` once to see what you'd get on a bad day.
3. [ ] On each shop tablet, sign in once while online so it keeps a saved copy. Sign out on shared devices at the end of the day (that wipes the copy).

---

## Network-only access (office and VPN only)

The DMS is reachable **only from the office address** (the VPN comes out there too). Everyone else is blocked by Cloudflare before they reach the server. Only the two health pages, `/readyz` and `/healthz`, stay open so the deploy check and uptime monitors can tell the site is alive. They show only whether the site is up and which version is running.

Do this once, in order:

1. [ ] In Cloudflare, open the `mmh-terraform` token (*My Profile → API Tokens*) and add the permission `Zone` · `Zone WAF` · `Edit` for the `maine-material.com` zone. Without it, the next step fails with a permissions error.
2. [ ] If you created a WAF custom rule by hand (*Security → WAF → Custom rules*) to block outside visitors, **delete it first**. Terraform manages this rule now, and two rules would conflict.
3. [ ] Make sure `ADMIN_SSH_CIDRS` in the `production` environment holds your office address(es), like `["203.0.113.10/32"]`. The rule uses the same list.
4. [ ] *Actions → **Terraform** → Run workflow*: environment `shared`, action `plan`, read the summary (it should add one ruleset), then run `apply`.
5. [ ] Test from outside: open https://dms.maine-material.com on your phone with Wi-Fi **off** (mobile data). You should see a Cloudflare "blocked" page. Then connect to the VPN and try again: you should see the sign-in page. https://dms.maine-material.com/readyz should show a short status from anywhere.

If you lock yourself out, sign in to Cloudflare, go to *Security → WAF → Custom rules*, and turn off **DMS office-only access**. Then fix `ADMIN_SSH_CIDRS` and run `shared` again.

## Security audit (October 2026)

These close the gaps code can't close by itself (see [SECURITY_AUDIT](SECURITY_AUDIT.md)). Three parts:

- **Part 1** (about an hour, no decisions): do it now. Do step 6 **before merging** the security pull request.
- **Part 2** (about 30 minutes): the locked Backblaze B2 copy. It stays off until you do it.
- **Part 3** (about 20 minutes): split the GitHub keys. Do it **right after merging**: Terraform runs wait for it.

### Part 1: quick fixes

1. [ ] **Protect `main` in GitHub.** Today anyone (or anything) with push access can change `main` directly, and every change to `main` deploys.
   - *Repository → Settings → Rules → Rulesets → New ruleset → New branch ruleset*.
   - Name `Protect main`, Enforcement status **Active**. Under *Target branches → Add target → Include default branch*.
   - Tick **Restrict deletions** and **Block force pushes**.
   - Tick **Require a pull request before merging**. Leave *Required approvals* at **0**: pull requests are opened under your own account, and GitHub doesn't let you approve your own.
   - Tick **Require status checks to pass**, then *Add checks* and add all five: `Backend (lint, types, migrations, tests)`, `Frontend (lint, types, unit tests, build)`, `End-to-end (Playwright)`, `Infrastructure (Terraform, shell, secrets)`, `Container images (build + Trivy scan)`.
   - Leave the bypass list empty. *Create*.
   - *Settings → Actions → General → Workflow permissions*: choose **Read repository contents and packages permissions**, and untick **Allow GitHub Actions to create and approve pull requests**. *Save*.
   - *Settings → Environments → staging → Required reviewers*: add yourself. Each merge then waits for one click before it reaches staging (staging and production share a deploy key, so staging needs the same care).
2. [ ] **Keep old versions of the Terraform state.** *DigitalOcean → Spaces → mmh-terraform-state → Settings → Versioning → Enable*.
3. [ ] **Limit the Cloudflare certificate token to our servers.** Cloudflare → *My Profile → API Tokens → mmh-caddy-dns → Edit → Client IP Address Filtering → Is in*: add the reserved IP of staging and of production (DigitalOcean → *Networking → Reserved IPs*). A stolen copy of the token then can't change DNS from anywhere else.
4. [ ] **Update and lock down the UniFi network.** The office network is the only way into the DMS, and Ubiquiti published several critical security fixes this year (bulletins 064, 066 and 067). Menu names vary a little by version.
   - Sign in to the UniFi console (unifi.ui.com or the local address). Update **UniFi OS**, the **Network** application and every device to the newest versions now.
   - Turn on automatic updates for UniFi OS, the applications and devices (*UniFi OS Settings → Updates* or *Control Plane → Updates*).
   - Your **ui.com account**: make sure two-factor sign-in is on (*account.ui.com → Security*). Remove any admin accounts you don't recognise (*Admins & Users*).
   - If you don't manage the network from home, turn off **Remote Management** / remote access. If you do, keep it, but only with two-factor on.
   - *Settings → Security* (or *CyberSecure*): turn on **Intrusion Prevention** if your gateway has it.
   - *Settings → Firewall & Security / Port forwarding*: there should be **no port forwards** unless you know what each one is for. Turn off **UPnP**.
   - The VPN: use the built-in WireGuard or Teleport VPN, one profile per person, and delete profiles for people who leave.
5. [ ] **Turn on alerts for account changes.**
   - DigitalOcean → *Settings → Security*: check that two-factor sign-in is on for every team member, and look through *Security history*. Add a monthly calendar reminder to look again.
   - Cloudflare → *Notifications → Add*: if your plan offers it, add an alert for DNS record changes. Check two-factor sign-in is on for every Cloudflare member.
6. [ ] **Check who owns the database tables** (from the office, takes 5 minutes, **before merging**):

   ```bash
   ssh mmhadmin@<production IP>
   sudo grep ADMIN_DATABASE_URL /opt/mmh/admin.env     # copy the URL after the =
   docker run --rm -it postgres:16-alpine psql "<that URL>"
   ```

   Then type these three lines and send me the output:

   ```sql
   SELECT tablename FROM pg_tables WHERE tableowner = 'mmh_app';
   \du mmh_app
   SELECT has_schema_privilege('mmh_app', 'public', 'CREATE');
   ```

   The first should list no tables, the second should show no attributes, and the third should say `f`. Type `\q` to leave. (The next deploy also checks the first one and stops safely if it's wrong.)

### Part 2: the locked off-site copy (Backblaze B2)

Every night the DMS copies the encrypted database backup and every new photo and scan to Backblaze B2, outside DigitalOcean. The bucket is **locked**: for 30 days nothing in it can be deleted or changed by anyone, you included. The key on our servers can only add files. The server's logs go there too. Expect about $1–3 a month (the first 10 GB are free; then about $6 per TB per month).

1. [ ] **Account.** Sign up at backblaze.com for **B2 Cloud Storage**. Pick the **US East** region when asked. Use an email and password that you use nowhere else and keep in the password manager. Then *My Settings* (or *Account*) → turn on **two-factor verification**. Add a payment card so the account never pauses.
2. [ ] **Bucket.** *B2 Cloud Storage → Buckets → Create a Bucket*:
   - Name: `mmh-offsite-` plus four random digits, like `mmh-offsite-4821` (names are unique worldwide).
   - Files in Bucket: **Private**. Default Encryption: **Enable**. Object Lock: **Enable**.
   - After creating it, on the bucket's card click **Object Lock: Enabled → Default retention**: turn it on, mode **Compliance**, **30 days**. *Update Bucket*.
   - On the bucket's card, note the **Endpoint**, like `s3.us-east-005.backblazeb2.com`. **Save as:** `OFFSITE_ENDPOINT_URL` with `https://` in front: `https://s3.us-east-005.backblazeb2.com`. The bucket name: **Save as:** `OFFSITE_BUCKET`.
   - Leave *Lifecycle Settings* at **Keep all versions**.
3. [ ] **Keys.** *Application Keys → Add a New Application Key*, four times. Each shows its `applicationKey` **once**: copy both values straight into GitHub (step 4).

   | Name | Allow access to bucket | Type of access | File name prefix |
   |---|---|---|---|
   | `mmh-production-writer` | the offsite bucket | **Write Only** | `production/` |
   | `mmh-staging-writer` | the offsite bucket | **Write Only** | `staging/` |
   | `mmh-production-check` | the offsite bucket | **Read Only** | `production/` |
   | `mmh-staging-check` | the offsite bucket | **Read Only** | `staging/` |

   Never put the account's master key anywhere: it stays in your head and the password manager.
4. [ ] **GitHub** (*Settings → Environments*):

   | Environment | Type | Name | Value |
   |---|---|---|---|
   | `production` | Secret | `OFFSITE_ACCESS_KEY_ID` | keyID of `mmh-production-writer` |
   | `production` | Secret | `OFFSITE_SECRET_ACCESS_KEY` | applicationKey of `mmh-production-writer` |
   | `staging` | Secret | `OFFSITE_ACCESS_KEY_ID` | keyID of `mmh-staging-writer` |
   | `staging` | Secret | `OFFSITE_SECRET_ACCESS_KEY` | applicationKey of `mmh-staging-writer` |
   | `restore-test-production` | Secret | `OFFSITE_CHECK_KEY_ID` | keyID of `mmh-production-check` |
   | `restore-test-production` | Secret | `OFFSITE_CHECK_KEY_SECRET` | applicationKey of `mmh-production-check` |
   | `restore-test-staging` | Secret | `OFFSITE_CHECK_KEY_ID` | keyID of `mmh-staging-check` |
   | `restore-test-staging` | Secret | `OFFSITE_CHECK_KEY_SECRET` | applicationKey of `mmh-staging-check` |
   | all four above | Variable | `OFFSITE_BUCKET` | from step 2 |
   | all four above | Variable | `OFFSITE_ENDPOINT_URL` | from step 2, with `https://` |

5. [ ] **Turn it on.** *Actions → Deploy → Run workflow* (or wait for the next merge). The next night's copy sends everything so far; after that, only what's new.
6. [ ] **Check it the next morning.** The admin dashboard's *System health* shows **Locked off-site copy: Last file sent …** in green. In B2, *Browse Files* shows `production/db/`, `production/media/` and `production/logs/`. Then *Actions → Backup check → Run workflow*: it should pass.

### Part 3: split the GitHub keys

Today the all-powerful DigitalOcean token, Spaces key and Cloudflare Terraform token sit in the `staging` and `production` environments, so any deploy run holds keys that can delete the database and every backup. After this, only Terraform runs (which always need your approval) hold them; deploys get keys that can only open the firewall and read the Terraform state.

You'll need the **full-access** values again. GitHub can't show saved secrets, so use the copies in the password manager. If you don't have them, create new ones (step 3 below shows where) and delete the old ones afterwards.

1. [ ] **A Terraform-only environment.** *Settings → Environments → New environment* `terraform`. **Required reviewers**: you. **Deployment branches**: *Selected branches* → `main`. Add these **secrets** (the full-access values): `DIGITALOCEAN_TOKEN`, `SPACES_ACCESS_KEY_ID`, `SPACES_SECRET_ACCESS_KEY`, `TERRAFORM_CLOUDFLARE_API_TOKEN`.
2. [ ] **Repository variables.** *Settings → Secrets and variables → Actions → Variables → New repository variable*. Copy these from the `production` environment (same names, same values): `CLOUDFLARE_ZONE_ID`, `ADMIN_SSH_PUBLIC_KEY`, `DEPLOY_SSH_PUBLIC_KEY`, `ADMIN_SSH_CIDRS`, `ALERT_EMAILS`. If an environment has a `DROPLET_SIZE` variable, add it as `STAGING_DROPLET_SIZE` or `PRODUCTION_DROPLET_SIZE`.
3. [ ] **Check nothing changed.** *Actions → Terraform → Run workflow*: `staging`, `plan`. Approve it. The summary at the bottom must say **No changes**. Repeat for `production` and `shared`. If any plan wants to change something, stop and send me the summary.
4. [ ] **Limited keys for deploys.**
   - DigitalOcean → *API → Tokens → Generate New Token*: name `mmh-deploy`, expiration **1 year**, **Custom Scopes**: tick only **firewall: read** and **firewall: update**. Copy it.
   - DigitalOcean → *Spaces Object Storage → Access Keys → Create Access Key → Limited Access*: name `mmh-deploy-state`, bucket `mmh-terraform-state`, permission **Read**. Copy both values.
5. [ ] **Swap them in.** In **both** `staging` and `production`: replace `DIGITALOCEAN_TOKEN` with the `mmh-deploy` token, and `SPACES_ACCESS_KEY_ID` / `SPACES_SECRET_ACCESS_KEY` with the `mmh-deploy-state` key. **Delete** `TERRAFORM_CLOUDFLARE_API_TOKEN` from both.
6. [ ] **Test.** *Actions → Deploy → Run workflow*. Staging (after your approval) should finish green, including *Remove the temporary SSH rule*. If anything fails, put the old values back and send me the error.

---

## In-app help

Nothing to set up: Help is on for everyone after the deploy.

1. [ ] **Tell the staff.** Help is in the menu (under *You*), and the **?** button at the top of every page opens the help for that page. They can also type what they're trying to do, for example "open a work order", in the search box at the top.
2. [ ] **Make the help check required** (optional, recommended). *Repository → Settings → Rules → Rulesets → Protect main → Require status checks to pass → Add checks*: add `Help articles kept up to date`. A pull request that changes what people see then can't be merged until the help is updated, or its description says `Help: no change needed (reason)`. The check only appears in the list after it has run once, on this pull request.
3. [ ] **If an article is wrong**, tell Claude which one and what's wrong, or open an issue. Articles are fixed with a normal pull request.

## Ongoing

| When | What |
|---|---|
| Each merged pull request | Approve the production deploy in *Actions* when you're ready. |
| Daily (automatic) | Backup check confirms last night's backup arrived and none are missing. A failure opens a GitHub issue labelled `urgent` and emails you: treat it as a possible attack (see RUNBOOK). |
| Monthly (automatic) | Restore test runs on the 3rd. A failure opens a GitHub issue labelled `urgent` and emails you. |
| Yearly | Renew `DIGITALOCEAN_TOKEN` (in `terraform`), the `mmh-deploy` token (in `staging` and `production`) and `GHCR_READ_TOKEN` (calendar reminders). |
| Monthly | Check for UniFi updates if automatic updates are off. Look through DigitalOcean *Security history*. |
| Staff changes | Remove leavers under *Admin → Users* the same day. |
| Office IP changes | Update `ADMIN_SSH_CIDRS` in both environments, then run Terraform `apply` for staging, production **and `shared`**. Until `shared` is applied, the new address is blocked from the DMS. |
