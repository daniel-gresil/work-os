# Spec: broken-down Vintage invoices for QuickBooks

Date: 2026-10-01. Status: agreed with Dan, not built. Nothing in any sheet or repo was changed to write this.

## Goal

Each Vintage Industries invoice registered in file 7001 reaches QuickBooks as one invoice with one Line per cost (front print, garment dye, packaging, mill blanks, ...) instead of a single sales total. The accountant does all the work in 7001.

## Files and repos

| Name | What it is | ID |
|---|---|---|
| 7001 | Accounts Receivable Ledger. Tabs `Vintage Invoice`, `VI Invoice Line Item`. Repo `Lave-Apparel/7001_Moda-_Accounts_Receivable_Ledger` (Apps Script). **All code changes are here.** | `1pg2FXMKCA_WAgqijWhKTfpg0eV9lwR5PBN4iKl81oyk` |
| WIP Lavandería | WIP Lavanderia & Print. Tabs `Shipped 2026`, `Open Production`. Source of laundry and print prices. Read only. | `1QrWLs4g-7qiz0I7x6-KAymXK0TNZX5hJJdHaCXJwztM` |
| 9025 | WIP Lave Apparel. Tabs `WIP`, `To Invoice`, `Ship`. Source of cut and sew prices. Read only. | `1VnP52UxzIdfnZhoZs2U2otOz7XGRhKajmshfNOb345k` |
| 7002 | QuickBooks Import Sheet. Tab `Invoices` is the Queue; tabs `Items`, `Customers`. Read by the nightly importer in `Lave-Apparel/qb_sync_tool`. **The importer and the Queue contract are not changed.** | `1yUgXI9RMHUhd6dVRQsBMWmOE0nGkI7t16n7dYsff8sw` |

Columns are always found by the column ID in row 1, never by letter or header text.

## Terms

- **Queue**: the `Invoices` tab of 7002. One row per Line, grouped by invoice number.
- **Line**: one Queue row (item, quantity, unit price).
- **Import**: the nightly creation of the invoice in QuickBooks from the Queue. One-way and create-only, so do not call it a sync.
- **Line-item row**: one row of `VI Invoice Line Item`, which is one job on one invoice.
- **Cost column**: a column of `VI Invoice Line Item` that has a QuickBooks item in row 2.
- **Source**: the file a line-item row was priced from, `Lavandería` or `9025`.

## What exists today

| Piece | State |
|---|---|
| Menu "Vintage Industries → 🔗 Add Invoice to Line Item" (`add_invoice_to_line_item`, `vi_line_item/add_line.js`) | Adds the selected `Vintage Invoice` rows to `VI Invoice Line Item`, priced from file 9192 `Active` by style. |
| `exportInvoiceLineItemsTo7002` (`_add_invoices_to_7002/export_invoice.js`) | Not in the menu. Hard-coded cost list. Sends no Qty and no TxnDate. Looks up Queue columns by IDs the Queue no longer has (2581, 2509, 2533). Maps items by header text through 7002 `Items` column B (7626). |
| `VI Invoice Line Item` tab | Headers only (IDs in row 1, group labels in row 2, names in row 3), sewing costs from 9192. No data. |
| Columns 7624 "Import on Line Item" (`Vintage Invoice`) and 7625 "Sync 7002" (`VI Invoice Line Item`) | Exist, empty. |

## Design

### 1. Layout of `VI Invoice Line Item`

This tab is a deliberate exception to the usual "ID row, then header row" layout. It has five header rows; data starts on row 6. Freeze 5 rows.

| Row | Holds | Example | Example |
|---|---|---|---|
| 1 | Column ID, the same ID the column has in its source file | 6128 | 7214 |
| 2 | QuickBooks item, standard | B1-Front1 | Freight Out |
| 3 | QuickBooks item, TB (used when the customer is Lave) | TB Printing | (blank) |
| 4 | Charge type: `Per unit` or `Per job` | Per unit | Per job |
| 5 | Column name | Front print | Freight/Pedimento |

Rows 2 to 4 are the mapping. They are filled by accounting, not by code, and the script reads them on every run. Adding, removing or remapping a cost column must need no code change.

Identity columns (rows 2 to 4 blank):

| ID | Name | Filled from |
|---|---|---|
| 2581 | Invoice | `Vintage Invoice` |
| 2533 | Customer | `Vintage Invoice` |
| 2535 | Date | `Vintage Invoice` |
| 2509 | Due date (terms text) | `Vintage Invoice` |
| new | Source | script: `Lavandería` or `9025` |
| 6249 | Job # | source file: VI Ref# (6059) or Job # (6249) |
| 6250 | Split | source file: Split (7285) or Split# (6250) |
| 2541 | QTY | see section 3 |
| new | Row total | script: sum of the row's cost cells |
| 7625 | Sync 7002 (status) | script |

Cost columns to create, each with the ID it has in its source:

- **From WIP Lavandería**: 6124 Embroidery, 6125 Garment Dye Treatment, 6126 Grinding, 6127 cropping / sewing, 6128 Front print, 6129 Back print, 6130 Neck print, 6168 Transfer, 6131 Sleeve print, 6152 Rhinestones, 6132 Packaging Labor, 6133 Logistic, 6135 Duties, 6134 Set up / Extras, 6153 Dev Fee, the six per-unit packing-supplies columns 6190 Polybag Price, 6189 Box Cost per Unit, 6194 Price Tickets, 6195 Dept Label, 6196 Size Strips, 6197 Barcode Stickers, and 6242 Mill Blank Sale Price Total (`Per job`). Not cost columns: 6191 Polybag Qty, 6008 Polybag Type, 6192 Box price per box, 6193 Box Qty (inputs, not prices), 6198 Pallet Cost (never used) and 6154 TBD #2 (six rows, values up to 12, not per unit); accounting can add either later by inserting a column with its ID in row 1.
- **From 9025**: 7056 M.O., 4220 Cutting, 7209 Sewing, 7210 Transfer Application, 7095 Front Print, 7096 Back Print, 7097 Neck Print, 7099 Packaging, 7211 Garment Dye, 7212 Other Wash, 7102 Extras, 7213 Taxes, 7214 Freight/Pedimento.

The existing 9192 sewing columns (1636, 1590, 1497, ...) and the 9192 lookup are removed. 9192 is no longer used.

### 2. `Vintage Invoice` tab

Add three columns: Job # (6249), Split (6250) and Source. The script fills them in step 1 when the invoice has exactly one job. For an invoice with several jobs they stay blank; the detail is in the line-item rows. A value typed by hand is never overwritten.

Column 7624 becomes the step-1 status, written by the script.

### 3. Step 1: "Add Invoice to Line Item" (change the existing function)

The accountant selects one or more rows in `Vintage Invoice` and runs the menu item. No checkboxes, no timer.

For each selected invoice:

1. **Find the jobs.** Look up the invoice number in WIP Lavandería Invoice Link (6140), on `Shipped 2026` and `Open Production`. If any job is found, the Source is `Lavandería` and 9025 is not read. Otherwise look it up in 9025 Invoice # (7071), on `WIP`, `To Invoice` and `Ship`; Source is `9025`. **Lavandería wins when an invoice is in both.**
2. **One line-item row per job.** A job is a distinct Job # + Split. The same 9025 job can appear on two tabs (seen on invoice 22749); keep one row for it.
3. **Fill the cost cells with dollar amounts**, rounded to cents. For every cost column whose row-1 ID exists in the source tab:
   - `Per unit`: source price × quantity.
   - `Per job`: source amount as it is.
   - A cost column with a QuickBooks item but a blank charge type is an error; fill nothing for that invoice.
4. **Quantity** goes into QTY (2541). Lavandería: Total Shipped (6272) when above zero, else Qty (6067). 9025: Shipped Qty (6373) when above zero, else Total: Order Quantity (4768).
5. **Write Row total**, and write Job #, Split and Source back to `Vintage Invoice` when there is one job.
6. **Status in 7624**: `Added <date>`, or `Job not found` when the invoice is in neither file. In that case add nothing; the accountant runs it again once the invoice number is recorded in the source file.

Running step 1 again on an invoice that already has line-item rows: if none is queued, replace them after a confirmation; if any is queued, refuse.

The accountant can then edit any cost cell. Nothing is written back to WIP Lavandería or 9025.

### 4. Step 2: export to the Queue (fix `exportInvoiceLineItemsTo7002` and add it to the menu)

The accountant selects line-item rows and runs a new item in the "Vintage Industries" menu.

Checks, per invoice. Any failure means no Line of that invoice is written, and the reason goes in 7625 and in a dialog:

1. All line-item rows of the invoice are in the selection. A partial selection is refused.
2. No row of the invoice is already `Queued`.
3. The sum of all cost cells across the invoice's rows equals Invoice Total Amount (2544) on `Vintage Invoice`, to the cent.
4. Every cost cell with a non-zero amount has a QuickBooks item in row 2 that exists in column A of 7002 `Items`.
5. The customer translates through 7002 `Customers` (7001 name in column B, ID 2533, to QuickBooks name in column A, ID 7629).

Lines. Each non-zero cost cell becomes one Queue row, found by column ID:

| Queue column | ID | Value |
|---|---|---|
| InvoiceNo | 7280 | invoice number, plain value. All rows of the invoice share it. |
| Customer | 7281 | translated customer. For Lave, when AR (267) on `Vintage Invoice` is `Factor`, use `Tequila Blues Factored`. |
| TxnDate | 7272 | Invoice Date (2535) |
| DueDate | 7282 | blank. Terms are text such as "N20" and the importer accepts only a date; QuickBooks applies the customer's terms. |
| Item | 7627 | row 3 (TB item) when the QuickBooks customer starts with "Tequila Blues" and row 3 is not blank; otherwise row 2 |
| Description | 7273 | Job #, Split and column name, e.g. `VP-4051-01 Front print` |
| Qty | 7283 | 1 |
| UnitPrice | 7628 | the dollar amount in the cell |

QuickBooks only needs dollar amounts per item, so quantity is always 1.

After a successful export, write `Queued <date>` in 7625 on every row of the invoice and show a summary listing each Line's item and amount, so a TB cell left blank by mistake is visible before the nightly import.

Do not use 7002 `Items` column B (7626) any more. Leave the column in place.

## Rules the developer should not "fix"

- A blank TB cell is not an error. It falls back to the standard item. If accounting later consolidates TB and standard items, they clear row 3 and no code changes.
- The export never multiplies. Amounts are final when they are in the cells.
- An invoice with several jobs is valid: several rows, one invoice number, one QuickBooks invoice.
- Dry behaviour first: both functions validate everything for an invoice before writing anything for it.
- Read source prices as raw cell values (`getValues()`, never `getDisplayValues()`). WIP Lavandería prices carry three decimals (Packaging 0.197, Price Tickets 0.065) and display rounded; invoice 22875 only reconciles to $3,126.60 from the raw values. Per-cell rounding to cents after multiplying can still drift a cent from Unit Price × quantity on odd quantities; when the total check fails by cents, the status message shows the difference and the accountant adjusts one cell.
- Read whole tabs, never a fixed row window. `Shipped 2026` had 1,198 rows on 2026-10-09 and invoice 22875 sat on rows 1095 to 1098. Column letters also move (eight columns were inserted between 2026-10-03 and 2026-10-09), which is why everything is found by row-1 ID.

## Checks to leave behind

Put the logic that turns line-item rows plus header rows into Queue rows in a pure function, and add one test function with asserts covering:

1. One job, three `Per unit` costs, 600 units: three Lines, Qty 1, amounts 270.00, 60.00, 162.00.
2. A `Per job` cost is not multiplied.
3. Customer "Tequila Blues": TB item used where row 3 is filled, standard item where it is blank.
4. Two jobs on one invoice: Lines share the invoice number; total check uses both rows.
5. Total off by one cent: refused.
6. Cost cell with an amount and no item in row 2: refused.

Manual acceptance on real data, read-only against the source files:

- 22872 (Isaac Morris, one job, Lavandería).
- 22875 (Isaac Morris, four job rows, two without VI Ref#).
- 22882 (Lave, 9025 job 10866-A1).
- 22743 (in both files; Lavandería must win, and the total check shows whether that fill matches $1,330.56).
- 22876 (in neither file today; expect `Job not found`).

Then one end-to-end import using the importer's own test procedure (`qb_sync_tool/docs/invoice-import.md`, "Test procedure").

## Not part of the code change

- **Accounting fills rows 2 to 4** for every cost column: standard item, TB item, charge type. WIP Lavandería adds Logistic, Duties, Set up and Dev Fee into its per-unit price, so decide per column whether those are `Per unit` or `Per job`.
- **7002 `Customers` column B** needs the 7001 names for the Tequila Blues customers (today blank), and Philcos Enterprise needs a customer record in QuickBooks. Test invoice 22714 is stuck in the Queue for that reason and should be removed.
- **New column IDs** (Source, Row total) are claimed in the column registry (9085) before the columns are created.
- **TB versus standard items**: Dan asked Craig on 2026-10-01 whether the TB items can be consolidated. The design works with either answer.

## Open points for Dan

1. ~~Job # and Split in 7001 use one pair of columns (IDs 6249 and 6250) holding either file's job number, plus Source. The alternative is two pairs, one per source file.~~ **Decided 2026-10-03: one pair plus Source.** An invoice only comes from one file; two pairs would leave half the columns empty on every row.
2. ~~WIP Lavandería's Unit Price formula (6136) sums a range that includes Polybag Qty (6191). Confirm which packing-supplies columns are real per-unit prices before creating them as cost columns.~~ **Decided 2026-10-09: the six columns listed in section 1.** Found on the way: the Unit Price formula differs by row (Shipped 2026 mostly `SUM(DL:DX)`, which excludes Set up and Dev Fee; Open Production mostly `SUM(DL:EB)+EF+SUM(EG:EL)`, which includes Polybag Qty, so 33 rows carry one dollar too much). The 7001 fill multiplies each column's own price by quantity and is unaffected; mismatches surface in the export's total check.
3. ~~For invoice 22743 the 9025 rows add up to the invoice amount exactly. If the Lavandería fill does not, the "Lavandería wins" rule needs a second look for Lave jobs.~~ **Checked 2026-10-09: the Lavandería fill is $1,330.56 too** (one row, VP-3325, 1,232 units: Front print 0.60, Neck print 0.13, Packaging 0.35). Both files agree, so "Lavandería wins" stands.
4. Some Lavandería job rows on invoices have no Split value, and some have no VI Ref# (two of the four rows on invoice 22875). The row is still added; the Description is then built from what is there.
