---
title: Quotes
summary: Write a quote for one or more units with options, delivery, discounts and trade-ins, then print it for the customer.
section: sales
roles: admin, sales
flag: sales
pages: /sales, /sales/new, /sales/:id
keywords: make a quote, write a quote, new quote, estimate, proposal, price a unit, quote a forklift, trade in, trade-in allowance, payoff, discount, delivery charge, sales tax, tax exempt, print quote, quote pdf, expired quote, declined, mark sent, accepted
order: 10
---
Quotes are numbered from **Q-30001** upwards. Only admin and sales can see quotes, because they carry prices.

## Start a quote

- From the **Sales** page, press **New quote**.
- From a unit in our stock, press **Quote this unit**. The unit is added at its asking price.
- From a customer's page, press **New quote**. The customer is filled in.

You become the salesperson on any quote you start.

## Fill it in

**Customer**: pick the customer (required). Add **Attention**, **Customer PO**, **Quote date** and **Valid until** if you need them. Valid until starts 30 days out. After that date a draft or sent quote shows **Expired**. Expired is only a label; you can still sell from it.

**Units and items**:

- **Add a unit from our stock**: type a serial, stock number or model. Only units that are available, on hold or in prep can be added. The price starts at the asking price; change it if you've agreed a different one.
- **Add item**: an attachment or option, delivery, service or warranty, or anything else. Give it a **Description**, **Qty** and **Price**.
- **Add discount**: type the **Amount off** as a positive number; it's taken off.
- Untick **Taxed** on any line that isn't taxed. Delivery starts unticked.

**Trade-ins**: press **Add trade-in**. Pick one of the customer's units we already know under **Their unit**, or describe it (**Make**, **Model**, **Serial**, **Year**). Then enter the **Allowance**, **Hours**, any **Payoff (if owed)** and who it's **Owed to**, and **Condition notes**.

**Terms and notes**: **Terms** are printed on the quote. **Internal notes** are never printed.

Press **Create quote** (or **Save changes**). Nothing is saved until you do, and leaving the page throws unsaved changes away.

## How the total is worked out

1. **Subtotal**: every line, less discounts.
2. Less the **Trade-in allowance**.
3. Plus any **Trade-in payoff** (we pay off what they still owe).
4. Plus **Sales tax**: the tax rate (5.5% to start) on the taxed lines less the trade-in allowance.

For a tax-exempt customer, tick **Tax exempt** and enter the **Exemption certificate #**. It prints on the quote.

## Quote status

- **Draft**: being written.
- **Sent**: press **Mark sent** when it goes to the customer.
- **Accepted**: press **Accepted** when they say yes. Then [record the sale](help:record-a-sale).
- **Declined** or **Cancelled**: kept for the record and locked. Press **Reopen** to make it a draft again.
- **Sold**: the sale has been recorded. The quote is locked.

> Warning: Press **Save changes** before pressing a status button. A status button doesn't save your typing, and the page reloads without it.

## Print the quote

Press **Print**. The quote opens as a PDF with the customer, the items, trade-ins, totals, your terms and a line for the customer to sign. Internal notes and our cost are never printed.

## Find a quote

The **Sales** page has tabs for **Open** (draft, sent and accepted), **Sold**, **Declined** (declined and cancelled) and **All**. Search by quote or sale number, customer, serial, model or customer PO. **Mine** shows only your quotes. You can also type a quote, sale or invoice number into the search box at the top of every page.
