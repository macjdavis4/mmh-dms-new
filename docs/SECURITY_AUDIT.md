# Security audit, October 2026

A full review of the DMS against the attack that matters most to a small business: someone gets in, copies customer data, then destroys or encrypts it (and the backups) and demands a ransom.

Five areas were reviewed separately, by reading the code and, where it mattered, by running proof-of-concept attacks against a local copy:

1. Sign-in, sessions and two-factor (2FA)
2. Who can see and change what (every API endpoint, every role)
3. Uploaded files, imports, invoices, PDFs and exports
4. Servers, deploys, GitHub Actions and backups
5. The browser app, shared tablets, and third-party packages

## Bottom line

- **The app itself is in good shape.** No way was found to run code on the server, read files off it, inject SQL, or get past sign-in from the internet. The office-only Cloudflare rule means an outsider can't even reach the sign-in page.
- **One serious app bug was found and fixed:** an old or reset 2FA authenticator could still sign in to the admin back office (details below).
- **The biggest remaining risk is the backups, not the app.** Every copy of the data (database, its backups, photos and their backups) lives in one DigitalOcean account. Keys that sit on the servers and in GitHub can delete all of it. Anyone who steals one of those keys could wipe everything except DigitalOcean's own 7-day database recovery. Code changes in this audit add alarms and a brake, but **the real fix needs your decision (A below)**.

## Fixed in this pull request

| # | Severity | What was wrong | Fix |
|---|---|---|---|
| 1 | **High** | After *Reset two-factor* (lost phone) or setting up a new phone, the old authenticator and old recovery codes still worked on the `/django-admin/` sign-in page. Someone with a stolen phone and the password got full admin access. Proved with a working test. | Old authenticators and recovery codes are now **deleted**, not just switched off. The admin back office refuses any device that isn't active. |
| 2 | Medium | Resetting someone's 2FA didn't sign out a stolen laptop that was already signed in. | *Reset two-factor* now signs the person out on every device. |
| 3 | Medium | The sign-in rate limit (10 tries a minute) could be dodged by adding a made-up `X-Forwarded-For` header to each request. | Rate limits now use the real visitor address that Caddy passes on. |
| 4 | Low | Checking the current password inside the app (change password, turn off 2FA, new recovery codes) had no rate limit. | Same limit as sign-in. |
| 5 | Low | Error reports to Sentry could include typed passwords and 2FA codes. | Request bodies are never sent to Sentry. Browser error reports drop search terms from addresses. |
| 6 | **High** | An imported price that wasn't a clean number (`$38,900 OBO`) was copied into the unit's notes, which every role can read. | Such a price now stops that row with an error and is never copied anywhere. |
| 7 | Medium | A service user could download a salesperson's original import file, including all prices. | Only admin, sales, or the person who uploaded it. |
| 8 | Low | Anyone who could import could run, discard or change someone else's import. | Only an admin or the person who started it. |
| 9 | Low–Medium | Adding `?include_deleted=1` to an address let any role open and **edit** removed records. | Removed records only appear in lists; they must be restored before anything else. |
| 10 | Low | Unit history showed staff IP addresses to every role. | Admins only. |
| 11 | Low | Global search ignored feature switches that were limited to some roles. | Search follows the same switches as the pages. |
| 12 | Low | A salesperson could put another person's name on a quote. | Sales can only use their own name; admins can choose. |
| 13 | Medium | A 12 KB picture file claiming to be 10,000 × 10,000 pixels could use over a gigabyte of memory and stall the server. | Pictures over 60 megapixels are refused before they're opened. |
| 14 | Medium | One crafted PDF invoice with hundreds of pictures could keep the background worker busy for hours, delaying the nightly backups. | At most 30 pictures and 5 minutes of reading per invoice. |
| 15 | Medium | On a shared tablet, the next person to sign in could briefly see the previous person's cached screens, including prices. | Everything cached is cleared at every sign-in. |
| 16 | Medium | The offline copy (up to 600 units with customer names) stayed on the device up to 14 days after sign-out or after access was removed, and opened without signing in. | When online, the offline pages check who is signed in and wipe the copy if nobody is, or someone else is. Losing access wipes it at the next sync. (With no connection at all it still opens, by design; see "Known limits".) |
| 17 | Low | The full app source code was published next to the app (source maps). | No longer published. |
| 18 | Low | Supplier invoices (showing costs) could stay in a tablet's browser cache for an hour. | Never cached. |
| 19 | Low | Paper-backup spreadsheets missed two ways a cell can be turned into a formula. | Same rule as report exports. |
| 20 | Low | The backup could fail if the database password ever contained an apostrophe. | Proper quoting. |
| 21 | Low | Small items: a downloaded file's name could break the download header; sign-in redirect accepted `/\\other-site`; an unused package; a stray decorator. | Fixed. |

### Ransomware safeguards added

| What | Why |
|---|---|
| **Daily backup check from GitHub** (*Actions → Backup check*) | Each morning, from outside our servers, confirms last night's database backup arrived and none have been deleted. If not, it opens an urgent GitHub issue (which emails you). Deleting backups is usually step one of a ransomware attack, so this is the early warning. |
| **Brake on the nightly photo copy** | If many photos that already have a backup copy suddenly change at once (what ransomware encryption looks like), the nightly copy stops and leaves the good copies alone, instead of overwriting them with encrypted ones. |
| **Database owner check on every deploy** | The deploy stops if the app's database user owns any table (an owner could drop tables and switch off the no-delete protection), or if the owner's login is missing. |
| **The web proxy gets only its own 3 settings** | Before, Caddy (the internet-facing part) was handed every secret: database, storage keys, Django key. Now it only gets the site name, email and its certificate token. |
| **GitHub Actions pinned to exact versions** | A hijacked third-party action (this happened to a popular one in 2025) can no longer slip new code into a run that holds our keys. Dependabot keeps the pins current. The Caddy plugins are pinned too. |
| **A failed SSH clean-up fails the deploy** | Each deploy opens SSH to the GitHub runner for a few minutes. If closing it failed, that used to be ignored. Now the run turns red and the runbook says how to close it. |

## Decisions for you

**A. An undeletable backup copy outside DigitalOcean (strongly recommended).** Today a single stolen key can delete the photos, their backups, and every off-site database backup. Options:

1. **Backblaze B2 or AWS S3 with "Object Lock"** (about $1–3 a month at our size). The nightly job adds one more encrypted copy there, with a key that can write but not delete, and the bucket refuses deletion for 30 days, even by us. This is the standard ransomware defence. *Recommended.*
2. **A second DigitalOcean account** (different email, its own 2FA, nobody uses it day to day) that pulls a copy every night with a read-only key. No new vendor, but weaker: that account's password becomes the single point of failure.

**B. Split the keys GitHub holds.** Today the same all-powerful DigitalOcean token and storage key sit in both the `staging` and `production` environments, and staging deploys run with no approval. I would change the workflows so deploys use a token that can only open the firewall for a few minutes, and the all-powerful keys live in a new `infrastructure` environment that always needs your approval. You'd create two new limited keys (about 15 minutes; I'll write the steps). Until then, step 1 in [MANUAL_STEPS](MANUAL_STEPS.md) "Security audit" (approval on staging) covers most of the risk.

**C. Should the `parts` role see what we pay for parts?** CLAUDE.md says cost is for admin and sales only, but the parts screens deliberately show part cost to parts staff (they receive invoices). Either is reasonable. Tell me which and I'll make the code and CLAUDE.md agree.

**D. Remove the Cloudflare DNS token from the servers (optional).** The web server holds a token that can change any DNS record for `maine-material.com` (including email). Switching to a free 15-year Cloudflare origin certificate removes it entirely. Step 3 of the manual steps limits the damage in the meantime.

## Known limits (accepted or for later)

- **Deploy by image fingerprint, a hard-coded image name on the server, and one deploy key per server.** These change the server's start-up script, which means rebuilding the servers. Best done together with decision B.
- **The offline copy opens with no connection and no sign-in.** That's what it's for (field work with no signal). It holds no prices and expires after 14 days. A short PIN for the offline pages is possible if you want it.
- **Recovery codes are stored unencrypted in the database.** Someone who can read the database already has everything else; they are single-use and rate-limited.
- **Sessions last as long as they're used** (12 hours of inactivity ends them). A hard daily limit is easy to add if you'd like one.
- **Anyone in the office can lock an account for 15 minutes** with five wrong passwords. Deliberate: it protects against password guessing.
- **Original photos keep their location data (EXIF).** Thumbnails don't. Removing it would alter the files as uploaded.
- **Paper-backup files (customer phone list) are not encrypted**, so they can be opened when the DMS is down. They are in a private bucket and kept 30 days.
- **Base images (Python, Node, Caddy) are pinned by version, not fingerprint.** Dependabot and the Trivy scan cover them.

## How this was checked

- 16 new automated tests reproduce each fixed attack and prove it now fails, alongside the existing suite. See `backend/tests/test_security_audit.py`, plus new cases in `test_backup.py` and `test_db_privileges.py`.
- Dependency scans: `pip-audit` and `npm audit` found no known vulnerabilities (Django 5.2.17 LTS, Pillow 12.3, pypdf 6.19, React and the rest current).
- The 2FA bypass and the rate-limit bypass were each reproduced against a local copy before being fixed.
