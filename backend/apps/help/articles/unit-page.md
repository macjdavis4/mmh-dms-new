---
title: The unit page
summary: Everything about one forklift: photos, the full spec card, hours, prices, owners, service and maintenance.
section: units
flag: customers-units
pages: /units/:id
keywords: unit details, forklift details, spec card, unit card, needs review, mark as reviewed, stock status, available, on hold, in prep, sold, remove unit, delete unit, change history, who changed
order: 20
---
Press any unit to open its page. From top to bottom it shows:

- Its badges (**New** or **Used**, its stock status, and **Needs review** if flagged), make and model, serial and stock number.
- [Photos](help:unit-photos-and-files) and the key facts: hours, capacity, fuel, lift height and owner.
- The full spec card, the same sections as the paper Eagle card: card header, mast and carriage, tires, battery and charger, components, forks and attachments.
- The [scanned original card](help:unit-photos-and-files#scanned-cards-and-documents) and documents.
- [Hour meter readings](help:hour-meter).
- [Ownership history](help:change-owner).
- [Planned maintenance](help:maintenance) and **Service history** (work orders on this unit).
- **Change history**: every edit to the card, who made it and when.

::: roles admin sales
## Prices

**Pricing this time in stock** shows the cost, asking price and sale price. Only admin and sales see prices; they're hidden from everyone else by the server.

The prices are for this time in stock. When a unit we sold comes back to us, it starts with fresh prices, and the old sale keeps its own numbers in the ownership history.
:::

## Stock status

Each unit of ours has a stock status: **Available**, **On hold**, **In prep** or **Sold**. Selling a unit sets it to Sold. A unit coming back to our stock is set to In prep and Used.

::: roles admin sales
Change the stock status on the unit card (**Edit unit card**, then **Stock and pricing**).
:::

## Needs review

A unit marked **Needs review** has something on its card that needs a second look, often from an import. The note at the top says what.

::: roles admin sales service
When it's checked, press **Mark as reviewed**. To flag a unit yourself, edit the unit card and tick **Something on this card needs a second look** under **Data quality**.
:::

::: roles admin
## Remove a unit

Press the bin icon at the top of the unit page and confirm. The unit disappears from inventory and search, but its history stays on record. Press **Undo** on the message straight away if you didn't mean it.

A removed unit's serial still counts as used, so the same serial can't be entered again. A removed unit can't be opened from the app, so Undo is the quickest way back.
:::
