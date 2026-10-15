---
title: Change owner (sold, traded in, repossessed)
summary: Record a unit changing hands: sold to a customer, coming back to our stock, or sold between customers.
section: units
flag: customers-units
keywords: change owner, sold, sell a unit, customer bought, trade in, trade-in, repossession, repo, bought back, buy back, lease return, bought used, sold between customers, transfer, ownership history, previous owner, undo sale, correct deal, margin
order: 60
---
A unit stays one record, with one serial, however many times it changes hands. **Ownership history** on the unit page shows every owner, newest first, with why it changed hands, the date, the invoice or reference number and the hours.

> Tip: If the sale is on a quote, use [Record sale](help:record-a-sale) on the quote instead. It changes the owner of every unit and trade-in on the quote in one go.

::: roles admin sales
## Change the owner

1. Open the unit and press **Change owner**.
2. Choose **What happened?**:
   - **Sold to a customer**: it leaves our stock.
   - **Came back to our stock**: a trade-in, repossession, buy-back, lease return or a unit we bought used.
   - **Changed hands between customers**: we weren't part of the deal.
3. Choose **Why**, and check the **Date** (today to start; it can't be in the future).
4. Pick the customer it was **Sold to**, or the **New owner**. The customer must already be under **Customers**.
5. Enter the **Sale price** or **What we paid** (the trade allowance, buy-back price or payoff).
6. Add the **Hour meter**, **Invoice or reference #** and a **Note** if you have them.
7. Read **What will change**, then press **Record sale**, **Take into stock** or **Change owner**.

## What changes

- **Sold**: the stock status becomes **Sold**. The sale keeps its own price, and the unit's cost on the day, so the margin is kept.
- **Came back**: the stock status becomes **In prep** and the condition becomes **Used**. What we paid becomes the unit's cost for this time in stock. The asking and sale price start empty; the last sale keeps its numbers in the history.
- **Between customers**: only the owner changes.

## Correct a recorded deal

Press the pencil on an entry in **Ownership history** to fix the reason, the price, the invoice number or the note. To change who owned it or the date, undo the change and record it again.
:::

::: roles admin
## Undo the latest change

Press the undo arrow on the newest entry and confirm. The previous owner becomes current again, and the stock status, condition and prices go back to what they were, except anything changed by hand since. Only the latest change can be undone, and the undone record stays in the audit log.
:::

::: roles service parts read_only
## Who can change the owner

Only admin and sales can record a change of owner. You can see the ownership history on any unit.
:::
