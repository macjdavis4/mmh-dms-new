---
title: Record a sale
summary: Turn an accepted quote into a sale: units go to the customer and trade-ins come into our stock, all in one step.
section: sales
roles: admin, sales
flag: sales
keywords: sell a forklift, sell a unit, sell from a quote, sell, sold, close the deal, invoice number, deliver, delivery hours, void sale, undo sale, financing fell through, cancel sale
order: 20
---
Recording the sale does everything at once, or nothing at all:

- Each unit on the quote goes to the customer, at its price on the quote, and becomes **Sold**.
- Each trade-in comes into our stock as **In prep** and **Used**, with the allowance as its cost. A trade-in that was only described on the quote is added as a new unit.
- The sale gets a number from **S-40001** upwards, and the totals are kept as they were on the day.
- The quote becomes **Sold** and is locked.

## Record it

1. Open the quote and press **Record sale**. If you have unsaved changes, they're saved first.
2. The system checks every unit. If something is in the way, for example a unit that isn't in our stock any more or a trade-in serial we already have, it's listed in red and the sale can't be recorded until you fix it.
3. Check the **Sale date** (today to start; it can't be in the future) and enter the **Invoice #** if you have one.
4. Enter the **Hour meter at delivery** for each unit if you know it.
5. Read **What will happen**, then press **Record sale**.

The sale also shows in [Bought and sold](help:bought-and-sold), with the sale number.

::: roles admin
## Void a sale

If a sale falls through (for example, the financing fell through), an admin can void it:

1. Open the sold quote and press **Void sale**.
2. Say **Why**.
3. Press **Void sale**.

Every unit goes back to who had it before, with its stock status and prices. The quote goes back to **Accepted**, so you can change it and sell it again. The voided sale stays on record.

A sale can't be voided if any of its units has changed hands again since. Undo those changes first.
:::

::: roles sales
> Note: Only an admin can void a sale. Ask an admin if a sale needs to be undone.
:::
