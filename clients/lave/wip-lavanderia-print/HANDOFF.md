<!-- Handoffs before 2026-10-01 are in the repo's local, gitignored .claude/HANDOFF.md -->

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
