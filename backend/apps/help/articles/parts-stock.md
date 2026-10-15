---
title: Receive and count stock
summary: Add parts that arrived, count what's on the shelf, read a part's stock history, and put a mistake right.
section: parts
flag: parts-stock
keywords: receive parts, add stock, delivery, count stock, stocktake, inventory count, cycle count, on hand, quantity, adjust stock, stock history, reverse, mistake, wrong count, entered twice, opening count
order: 30
---
Every change to a part's stock is a line in its **Stock history**: opening counts, deliveries, parts used on and returned from work orders, count adjustments and reversals. Lines are never edited or deleted. A mistake is put right with a reversing line, so the history always adds up.

On hand can never go below zero.

::: roles admin parts
## Receive parts by hand

For parts that came with a supplier invoice, use [Parts invoices](help:parts-invoices) instead. It reads the invoice for you and keeps track of backorders. To add parts by hand:

1. Open the part and press **Receive**.
2. Enter **How many arrived**.
3. Check **Our cost each**. It starts at the catalog cost; change it to the invoice price if it's different. This doesn't change the catalog cost.
4. Add the **Invoice or packing slip #**.
5. Press **Add to stock**.

## Count the shelf

1. Open the part and press **Count**.
2. Enter what's actually **On the shelf**. You'll see the difference from the record as you type.
3. Say **Why it's different** if you know, for example "yearly count".
4. Press **Save count**.

The first count of a part is its opening count. Later counts record only the difference.

## Put a mistake right

1. In **Stock history**, press the reverse arrow on the wrong line.
2. Say **Why**, for example "entered twice".
3. Press **Reverse it**.

A matching line is added the other way, and the original stays in the history marked **Reversed**. Reversing a receipt from a supplier invoice puts the quantity back as "to come" on that invoice.

You can't reverse a line that's already reversed, a reversal, or parts used on a work order that's no longer open.
:::

## Read the stock history

The part's page shows every change, newest first: what happened, when, who did it, the change (+ or −) and how many were left after. Lines for work orders link to the work order.

::: roles admin parts sales
Admin, parts and sales also see the cost of each line.
:::

## The nightly stock check

Every night the system adds up every part's history and compares it with the count on hand. Nothing is changed. Any difference is shown at the top of [Low stock](help:low-stock#the-nightly-stock-check) and your admin is alerted.
