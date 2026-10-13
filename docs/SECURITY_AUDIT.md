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
- **The biggest risk was the backups, not the app.** Every copy of the data (database, its backups, photos and their backups) lived in one DigitalOcean account, and keys on the servers and in GitHub could delete all of it. Now there is a **locked copy in Backblaze B2** that nobody can delete for 30 days, the all-powerful keys are only used by Terraform runs you approve, and the server's logs are archived where an intruder can't erase them. These take effect once you complete Parts 2 and 3 of the [manual steps](MANUAL_STEPS.md#security-audit-october-2026).

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
| 22 | Medium | One sign-in could last for ever while in use, and a copied session cookie gets past 2FA (Mandiant M-Trends 2026). | Admins sign in again after 12 hours, everyone else after a week. |
| 23 | Medium | *Reset two-factor* worked straight from a menu, with no check, and nobody else saw it. Phone scams asking for exactly this are now the second most common way in (M-Trends 2026). | The admin must say how they confirmed it was really the person (in person, or a call back on a known number), and every admin sees recent resets on the dashboard. The command-line reset now deletes devices and signs the person out too. |

### Ransomware safeguards added

| What | Why |
|---|---|
| **Daily backup check from GitHub** (*Actions → Backup check*) | Each morning, from outside our servers, confirms last night's database backup arrived and none have been deleted. If not, it opens an urgent GitHub issue (which emails you). Deleting backups is usually step one of a ransomware attack, so this is the early warning. |
| **Brake on the nightly photo copy** | If many photos that already have a backup copy suddenly change at once (what ransomware encryption looks like), the nightly copy stops and leaves the good copies alone, instead of overwriting them with encrypted ones. |
| **Database owner check on every deploy** | The deploy stops if the app's database user owns any table (an owner could drop tables and switch off the no-delete protection), or if the owner's login is missing. |
| **The web proxy gets only its own 3 settings** | Before, Caddy (the internet-facing part) was handed every secret: database, storage keys, Django key. Now it only gets the site name, email and its certificate token. |
| **GitHub Actions pinned to exact versions** | A hijacked third-party action (this happened to a popular one in 2025) can no longer slip new code into a run that holds our keys. Dependabot keeps the pins current. The Caddy plugins are pinned too. |
| **A failed SSH clean-up fails the deploy** | Each deploy opens SSH to the GitHub runner for a few minutes. If closing it failed, that used to be ignored. Now the run turns red and the runbook says how to close it. |
| **Locked off-site copy (Backblaze B2)** | Every night: the encrypted database backup and every new photo and scan go to a B2 bucket with Object Lock (compliance mode, 30 days), outside DigitalOcean. Nobody can delete or change them for 30 days, us included. The server's key can only add files; what was sent is recorded in an append-only table. Files already copied are never overwritten, so encrypted files can't replace good ones. Tested against an S3 server with Object Lock. |
| **Log archive** | The app, Caddy, SSH sign-ins and `sudo` are sent to the same locked bucket every 5 minutes, so an intruder can't erase the record. The daily check alerts if logs stop. |
| **Keys split** | Only the new `terraform` GitHub environment (always needs your approval) holds the full-access DigitalOcean, Spaces and Cloudflare Terraform keys. Deploys use a token that can only change the firewall and a key that can only read the Terraform state. |
| **Daily check covers B2** | The daily Backup check also confirms the B2 copy is current and logs are still arriving. |

## Decisions (made October 13, 2026)

- **A. Locked off-site copy: Backblaze B2.** DigitalOcean Spaces has no Object Lock (its S3 compatibility list doesn't include it, and it's an open feature request), so it couldn't provide an undeletable copy. Built; turn it on with Part 2 of the manual steps.
- **B. Split the GitHub keys: yes.** Built; Part 3 of the manual steps.
- **C. Parts staff see part costs: yes.** CLAUDE.md now says so; unit cost and prices stay admin and sales only.
- **D. Cloudflare origin certificate: later.** Step 3 of Part 1 (limit the token to our servers' addresses) covers it for now.
- **From the Mandiant M-Trends 2026 report:** hard session limits and 2FA-reset safeguards (built, items 22 and 23); the UniFi network updated and locked down (Part 1, step 4); branch protection on `main` (Part 1, step 1: it is **not** on today); server logs off the server (built).

## Known limits (accepted or for later)

- **Deploy by image fingerprint, a hard-coded image name on the server, and one deploy key per server.** These change the server's start-up script, which means rebuilding the servers. Until then staging and production share a deploy key, so keep approval on staging (Part 1, step 1).
- **The offline copy opens with no connection and no sign-in.** That's what it's for (field work with no signal). It holds no prices and expires after 14 days. A short PIN for the offline pages is possible if you want it.
- **Recovery codes are stored unencrypted in the database.** Someone who can read the database already has everything else; they are single-use and rate-limited.
- **Anyone in the office can lock an account for 15 minutes** with five wrong passwords. Deliberate: it protects against password guessing.
- **Original photos keep their location data (EXIF).** Thumbnails don't. Removing it would alter the files as uploaded.
- **Paper-backup files (customer phone list) are not encrypted**, so they can be opened when the DMS is down. They are in a private bucket and kept 30 days.
- **Base images (Python, Node, Caddy, Vector) are pinned by version, not fingerprint.** Dependabot and the Trivy scan cover them.
- **The locked copy protects 30 days.** After that, files stay unless someone with the B2 master password deletes them: keep that password out of everything but the password manager.

## How this was checked

- New automated tests reproduce each fixed attack and prove it now fails, alongside the existing suite: `backend/tests/test_security_audit.py` and `test_offsite.py`, new cases in `test_backup.py` and `test_db_privileges.py`, and a browser test for the 2FA reset. Screenshots of the changed screens are in `docs/screenshots/security-audit/`.
- The off-site copy and the log archive were run against a local S3 server with Object Lock in compliance mode: uploads succeeded, and deleting a locked file was refused.
- Dependency scans: `pip-audit` and `npm audit` found no known vulnerabilities (Django 5.2.17 LTS, Pillow 12.3, pypdf 6.19, React and the rest current).
- The 2FA bypass and the rate-limit bypass were each reproduced against a local copy before being fixed.
