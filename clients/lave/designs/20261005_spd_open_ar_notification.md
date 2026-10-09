# SPD | Automate AR Invoice Statement Notification (LAI-5145-01)

Request from Ody, 2026-10-03, task doc `1AUupBk-ncXZCQ8zM5rcz21dzA3ipGnVPiCceMuVspr8`.
ADO card 360 "SPD - Open AR Tab" (created by Dan 2026-10-05, empty) receives this spec.
Status 2026-10-09: design settled with Dan; card not yet written, waiting on the open points below.

## Design (settled with Dan)

**A. AR Ledger tab fed by 7001M (daily trigger).** The existing `AR Ledger` tab on the SPD Mfg
Dashboard (`1AMN1Ivy-bPPImI7Z_Y5d-0_nWph1In6Aee_88tJfFmA`, gid 2105051379) stays and is filled by a
script in 7001M (`1pg2FXMKCA_WAgqijWhKTfpg0eV9lwR5PBN4iKl81oyk`, repo
`7001_Moda-_Accounts_Receivable_Ledger`). One row per SPD invoice from `Vintage Invoice`
(customer in {SPD Mfg, SPD MANUFACTURING, INC}), keyed by Invoice #: new invoices appended,
existing rows refreshed, nothing deleted. Script-owned columns: PO# (6254), Invoice # as link to the
invoice sheet (2531), Invoice Date (2535), Due Date = Invoice Date + 30 calendar days, Invoice Amount
(2544). Human-owned, never touched: Pay Date, Payment Amount, Notes - LAI, Notes - SPD; Balance keeps
its running formula. Row 1 gets column IDs (tab has titles only).
Reference: `_to_invoice_tab/_update_invoice_data_back_to_9025.js` / `update_invoice_data_back_to_9025`.

**B. Weekly open-AR email (7001M).** Reads the AR Ledger tab, rows with Balance <> 0, table: Invoice #
(link), PO#, Invoice Date, Due Date, Days past due, Amount, total. Recipients from 7001 `List Emails`
row "SPD MANUFACTURING, INC" (invoices@spdmfg.com, debram@spdmfg.com; cc jose@vintageindustries.mx,
Sandra). No email when nothing is open. Reference: `triggers.js` / `send_invoicing_per_week`.

**C. WIP Shipped invoice column.** S1147 (registered "Submitted By", website field) holds 49 typed
invoice numbers. Add one new S-id (next free S1276) with a lookup by PO# into the AR Ledger; verify
against the typed values, clear S1147. Dashboard PO# (S1004) has a leading zero, 7001 PO does not.

**D. Job # fix.** `Vintage Invoice` col 2581 is IMPORTRANGE of the invoice sheet's Invoice!W5, and the
VI template (`1cL4MuY23E0eZdHFMQAyduJP-Zl6VlIn7cGozSGvFw1g`) sets W5 `=W2` (the invoice number).
Make W5 the real VI Job# (dashboard S1005 / 9025 col 7114). `add_blank_invoice_vintage.js:119`.

**E. VI invoice numbering = job # (like LAI `INV-<job>`).** Own card under Epic 244 "7001 Accounting";
card 360 links to it. Conflicts with bundled invoices (22502 covers 11 POs) and the QuickBooks import.

Assignee Jose Chavez (Ody calls him Emanuel), Epic 244, effort 3 days.

## Open with Ody (ask Dan which are already confirmed)

1. Due date 30 days although SPD invoices carry terms N15.
2. Weekly email day and time (proposed Monday 8:00 Tijuana).
3. Numbering of a bundled invoice covering several jobs (for card E).

## Related cards
354 VI invoice naming (Isaac), 355/356 column IDs in 7001 (Jose), 269 QuickBooks export (blocked).
