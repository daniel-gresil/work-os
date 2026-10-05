# Design: blank T-shirt inventory in ERPNext, with a specialised agent

Date: 2026-10-03. Status: discovery done, model and architecture proposed, nothing built. No sheet or ERPNext record was changed to write this.

## Goal

Replace the "LAI & VI - Garment Inventory Tracker" spreadsheet with ERPNext: vendors (mills), blank items, customers, the printed product with the blank in its BOM, demand from open orders, purchasing to cover the shortfall, receiving, and allocation of stock to specific orders. Then build an agent that runs this process in ERPNext, starting at L1 (drafts, Dan approves).

## Files and repos read

| Name | What it is | ID / path |
|---|---|---|
| Garment Inventory Tracker | "LAI & VI - Garment Inventory Tracker (09-11-26)". The file being replaced. Tabs `Inventory`, `Availabiilty`, `001`..`051` (one ledger per SKU), `Lists`, `Notes`. | `1eFvKttDYmZdJlYouPPeuPAYaFSimKLyQSk_fPsjey7k` |
| SPD Mfg Dashboard | Customer-facing dashboard for SPD Mfg. Tabs `WIP Planned `, `WIP Shipped`, `Garment Inventory` (S1247-S1263, fed daily from the tracker), `Threshold Inventory`, `Stock Out`, `Pricing - Mill Blank`. Repo `Lave-Apparel/spd-dashboard`. | `1AMN1Ivy-bPPImI7Z_Y5d-0_nWph1In6Aee_88tJfFmA` |
| WIP Lavanderia & Print | Vintage Industries production WIP. Tab `Open Production` (ids row 1, data from row 6). Repo `Lave-Apparel/wip-lavanderia-print`. | `1QrWLs4g-7qiz0I7x6-KAymXK0TNZX5hJJdHaCXJwztM` |
| SPD - Assumptions | Tab `Costing Database` (ids row 1, data from row 4): the blank price list. | `11hWeBKGV8cXcUh9QJqQZDmooBUB49pZnsOLlDM5hWOA` |
| lave-erpnext-poc | Custom Frappe app `lave_apparel`; today it holds one empty DocType and no fixtures, so ERPNext is effectively stock v16. Staging `staging-erpnext.laveapparel.com`, production `erpnext.laveapparel.com`, both on the OVH VPS. | `~/Developer/GitHub/lave-erpnext-poc` |

## How the process works today

**SKU** = Supplier + Style# + Colorway, held at a **Div** (location): `VI` (Vintage Industries, the printer) or `LAI` (Lave). 51 SKUs exist (tabs 001-051); 26 have stock.

**Tracker tab per SKU** (`001`..): header rows carry supplier, style, colorway, cost per size tier (XS-XL, 2X, 3X, 4X, 5X, 6X). From row 8 a ledger: Date, Job # (VP-#### = WIP Lavanderia `VI Ref#`, or STOCK), Split, Ref#, Type, then three size blocks XXS..6X: **Received**, **Pulled**, **Allocated**. Types used: Received 87, Pulled 79, Allocated 9 (175 movements, 73 job refs). On-hand per size = sum(Received) - sum(Pulled). `Lists` also defines `Adjust +`, `Adjust -`, `Open PO`, unused so far.

**Inventory tab**: one row per SKU, on-hand per size via INDIRECT into the SKU tab; cost per size tier via IMPORTRANGE from `Costing Database` matched on Style# + Color Group; stock value.

**Availabiilty tab**: on-hand minus Allocated per size. This is the "what can I promise" number.

**Costing Database** (47 rows): Ref#, 1001 Brand Supplier, 1002 Style#, 1055 Style Details, 1003 Color Group, Content, Weight; Supplier Mill Blank Cost per size 1007-1014; Lave margin 1016-1024; logistic 1026-1034; duty 1036-1044; VI selling price 1046-1054. Costs are per Color Group (White / Black / Colors / White PFD / Garment Dye), not per colorway.

**Open Production** (WIP Lavanderia) is the demand: per job row 6063 Customer, 6065 PO, 6059 VI Ref#, 7289 Div, 6115 Mill Blank Brand, 6116 Style #, 7284 Style Details, 6117 Colorway, 6081 Blank Status, 6273 Blank Purchase Order, 6162/6164 Blank received dates, customer PO qty by size 6099-6107/6120-6122 (6108 total), **Mill Blank to Order by Size** 6201-6213 (6214 total), mill blank cost per size 6215-6228 (filled nightly by `_sync_mill_blank_cost.js` from the Costing Database).

**SPD dashboard**: `Garment Inventory` mirrors on-hand (daily Apps Script, SPD Mfg rows only); `Threshold Inventory` holds a target size mix per SKU; `Stock Out` lists SKU+size with the in-house date.

Suppliers seen: Optima, Zuni, Gildan, Lane Seven, M&O, SanMar, American Cotton, Kaiyii Apparel, Port & Company, Made Blanks, American Apparel, Smartex, Independent Trading, Los Angeles Apparel. Customers whose blanks are tracked: SPD Mfg (most), Vintage Industries Inc (own stock), Firestone Walker Brewing Company.

## Proposed ERPNext model (stock features only, no custom code)

| Spreadsheet concept | ERPNext |
|---|---|
| Supplier | **Supplier** (group "Mill") |
| Customer (SPD Mfg, ...) | **Customer** |
| Blank style (Optima 47832) | **Item template**, item group "Mill Blank", attributes `Blank Colorway` × `Blank Size` |
| SKU + size | **Item variant** (one per colorway × size); supplier part no. in the Item Supplier table |
| Div VI / LAI | **Warehouse** `Blanks - VI`, `Blanks - LAI` |
| Costing Database cost per size tier | **Item Price** on the Buying price list per variant (Supplier cost) |
| Received | **Purchase Receipt** against a **Purchase Order** |
| Allocated | **Stock Reservation Entry** against the Sales Order (ERPNext v15+) |
| Pulled | **Stock Entry (Material Issue)** or consumption by the job |
| Adjust +/- | **Stock Reconciliation** |
| Open PO | the PO itself (ordered, not yet received) |
| Printed product sold | **Item** per customer style (SPDN2099M...), **BOM**: 1 blank variant per finished unit, per size |
| Demand check | **Production Plan**: pull open Sales Orders, explode BOMs, net against warehouse stock and open POs, raise **Material Request (Purchase)** for the shortfall |

Open points: whether one finished Item per customer style is right or one per job; whether size tiers in pricing (XS-XL same price) are kept as per-variant prices (simple) or a pricing rule; which ERPNext instance (see below).

## Agent

Purpose: run the above in ERPNext. Expert in ERPNext stock, BOM, buying and selling; starts at **L1**.

Triggers: ERPNext **Webhook** DocType on `Sales Order` submit, `Purchase Receipt` submit, `Stock Entry` submit (event-driven), plus one scheduled daily sweep as a safety net. Not a 24h poller.

Runtime options (from Claude Code docs, 2026-10-03): (a) Claude Code **routine** with an API trigger: ERPNext webhook POSTs to the routine's fire URL; runs in the cloud on the subscription; (b) `claude -p` on the Mac Studio behind a small webhook receiver, auth via `claude setup-token`; (c) GitHub Actions `claude-code-action` with `CLAUDE_CODE_OAUTH_TOKEN`. Agent SDK needs API-key billing, so it is out.

Shape: one repo = the agent. `CLAUDE.md` for identity, rules and autonomy level; `skills/` for each procedure (check demand, draft PO, receive, allocate); a thin ERPNext client (`erp.sh` or a Python module using the REST API with an API key for a dedicated `blank-agent` user); `memory/` for decisions; a run log. Where the repo lives is open: hard rule 1 keeps Claude files out of `Lave-Apparel` repos.

## Access notes

- Google Sheets read access from work-os: OAuth refresh token in 1Password `infra` item `ddyor7povtvi522bbgvgwottie` (added to `.claude/op-secrets.txt` as `SHEETS_*`).
- ERPNext staging: `erpnext-staging-admin` in `lave-agent-vault` returns "Invalid login credentials" (2026-10-03). Do not send HTTP basic auth to `/api`: Frappe reads it as api_key:secret.
- ERPNext production: Dan approved building here on 2026-10-03 ("production is clean"). The `erpnext-prod Administrator` password in 1Password `infra` is rejected by the site (2026-10-03), same as staging. No Mac has an SSH key for the VPS. Dan's Chrome is signed in as Administrator; scripted access needs an API key (User > API Access > Generate Keys), which Dan generates and stores in `lave-agent-vault`.

## Production state on 2026-10-03 (read through the browser session)

- ERPNext 16.35.0 / Frappe 16.35.0; apps `lave_apparel 0.0.1`, `sheets_sync 1.1.0`.
- Company **Lave Apparel Industries** (abbr `LAI`), USD, perpetual inventory on. Stock Settings: item naming by Item Code, FIFO, default warehouse `Stores - LAI`, negative stock off, **stock reservation off** (must be enabled for Allocated).
- Warehouses: stock set only (`Stores`, `Work In Progress`, `Finished Goods`, `Goods In Transit`, all `- LAI`).
- Item Groups: stock set. Item Attributes `Size`, `Colour` exist (stock, empty of our values). Price Lists `Standard Buying` / `Standard Selling`.
- 0 Items. 1 Customer `1981 MFG inc` (created 2026-09-08). 1 Supplier `Amazon` (2026-09-28). Both look like trial entries.
- Users: Administrator, Byron Corona, Daniel Souza, Isaac Valdez, itsupport (Gerardo Garcia), Jose Guadarrama, Rogelio Reyes.
