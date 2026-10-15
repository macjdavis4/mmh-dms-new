---
title: Add or change a part
summary: Add a part to the catalog, set its bin and reorder point, other brands' numbers and what replaced it.
section: parts
roles: admin, parts
flag: parts
pages: /parts/new, /parts/:id/edit, /parts/:id
keywords: new part, create part, edit part, change price, list price, our cost, reorder point, order quantity, cross reference, other brand number, replaced by, supersession, remove part, delete part
order: 20
---
Only admin and parts can add, change or remove parts.

## Add a part

1. Open **Parts** and press **Add part**.
2. Enter the **Part number** exactly as printed on the box or in the catalog, and the **Maker** (leave it blank for generic parts).
3. Enter the **Description**, and choose the **Category** and **Sold by the** (each, pair, set, kit and so on).
4. Under **Fits**, list the models it fits, for example `35LN-9A, 30L-9A`. Search uses this.
5. Pick the **Bin**, and set **Reorder at** and **Order this many** (see [Low stock](help:low-stock)).
6. Enter the **List price**, **Our cost**, the **Supplier** and the **Supplier's part #**.
7. Press **Add part**.

> Note: If the same maker and number is already in the catalog, you'll see a warning with a link while you type. One maker can't have the same number twice.

## Other brands' numbers

Under **Other brands' numbers**, press **Add a number** and enter the **Brand** and **Their number**. Search then finds the part by any of them.

## When a newer part replaces this one

Under **Replaced by a newer part**, pick the new part. The old part is then hidden from the parts list, and anyone who opens it is sent on to the current part. A part can't replace itself, and a chain of replacements can't go round in a circle.

## Change a part

Open the part and press **Edit part**. Change what you need and press **Save part**.

## Remove a part

Press the bin icon on the part's page and confirm. To bring it back, press **Undo** on the message straight away.

A part can't be removed while there's stock on hand (count it to zero first), or while another part is marked as replaced by it.
