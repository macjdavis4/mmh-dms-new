---
title: Work orders
summary: Open a job on a unit, assign a mechanic, log labor, and move it from open to completed.
section: service
flag: service
pages: /service, /service/new, /service/:id
keywords: new job, open a job, create work order, repair order, assign mechanic, labor, labour, time, hours worked, complaint cause correction, on hold, waiting for parts, complete job, close job, cancel job, reopen, customer complaint, broken down, not working, problem with a forklift
order: 10
---
A work order is one job on one forklift: a repair, a planned service, an inspection, prep for sale or warranty work. Numbers start at **WO-20001** and count up.

::: roles admin service
## Open a new work order

You can start one from three places:

- **Service** in the menu, then **New work order**.
- **New work order** in the quick actions on the dashboard.
- On a unit's page, in **Service history**, press **New work order**. The unit is filled in for you.

Then:

1. Pick the **Unit**. Type part of the serial, stock number or model and choose it from the list.
2. Fill in **What's wrong (complaint)**. This is required: what the customer reported, or the job to do.
3. Choose the **Type** (Repair, Planned maintenance, Inspection, Prep for sale or Warranty) and **Where** (In the shop, or On site (field)).
4. Choose the **Mechanic**, or leave it as *Not assigned yet*. If you are in service, it starts as you.
5. Add any of the optional fields: **Due**, **Hour meter**, **Customer PO** and **Contact on site** (name and phone).
6. Press **Open work order**.

The customer is taken from the unit's current owner. If we own the unit, it shows as *Our stock*.

> Note: The hour meter you enter is saved on the unit as a dated reading. If it's lower than an earlier reading you'll see a warning; it is still saved. If the meter was replaced, add a note saying so.

> Tip: Notes and the cause can't be entered on the new work order form. Add them on the work order page after it's open.
:::

## Find a work order

The **Service** page lists work orders, newest first.

- The tabs show **Open** (open, in progress and on hold), **Completed**, **Cancelled** or **All**.
- The search box finds a work order by number, unit serial, model, customer name or the complaint text.
- **Mine** shows only the jobs assigned to you.
- Late jobs show **Overdue** in red, and jobs due today show **Due today**.

::: roles admin service
The dashboard tile **Assigned to me** opens the list of your jobs.
:::

You can also type a work order number (for example `WO-20001`, or just `20001`) into the search box at the top of every page.

## Statuses

A work order moves through these statuses:

- **Open**: just created, nobody has started.
- **In progress**: someone is working on it.
- **On hold**: waiting for something, such as a part. The reason shows in a yellow note at the top.
- **Completed**: the work is done.
- **Cancelled**: the job won't be done. It's kept for the record.

::: roles admin service
## Move a job along

The buttons at the top of the work order change with its status:

- **Start work** moves an open job to in progress.
- **Put on hold** asks what it's waiting for (for example "seal kit from Doosan"), so anyone can pick it back up. **Resume** puts it back in progress.
- **Complete** finishes the job. You must fill in the **Correction** (what was done) first.
- **Cancel job** asks you to confirm. The work order and its labor are kept. Return any parts to stock first; a job with parts on it can't be cancelled.
- **Reopen** puts a completed job back in progress, or a cancelled job back to open.

> Warning: Press **Save changes** before you press a status button. Only **Complete** saves your edits first; the other buttons reload the page and your unsaved typing is lost.

## Complaint, cause and correction

Under **The job** there are three boxes:

- **Complaint**: what the customer reported, or the job to do.
- **Cause**: what you found.
- **Correction**: what you did. A work order can't be completed without it.

## Change the details

Under **Details** you can change the mechanic, type, where, due date, hour meter, customer PO, contact on site and notes. When you change anything, a bar appears at the bottom: press **Save changes**, or **Discard** to throw the changes away.

You can't change the unit or the customer of a work order. If it was opened on the wrong unit, cancel it and open a new one.

## Log labor

In the **Labor** section:

1. Pick the **Mechanic** (it starts as you).
2. Check the **Date**. It starts as today; future dates can't be used.
3. Enter the **Hours**, for example `1.5`. Anything from 0.05 to 24 hours.
4. Add **What was done** if you like.
5. Press **Add time**.

## Remove a labor line

Press the bin icon on the line. It goes straight away, and a message appears with **Undo** if you removed the wrong one. Labor lines can't be edited; remove the line and add it again.
:::

::: roles sales parts read_only
## Looking, not changing

You can open, search and print any work order. Only admin and service can open a new one, change its details or labor, or complete it.
:::

::: roles parts
Parts can add and return parts on an open job. See [Parts on a work order](help:parts-on-work-orders).
:::

## Related

- [Parts on a work order](help:parts-on-work-orders)
- [Print a work order](help:printing-work-orders)
- [Planned maintenance](help:maintenance)
