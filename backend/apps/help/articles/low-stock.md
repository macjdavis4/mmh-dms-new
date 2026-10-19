---
title: Low stock
summary: See which parts are at or below their reorder point and how many to order.
section: parts
flag: parts-stock
pages: /parts/low-stock
keywords: reorder, what to order, running low, out of stock, order list, stock check, drift, counts don't add up, check now, what do we need to order, what to buy
order: 50
---
Open **Low stock** in the menu. It lists every part with a reorder point that has that many or fewer on the shelf, sorted by bin so you can walk the shelves.

- **On hand**: how many the system says are on the shelf.
- **Reorder at**: the reorder point set on the part.
- **Order**: the part's **Order this many** setting.
- **Supplier**: who we buy it from.

A part only shows here if it has **Reorder at** set. To set it, edit the part (see [Add or change a part](help:adding-and-editing-parts)).

## The nightly stock check

Every night the system works out each part's count again from its stock history and compares it with the count on hand. The box at the top of this page shows the result:

- **Counts add up**: everything matches.
- **Some counts don't add up**: the parts that differ are listed. Nothing is changed automatically, and your admin has been alerted.

::: roles admin
Press **Check now** to run the check straight away.
:::
