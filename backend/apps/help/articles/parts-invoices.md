---
title: Parts invoices and backorders
summary: Upload a supplier's invoice or packing slip, check what the system read, receive the parts into stock, and follow backorders.
section: parts
roles: admin, parts, sales
flag: parts-invoices
pages: /parts/invoices, /parts/invoices/:id
keywords: stuck reading, reading the invoice, taking too long, stop reading, supplier invoice, packing slip, receive invoice, upload invoice, take a photo, scan invoice, ocr, read invoice, backorder, back order, still to come, arrived, won't come, partly received, freight, core charge, type in invoice, cancel invoice, duplicate invoice
order: 60
---
Invoices show our cost, so only admin, parts and sales can see them. Only admin and parts can upload, change and receive them.

::: roles admin parts
## 1. Upload the invoice

Open **Parts invoices** in the menu, then:

- **Upload invoice**: pick a PDF or a photo (up to 25 MB).
- **Take a photo**: on a phone, opens the camera.
- **Type one in**: for a paper invoice with no scan.

The system reads the invoice on our own server; nothing is sent to an outside service. Emailed PDFs are quick. Photos and scans can take up to a minute; the page updates by itself.

If it takes longer than a minute, press **Stop and type the lines in** and enter the lines from the file yourself. After 15 minutes the system stops reading on its own and leaves the invoice for you to type in.

## 2. Check the lines

The system suggests the supplier, invoice number, date, freight, tax, total and every line. Each line is matched to our part by our number, another brand's number or the supplier's number. If the part has been replaced, the line points at the current part.

Lines the reader wasn't sure about are marked **Check**, with the reason. For each line:

- Pick **Our part** if it's missing. If the part isn't in the catalog, [add it](help:adding-and-editing-parts) first.
- Fix the **Shipped**, **Backordered** and **Cost each** if they're wrong.
- Tick **Not a stock item** for freight, core charges and fees.
- Use **Add line** for anything the reader missed, or the bin icon to remove a line.

Under the lines, the totals are checked against the invoice total. Press **Save invoice** when you're done.

> Tip: **Read again** reads the file again from the start and replaces all the lines. Use it only before you've fixed lines by hand.

## 3. Receive into stock

1. Press **Receive into stock**. Save your changes first.
2. Count what's in the box. Each line starts at what was shipped; change it if the box is short.
3. Tick **Update our cost in the catalog to these invoice prices** if you want the catalog to follow the invoice.
4. Press **Receive into stock**.

The parts go into stock with the invoice as the reference. Anything not received yet waits under **Backorders**. The invoice shows **Partly received** until every line is in or closed.

## Backorders

Open the **Backorders** tab to see everything still to come.

- **Arrived**: enter how many came in. They go into stock now.
- **Won't come**: when the supplier cancels a backorder. Say why. Press **Undo** on the message if you didn't mean it.

## Cancel an invoice

Press **Cancel** and say why, for example "entered twice". You can only cancel before anything has been received from it. A cancelled invoice stays on record.
:::

## The same invoice twice

The same supplier invoice number can't be entered twice. If the reader sees a number that's already entered, it warns you and leaves the number blank. Don't receive the same invoice twice.

## The tabs

- **To do**: being read, to check, or partly received.
- **Backorders**: lines still to come.
- **Received**: everything is in.
- **All**: every invoice, including cancelled ones.

Search by supplier, invoice number or part number.

## If the reader can't read it

Reading works best on clear, typed invoices with one line per part. Handwriting and unusual layouts need typing in. Only the first 20 pages of a PDF are read. If nothing could be read, the invoice opens with a note saying why. Type the lines in with **Add line**.
