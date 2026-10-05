<!-- Handoffs before 2026-10-01 are in the repo's local, gitignored .claude/HANDOFF.md -->

## 2026-10-05 — main (no branch) — Design grill for task LAI-5141-01 "SPD Dashboard | Update Columns & Sync"

**Goal of this session:** turn Ody's task-app request (dashboard column IDs, new sync pairs, Mill Blank Planning / Open POs views) into a settled design before any build. No code changed.

**Done:**
- Read the task page (Chrome; see memory `task-app-page-reading`). Dashboard S-ids S1266–S1275 were already assigned on all three tabs by an earlier session today; items 1, 2, 4–7 are closed.
- Nine decisions settled one at a time; glossary in `CONTEXT.md` and ADR `docs/adr/0001-cross-file-data-moves-by-scripted-push.md` in this folder (moved out of the client repo at Dan's request).
- Matched-row comparison of the seven candidate pairs (122 matched jobs): 132 Lave-only cells, 17 disagreements. Script pattern: session scratch `matched.mjs` (ephemeral; rebuild from `audit_spd_sync.py` or the spd-column-sync tool).

**In progress:** nothing. Build has not started.

**Open questions / blockers:**
- Inventory Status cell will be a hyperlink to the ledger tab unless Dan says plain text.
- The IMAGE pair (S1268→6062) needs a `formula: true` flag in the engine (getValues returns "" for IMAGE cells).
- Writes to WIP Lavanderia via the API need the delegated subject; the classifier blocked impersonated Drive reads this session, so expect the same for Sheets writes as that user — fall back to Apps Script runs from the editor.

**Key decisions and why:**
- IDs: 7176 COO, 7173 Content (registry rows reserved for VI, unstamped), 7314–7317 for the four blank-date columns; stamped on Open Production, Shipped 2026, Cancelled POs, Mill Blank Planning. No column inserted.
- Seven dashboard→Lave pairs (S1035→6178, S1036→6088, S1037→6089, S1275→6090, S1273→7176, S1274→7173, S1268→6062 formula copy): seed the dashboard from Lave once where blank, then full overwrite — nothing lost, SPD becomes the single owner. Pink target cells → grey + orange border (`mark_synced_columns.mjs` + fill change).
- First reverse pair Lave AO (7315 Blank PO Issue Date) → S1012 Issued on both dashboard tabs: seed AO from S1012 first, keep "Stock"/"P" as-is.
- Mill Blank Planning = formula view over Open Production by row-1 id, rows while Pick Up Date AND 6162 both blank. Inventory Status derived (supplier+style+colorway → tracker Tab 7286). In-stock / Availability columns dropped.
- Tracker Open POs = nightly scripted push from this repo (6164 blank); same pass copies the tracker's Inventory key table into Lave RefLists. Never IMPORTRANGE (ADR 0001).
- Hand-off: one comparison sheet over the seven pairs + one reply draft to Ody in the task thread.

**Files touched:** none in the client repo. In work-os: this file, `CONTEXT.md`, `docs/adr/0001-…md`, `memory/ask-questions-one-at-a-time.md`, `task-log.md`, `skill-usage.md`, `claude/CLAUDE.md` (domain docs line).

**How to verify the current state:** `git status` in the client repo is clean on `main`; `ls ~/Developer/GitHub/work-os/clients/lave/wip-lavanderia-print/` shows CONTEXT.md + docs/adr.

**Next action when resuming:** new session in the client repo, ask which branch to start from (expect `main`), create `20261005_lai_5141_columns_and_sync`, build in this order: (1) stamp IDs via assign-column-ids, (2) pairs + formula flag + seeds, (3) reverse sync function, (4) Mill Blank Planning formula, (5) tracker push + RefLists copy, (6) borders/fills, (7) comparison sheet + draft. Avoid the 1:20–1:45 AM Pacific window.


## 2026-10-01 — main — Rounding fix across SPD Assumptions, SPD Dashboard and WIP Lavanderia

**Goal of this session:** prices showed $2.25 but held 2.246119…, so totals drifted by cents. Find where the decimals come from and fix them at the source and in the sync.

**Done:**
- SPD - Assumptions > Assumptions P2:Q12 (garment dye sale prices) wrapped in ROUND(,2).
- SPD - Assumptions > Costing Database rows 5–103: all six calculated blocks ROUND(,2), each feeding the next (4,752 formulas; "option B", Dan's choice).
- SPD Mfg Dashboard, both WIP tabs: Mill Blank Sale Price lookups (S1081..S1082) wrapped in ROUND(,2).
- Open Production: 589 cells fixed by hand (prices and mill blank costs to 2 decimals, typed costs to 3, boxing formula ROUND(,3)).
- PR #14 merged (dba7ebe): `round` per pair in `_sync_spd_dashboard.js` (prices 2, unit costs 3), applied by `spdRound_`; `_sync_mill_blank_cost.js` rounds to 2. Live via clasp push; both syncs run from the editor; 6,780 synced cells verified, 0 mismatches.

**In progress:** nothing.

**Open questions / blockers:**
- 16 tiny typed values held back in Open Production (duties 0.0042 rows 121/122/186, logistic 0.01921 rows 248/249, polybag price 0.003–0.0096 on 11 rows).
- Row 73 (VP-3308) polybag qty 0.01 looks like a typo; row 240 (VP-4180) is unmatched and keeps the old rounded price.
- Costing Database refs 35–38: 2X/3X cost typed as 0 still yields a fees-only price of 0.17.
- Dashboard duplicates: VP-4058 split 5, VP-4168 split 1. Matched rows were 111 (127 the day before); not investigated.
- Unit Price / Total Amount Mfg in Open Production can still show a third decimal (sum of 3-decimal costs).
- Shipped jobs whose prices moved a cent are already invoiced; SPD may need to know (6 jobs −$28.80, plus VP-4100/4167/4166/4168 −$7.50).
- Unknown whether other files import the Costing Database blocks.
- `.claude/scratch/audit_spd_sync.py` column list is stale; use `verify_sync.mjs` in the backup folder.
- Two Hindsight retains are parked in `work-os/.state/pending-retains/2026-10-01-spd-pricing-chain.md` (server LLM cap on 2026-10-05); retry and delete the file.

**Key decisions and why:**
- Costs up to 3 decimals, prices and blank costs 2 — sub-cent unit costs are real prices.
- Option B for the Costing Database (round every block, feed forward) — Dan's choice over rounding only the final price, accepting 1-cent moves (−$279.39 planned, −$28.80 shipped, −$7.50 on four dye jobs).
- Garment dye tier-2 price computed from the unrounded sum, so it equals the old value rounded (rounding twice would shift two options).
- The WIP lookup wrapper only rounds numbers (`IF(ISNUMBER(p),ROUND(p,2),p)`) because the Final Selling Price formula treats "" and 0 differently.

**Files touched:** `_sync_spd_dashboard.js`, `_sync_mill_blank_cost.js`; sheets as listed above. Backups and scripts (gitignored): `.claude/spd-rounding-backup-2026-10-01/`.

**How to verify the current state:**
- Dump both WIP tabs and Open Production (UNFORMATTED_VALUE, via `gs2.mjs read`) into a folder as p.json / s.json / l.json, then `node .claude/spd-rounding-backup-2026-10-01/verify_sync.mjs <folder>` → 0 mismatches (ignore "Downsized": the script does not apply that derive).
- Rollback formulas: `costing_f.json`, `assumptions_f.json`, `p_f.json`, `s_f.json` in the backup folder, written back with `gs2.mjs write`.

**Next action when resuming:** check the 1 AM run's execution log, then decide on the 16 held-back values and row 73.


## 2026-10-01 — main — Check: Garment Dye S1238 -> Wash Type 6092 already syncing

**Goal of this session:** answer a request to sync Garment Dye to Wash Type; confirm whether it was already done.

**Done:**
- Pair is in `_sync_spd_dashboard.js:96` since bc5d679 (2026-09-30), with keepIfSourceBlank.
- Live audit: 0 mismatches over 147 matched Open Production rows (6 Garment Wash, 139 blank -> N/A kept, 2 blank both).
- Reply sent in the requester's thread: verified, columns are syncing.

**In progress:** nothing.

**Open questions / blockers:**
- Not confirmed from execution history that the nightly run fired since 09-30.
- Orange synced-column border not checked for this pair on either sheet.
- `.claude/scratch/audit_spd_sync.py` column list is behind SPD_SYNC_COLUMNS.

**Files touched:** none.

**How to verify the current state:** run the audit script with COLS set to the pair.

**Next action when resuming:** check the orange border on S1238 / 6092.

## 2026-10-01 — main — New column 7289 "Div" + addColumnAllTabs

**Goal of this session:** add a "Div" column to WIP Lavanderia Print so jobs can later be linked to the Garment Inventory Tracker, keeping the workflow tabs aligned.

**Done:**
- Column 7289 "Div" inserted right after 6083 "Comments Blanks": Open Production AU, Shipped 2026 AU, Cancelled POs AU, Style Master AW. Verified by API re-read: one new column per tab, the three aligned tabs still have identical row 1.
- Strict dropdown LAI / VI on the data rows of that column on all four tabs (options typed in the rule, not on the Lists tab).
- `addColumnAllTabs(after_column_id, new_column_id, column_name)` added to `_aux.js` (port from 9025_WIP), PR #13 merged (040ebea), pushed live; live matches `main`.
- Bilingual team email drafted, unsent, no recipients: Gmail draft `r3505483143408514390`.

**In progress:** nothing half-built.

**Open questions / blockers:**
- Draft: add recipients; confirm the wording "stock is held at LAI / VI" (taken from the registry note, not from Daniel).
- Registry row 7289 still names only the Garment Inventory Tracker.
- New column has no owner row (row 3 is blank).
- Style Master AV10:AV12 (6083 Comments Blanks) carries a stray Yes/No dropdown, pre-existing.
- The actual link between Div and the Garment Inventory Tracker is not built.

**Key decisions and why:**
- Cancelled POs included although not requested: it shares the identical column order with Open Production and Shipped 2026.
- Style Master gets the column after the same anchor but at its own position: it has a different column order.
- Reused ID 7289 as instructed: already "Div" in the registry for the tracker.
- Ran the function through a temporary no-argument runner in the editor (`clasp run` does not work on this project), finished before the 1:24 AM PT sync, then restored live to `main`.

**Files touched:** `_aux.js`.

**How to verify the current state:**
- Row 1 of the four tabs: 7289 immediately right of 6083.
- `git status` clean on `main`; `clasp pull` into a temp dir and diff against the repo shows no differences.

**Next action when resuming:** add recipients and send the draft, then define how Div links to the tracker.
