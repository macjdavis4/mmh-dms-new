---
title: Add or change a unit card
summary: Enter a forklift's full card: components, mast, forks, tires, battery, attachments and notes.
section: units
roles: admin, sales, service
flag: customers-units
pages: /units/new, /units/:id/edit
keywords: new unit, add forklift, add unit, enter unit card, eagle card, edit unit, change spec, serial number, stock number, components, engine, transmission, hydraulic pump, control valve, spools, mast, forks, tires, battery, charger, attachment, side shifter, duplicate serial
order: 30
---
The form has the same sections as the paper Eagle 1-84 card. Type values exactly as written on the card, and leave anything unknown blank.

## Add a unit

1. Open **Units** and press **Add unit**.
2. Under **Unit**, enter the **Make**, **Model**, **Serial number**, **Year**, **Stock number**, **Condition**, **Fuel** and **Capacity (lb)**. You need at least a serial number, a model or a stock number.
3. Under **Card header**, enter the card date, customer as written, mechanic and work order number from the card.
4. Choose **Who owns it?**: **A customer** (then pick the customer) or **Our stock**. Enter the **Hour meter** if you have it; it's saved as a dated reading.
5. Fill in the rest of the card:
   - **Components**: make, model and serial of the engine, alternator, controller, ignition, fuel system, hydraulic pump, control valve (with its spools) and transmission.
   - **Mast, carriage and tilt**.
   - **Forks**: press **Add forks** for each size, written like `1.75 x 4 x 48 STD`, with how many.
   - **Tires**: type, drive size (for example `8.15-15`), steer size and anything else, like rim size.
   - **Battery and charger**.
   - **Attachments**: press **Add attachment** for each one.
   - **Special equipment, field modifications and notes**.
6. Press **Add unit**.

::: roles admin sales
Under **Stock and pricing**, set the **Stock status**, **Cost ($)**, **Asking price ($)** and **Sale price ($)**. Only admin and sales see this section.

> Note: A unit added as **Our stock** shows on the **In stock** tab only once it has a stock status (for example Available or In prep).
:::

::: roles service
> Note: Only admin and sales can set the stock status and prices. When you add a unit for our stock, ask sales to set its status so it shows on the **In stock** tab.
:::

## The same serial twice

Serial numbers are unique. As you type a serial, the form warns you if it's already on another unit (capitals, spaces and dashes don't matter), with a link to that unit. Saving will be refused. This includes removed units: ask an admin to bring the old unit back rather than entering it again.

## Change a unit card

Open the unit and press **Edit unit card**. Change what you need and press **Save unit card**. If you leave with unsaved changes, you're asked first.

The owner and hour meter aren't on this form for an existing unit. To record new hours, use [Add reading](help:hour-meter) on the unit page.

::: roles admin sales
To record a new owner, use [Change owner](help:change-owner) on the unit page.
:::

::: roles service
A change of owner is recorded by admin or sales.
:::

> Tip: Tick **Something on this card needs a second look** under **Data quality** if you're not sure about a value, and say what needs checking.
