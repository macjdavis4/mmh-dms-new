---
title: Site settings: read-only mode and the banner
summary: Pause all changes during maintenance, and show a message at the top of every screen.
section: admin
roles: admin
pages: /admin/settings
keywords: read only mode, pause changes, maintenance mode, banner, announcement, message to everyone, downtime notice, feature flag, turn off feature
order: 20
---
Open **Site settings** under **Admin** in the menu.

## Read-only mode

Turn it on to pause every change, for example during database maintenance. People can still sign in and look things up. Every screen shows "Read-only mode: you can look things up, but changes are paused."

- Turn the switch on and confirm with **Turn on**. Warn people first: anything they haven't saved will be lost.
- Turn it off the same way. Only admins can turn it off.

## Maintenance banner

A message at the top of every screen, including the sign-in page.

1. Type the **Message**, for example "The system will be down for updates Saturday 7–8 AM."
2. Choose the **Style**: Information, Warning or Critical.
3. Press **Save banner**.

Screens pick up the new banner within about a minute. Press **Remove banner** to take it down.

## Switching features off

Large features (for example Sales, Parts invoices, Reports or Help) can be switched off with feature flags. These are in the back office (**/django-admin/**, under **Feature flags**), not on this page. A switched-off feature disappears from the menu, and its help articles are hidden.
