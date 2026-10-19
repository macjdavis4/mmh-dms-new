---
title: Audit log
summary: See who changed what and when, with the values before and after, and every sign-in.
section: admin
roles: admin
pages: /admin/audit
keywords: failed job, job failed, backup failed, background job, audit, history, who changed, who deleted, sign in history, failed sign in, login attempts, before and after, track changes, who removed, who edited, deleted record
order: 30
---
Open **Audit log** under **Admin** in the menu. It records every change and every sign-in: who, what, when, and for changes, each field's old and new value. Entries can't be edited or deleted. Passwords are never shown.

- **Search by record name**, for example a customer or unit.
- Choose an action, such as **Updated**, **Deleted**, **Failed sign-in**, **Account locked**, **Two-factor removed**, **Background job failed** or **Backup failed**.

Red entries (failed sign-ins, lockouts, deletions, two-factor removed, failed background jobs and backups) are worth a look if you didn't expect them.

## Failed background jobs and backups

Within 5 minutes of a background job (such as reading an invoice or the nightly paper backup) or a backup failing for good, it's written here as **Background job failed** or **Backup failed**, with the job's name, how many tries it had and when it failed. The nightly jobs run again the next night. If the same one keeps failing, contact whoever looks after the system.

Each unit's page also shows its own **Change history**.
