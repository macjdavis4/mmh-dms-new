---
title: Import unit cards from a spreadsheet
summary: Load many paper unit cards at once from a CSV, with scans of the cards, and check every row before anything changes.
section: imports
roles: admin, sales, service
flag: batch-import
pages: /imports, /imports/new, /imports/:id
keywords: import, batch import, upload spreadsheet, csv, excel, template, sample file, bulk add units, scan cards, eagle cards, needs review, update existing units, import errors, warnings, columns
order: 10
---
An import adds or updates many units at once from a spreadsheet, one row per paper card. You see every row before anything changes, and you can undo an import later.

## 1. Fill in the template

1. Open **Imports** and press **Download template**. **See a filled-in sample** shows three example cards.
2. Fill in one row per unit card, with values as written on the card. Leave anything you can't read blank.
3. Every row needs a **unit_serial** (or a **stock_number**).
4. To attach a scan of each card, put its file name in **source_image_filename**.
5. In Excel, use **File → Save As → CSV UTF-8 (Comma delimited)**. An Excel workbook (.xlsx) can't be uploaded.

## 2. Upload it

1. Press **New import**.
2. Choose the CSV file.
3. Optionally, choose the scans of the cards (JPEG, PNG, WebP or PDF, up to 25 MB each). Each is attached to the row that names it.
4. Press **Check file**.

Nothing has changed yet. The import's page opens with every row marked:

- **New unit**: it will be added.
- **Update**: the unit is already in the system (same serial) and some values differ.
- **No changes**: the card matches what we have.
- **Can't import**: the row has an error, shown in red with the column.

Warnings are shown in amber. Use the tabs (**Errors**, **Warnings**, **New**, **Updates**) and the search box to go through them.

## 3. Import

1. Under **If a unit is already in the DMS**, choose **Update it with the card's values** or **Leave it alone**.
2. If some rows have errors, fix them in the spreadsheet and upload it again, or tick **Skip the rows with errors and import the rest**.
3. Press **Import**.

Up to 300 rows import straight away. Bigger files run in the background; the page updates by itself and you can leave it.

After importing, press **Units that need review** to check the units that had warnings.

## How rows are matched

- Units are matched by serial. Capitals, spaces and dashes don't matter. If there's no serial, the stock number is used. Importing the same file again changes nothing.
- Customers are matched by name ("Co." is the same as "Company"). If no customer matches, one is added. A name close to an existing customer is flagged so you can check for a duplicate.

## What an import never does

- A blank cell never erases anything.
- An import never changes the owner of a unit that's already in the system. Use [Change owner](help:change-owner) for that.
- A value that can't be read (for example "5 ton" in a number column) isn't thrown away: it's kept in the unit's notes as written, and the unit is marked **Needs review**.
- Prices are only imported when the person who uploads the file is admin or sales.

## Who can do what

Admin, sales and service can see every import. Only an admin, or the person who uploaded it, can import, add scans, undo or discard it.
