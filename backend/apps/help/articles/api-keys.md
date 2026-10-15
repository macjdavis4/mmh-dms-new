---
title: API keys
summary: Give the card-scanning app a key to send unit cards to the import, and revoke it if it's lost.
section: admin
roles: admin
flag: batch-import
pages: /admin/api-keys
keywords: api key, scanning app, card scanner, integration, revoke key, import api, token
order: 50
---
API keys are only needed for the card-scanning app or another tool that sends unit cards to the import. Spreadsheet imports don't need one.

## Make a key

1. Open **API keys** under **Admin** in the menu.
2. Press **New key** and give it a **Name** that says where it's used, for example "Card scanner tablet".
3. Press **Create key**, then press the copy button next to the key, paste it into the app's settings, and press **Done**.

The key is shown only once. Imports sent with it are recorded as you.

## Revoke a key

Press **Revoke** and confirm. Anything using it stops working straight away. This can't be undone; make a new key instead.

A key also stops working if the admin who made it is removed or can no longer import.
