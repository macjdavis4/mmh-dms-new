---
title: System health
summary: The admin card on the dashboard: database, background jobs, backups, the off-site copy and recent two-factor changes.
section: admin
roles: admin
keywords: system health, backups, backup status, off-site copy, background jobs, failed jobs, database, two factor resets, version, is the system ok
order: 60
---
Only admins see the **System health** card on the dashboard. It checks again every minute. Each line has a green tick or a red warning:

- **Database** and **Database schema**: the system can reach its database and it's up to date.
- **Background jobs**: jobs waiting, or failed ones in red. Each failure is also written to the [audit log](help:audit-log#failed-background-jobs-and-backups).
- **Last backup**: the nightly database backup.
- **Locked off-site copy**: the copy that can't be changed or deleted. It's green when a file went off-site in the last 30 hours.
- **Paper backup**: the nightly [paper backup](help:paper-backup).

## Two-factor changes

An amber box lists two-factor resets and people turning off their own two-factor sign-in in the last two weeks. If you don't expect one, check with the person straight away.

If something is red and stays red, contact whoever looks after the system. The steps for them are in the runbook.
