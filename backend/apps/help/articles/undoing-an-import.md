---
title: Undo, retry or discard an import
summary: Take back a whole import, finish one that stopped part-way, or throw away one you don't need.
section: imports
roles: admin, sales, service
flag: batch-import
keywords: undo import, reverse import, roll back import, wrong file, import failed, try again, discard import, kept on undo, original csv
order: 20
---
Only an admin, or the person who started the import, can undo, retry or discard it.

## Undo an import

1. Open the import from **Imports**.
2. Press **Undo this import** and confirm.

Units it added are removed, and units it updated go back to how they were. A unit someone edited after the import is left alone and listed under **Kept on undo**. Customers it added are removed only if nothing else uses them.

An import can be undone once. To bring the units back, upload the same file again.

## Try again after a failure

If an import stopped part-way, it shows **Failed**. Rows already imported are kept. Press **Try again** to import the rest, or undo what was imported.

## Discard an import you haven't run

On an import that's still **Ready to import**, press **Discard** and confirm. Nothing was imported from it, and it leaves the list.

## Get the file back

On an imported import, **Original CSV** downloads the file as it was uploaded. Admin, sales and the person who uploaded it can download it, because it can contain prices.
