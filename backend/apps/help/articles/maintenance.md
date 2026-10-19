---
title: Planned maintenance
summary: Set up 250-hour services and yearly inspections on a unit, see what's due, and turn a due service into a work order.
section: service
flag: service
pages: /service/maintenance
keywords: pm, preventive maintenance, service interval, 250 hour, 500 hour, 1000 hour, annual inspection, due soon, overdue, schedule service, maintenance plan, pause plan
order: 40
---
A maintenance plan says how often a unit needs a service: every so many hours, every so many days, or both. Whichever comes first makes it due.

## See what's due

Open **Maintenance due** in the menu. The page lists:

- **Overdue**: the date has passed, or the hour meter has reached the service hours.
- **Due soon**: due within 30 days or 50 hours. For short intervals the window is smaller, so a monthly check isn't always "due soon".

The most urgent are at the top. Tick **Show plans that aren't due** to see every plan. Paused plans are never listed.

The hours come from the unit's latest hour meter reading. If a unit has no readings, only the date counts, so keep the hours up to date (see [Hour meter readings](help:hour-meter)).

::: roles admin service
## Add a plan to a unit

1. Open the unit and scroll to **Planned maintenance**.
2. Press **Add plan**.
3. Pick a preset (**250-hour service**, **500-hour service**, **1000-hour service** or **Annual safety inspection**), or fill in your own:
   - **Name**, for example "250-hour service".
   - **Every … hours** and/or **Every … days** (365 = once a year).
   - **Last done on** and **Hour meter then**. Leave the hours blank to use the latest reading.
   - **What to do**: the task list. It's copied into the work order when the service is due.
4. Press **Add plan**.

## Turn a due service into a work order

Press **Work order** next to the plan, on the **Maintenance due** page or on the unit page. A planned-maintenance work order opens straight away, with the plan's name and task list as the complaint. Assign a mechanic on the work order.

Each plan has only one open work order at a time. While one is open, the button shows its number instead; press it to go to the job.

## When the job is done

Completing the work order marks the plan done: **Last done on** becomes the completion date and **Hour meter then** becomes the work order's hour meter. Reopening the work order puts the plan back as it was. Cancelling it leaves the plan alone.

## Change, pause or remove a plan

Use the **…** menu on the plan:

- **Edit** changes the interval, the task list or when it was last done. Untick **Active** to pause the plan, for example while the unit is parked. Tick it again to start it again.
- **Remove** takes the plan off straight away. Press **Undo** on the message if you didn't mean it.
:::

::: roles sales parts read_only
## Looking, not changing

You can see every plan and what's due. Only admin and service can add, change or remove plans and make work orders from them.
:::
