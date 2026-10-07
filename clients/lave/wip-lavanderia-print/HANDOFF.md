<!-- Handoffs before 2026-10-01 are in the repo's local, gitignored .claude/HANDOFF.md -->

## 2026-10-06 — main (PRs #19–#22 merged) — LAI-5141-01 follow-up: S1039 -> 6073, C6273 link look, and two faults that stopped the nightly sync

**Goal of this session:** Ody's 2026-10-05 update on LAI-5141-01: move the Cust. Due Date sync from the SPD date (S1038) to the VI date (S1039), and make the Blank Purchase Order links in Lavanderia look like links. The manual verification run then showed the sync had not completed since the 2026-10-05 deploy, so that was fixed too.

**Done:**
- `_sync_spd_dashboard.js`: pair `S1039 -> 6073` replaces `S1038 -> 6073`; link cells set `#1155cc` + underline after the rich text write (one `getRangeList` call); Image pair written cell by cell and a pasted picture on the dashboard is never copied (`spdFormula_`); `cells: true` on COO (7176) and Content (7173), each cell write flushed inside a `try`, refused cells in the summary as `cellsNotWritten`.
- `_check_job_split_duplicates.js`: fourth section in the nightly email, Image cells that are not `=IMAGE("https://...")` on the dashboard (S1268) and Open Production (6062); `imgProblem_`.
- Sheets: WIP Shipped row 2 now S1039 = 6073, S1038 blank; orange border on S1039 and off S1038 on both dashboard tabs, off 6072 on Open Production row 3; 76 + 23 link cells in 6273 restyled (Open Production, Shipped 2026). Backup of the marker cells: repo `.claude/scratch/s1039_markers_backup_2026-10-06.json`.
- Fourth manual run of `syncFromSpdDashboard` completed in 4 min 18 s: matched 131, `cellsNotWritten: []`, reverse sync ran (130 dashboard rows matched). Verified by API: 6073 = S1039 on 131/131; 81 link cells blue + underlined; Image, COO, Content with no difference left.
- Record sheet `1GbJmGCHsgsCN71iRzlcvftZBtbcnUhEZ7iyOsVNgwTk` (131 rows: 116 change, 6 filled, 9 same), built before the first run; shared with Ody as editor, no notification.
- Live = `main` at `4b87cbd`, checked by clasp pull + diff (31 files; live has CRLF line endings from another machine).

**In progress:** nothing half-built.

**Open questions / blockers:**
- The comment for Ody is not posted: clean HTML is on the MacBook clipboard and the task page is open at "New Comment". Claude cannot type there (keys do not reach the frame; macOS denies osascript keystrokes). The text is in the session transcript.
- First scheduled runs with this code: sync 1:24 AM PT 2026-10-06, check email 2–3 AM PT (first with the Image section; expect VP-2044 and VP-2045, both on Open Production).
- COO has five hand-typed values outside its dropdown (AV97, AV99, AV141, AV160, AV345) and VP-4248 has `#REF!` in the eleven Mill Blank Order Qty columns on the dashboard, copied into Lavanderia. Both left for Ody.
- 6072 (VI Ship Date) stays hand-typed and now mostly duplicates 6073; Summary WIP and Summary Shipped bucket by 6072.
- Converting a pasted picture to the IMAGE formula automatically: deferred. Needs a one-cell test of `CellImage.getContentUrl()`, a new "external request" scope (trigger owner must re-authorize), a Drive folder and a decision on link-public files.
- `spd_compare.py` compares dates as formatted text and reads 1Password directly; tonight's wrapper (scratchpad, not kept) patched both. Fold it into the tool.
- The email subject of the nightly check still starts with "VI Ref# + Split:" even when only Image cells are listed.
- Yesterday's worktree `20261005_lai_5141_columns_and_sync` and four old branches are still on GitHub (0917 dashboard columns, 1005 drop shipped old, 1005 import papeletas, 1005 lai 5141).
- Resolved from 2026-10-05: live `_push_tracker_open_pos.js` no longer differs from `main`.

**Key decisions and why:**
- Direction dashboard -> Lavanderia for S1039 — the target row has always meant that, and Ody edited it on the dashboard.
- Summary tabs left on 6072 — switching to 6073 would move 189 of 1,096 shipped rows to another month.
- Cell-by-cell only for the Image, COO and Content pairs, not all 73 — see ADR 0002.
- Link look set at cell level after the write, not inside the rich text value — works whatever style the write stamps.
- Check added to the existing nightly email, no new trigger — same recipients (Lists!S3), same schedule.

**Files touched:** client repo `_sync_spd_dashboard.js`, `_check_job_split_duplicates.js` (merged). work-os: this file, `CONTEXT.md` (Pasted image, Cell-by-cell pair), `docs/adr/0002-…`, `claude/skills/spd-column-sync/SKILL.md`, `task-log.md`, `skill-usage.md`, `clients/lave/email-style.md`. Project memory: `grilling-one-question-at-a-time.md`, `merge-needs-per-pr-go-ahead.md`, updates to `lavanderia-writes-via-assign-tool-oauth.md` and `task-app-page-reading.md`.

**How to verify the current state:**
- `git log origin/main -1` = 4b87cbd; `git archive origin/main` to a temp dir + `clasp pull` to another, `diff -rq --strip-trailing-cr` -> no differences.
- Editor: `test_spdKey` and `test_dupCheck` print OK. Executions page: `syncFromSpdDashboard` ends with "Execution completed" and `cellsNotWritten: []`.
- Sheets API: Open Production 6073 equals dashboard S1039 on every matched job; 6273 link cells have underline + `#1155cc`.

**Next action when resuming:** check the Executions page for the 1:24 AM PT run and the 2–3 AM check email, then confirm the comment reached Ody.

## 2026-10-05 — main — WIP Lavanderia "not enough memory": CF consolidation + archive of old shipped tabs (Ody's request)

**Goal of this session:** fix Ody's "there isn't enough memory to add any columns" error in WIP Lavanderia & Print, archive the old shipped orders to another file, and prepare the unneeded-tab clean-up.

**Done:**
- Root cause: not cell count (2.27M of 10M) but 38,412 conditional-format rules (18 distinct per tab) duplicated by every row move to Shipped/Cancelled. Consolidated to 155 rules, same colours, verified per cell with live values (no cell lost a format; 14k gap fills; 510 "Not Received" cells now consistently red). Scripts: repo `.claude/scratch/cf_plan.mjs`, `cf_apply.mjs`, `cf_check.mjs`; rollback = `.claude/scratch/cf_rules_backup.json`.
- Archive: Dan made a full copy, "WIP Lavanderia & Print - ARCHIVE 2026-10-05 (Shipped 2022-2025)" (1LnBK7IcNe--nosk4MTcYPj8MHO7WOMK2Dqrcocu8pys), verified tab by tab (`verify_copy.mjs`), shared with the 41 live-file principals without notifications (`share_archive.mjs`). Shipped 2022 / 2023 / Old deleted from the live file by Dan. File: 29→26 tabs, 2.27M→1.51M cells, 125k→53k formulas, INDIRECT 1,705→100.
- PR #15 merged + live: `AddJobsFrom9025/getData.js:77` no longer reads Shipped Old. PR #16 (import of live-only "papeletas" edits) closed unmerged by decision; live reset to main by clasp push from a clean export.
- ADO 361 created (Epic 351): move file ownership from it@vintageindustries.mx to a Lave Shared Drive, keep file ID; do after this clean-up.
- Gmail draft in Ody's thread (r-286994764605565721), pending in `work-os/.state/pending-drafts/`.
- Guardrails skill template `claspignore` now ends with `.claude/**`.

**In progress:** nothing half-built.

**Open questions / blockers:**
- Ody to confirm the error is gone and which tabs can go: Copy of WIP-Samples, TemplateNewOrder, Dashboard Template, Muestras lavados, Actualize, Floor TV- Printing, Floor TV- Laundry, WA Alerts Config, WA Alerts Log, PACKING, Cuadros Printing, Invoice Pending, REPORT (Mill Blank Planning is new and stays).
- Regrowth: row moves still carry per-row CF rules; either paste values+format without rules, or a nightly re-consolidation. Decide after Ody's test.
- This repo's `.claspignore` still re-includes `**/*.js`, so `clasp push` from the checkout uploads `.claude/worktrees/**` (happened today, fixed by a second push). PR needed: add `.claude/**` at the end.
- Live `_push_tracker_open_pos.js` differs from origin/main (pushed by the LAI-5141 session after its merge); drift check will flag it.
- Drift check did not alert on the live-only papeletas edits; check why.
- Hindsight retains for this session are pending: the server's LLM backend (ClinePass) hit its weekly cap on 2026-10-05, resets ~2026-10-06 21:00 UTC. Run `bash .state/pending-retains/2026-10-05-lavanderia-memory.sh` in work-os and delete the file once all three print RETAINED.
- Two redundant archive files to trash: 13BjP2E4FVuM5c-BJrqEHSnDmfE_xSCkHr9Z--U8HVJE and 1N-P_J55KCDal2Wff-N8Vp7C8z4n-FMKo5ilfbEhNvnc.
- Live file is shared "anyone with the link: viewer" and has four gmail.com editors; mirrored onto the archive as asked.

**Key decisions and why:**
- Consolidate CF before archiving — biggest win, non-destructive, reversible.
- "Not Received" rules pinned above "Received" — the file was inconsistent; red is the evident intent.
- Full-file copy as the archive, not tab copies — keeps cross-tab formulas and images; doubles as rollback.
- Live-only editor edits not adopted — Dan's rule; drift action resets live to main.
- Cancelled POs needed wip-sync-tool added to its whole-sheet protection before the API could write.

**Files touched:** `AddJobsFrom9025/getData.js` (merged). Scratch scripts under the repo's gitignored `.claude/scratch/`.

**How to verify the current state:**
- `source ~/.cache/claude-secrets/wip-lavanderia-print/env.sh && GOOGLE_SA_KEY_PATH="$GCP_WIP_SYNC_SA" node .claude/scratch/inventory.mjs 1QrWLs4g-7qiz0I7x6-KAymXK0TNZX5hJJdHaCXJwztM` → 26 tabs, ~1.5M cells.
- `... node .claude/scratch/cf_check.mjs "Shipped 2026"` → 18 rules, matches plan.
- Live vs main: `git archive main` to a temp dir + `clasp pull` to another, diff; expect only `_push_tracker_open_pos.js` until the LAI-5141 session reconciles it.

**Next action when resuming:** read Ody's reply (compare the sent email with the pending draft), then delete the confirmed tabs and open the `.claspignore` PR.


## 2026-10-05 — 20261005_lai_5141_columns_and_sync (merged, PR #17) — Build of LAI-5141-01 "SPD Dashboard | Update Columns & Sync"

**Goal of this session:** build the design settled in the morning session, one step at a time with a dry run before every sheet write, and leave it live: IDs, seven new pairs, the first reverse pair, the Mill Blank Planning view, the Tracker push, the synced-column markers, and the hand-off to Ody.

**Done:**
- IDs: 7314–7317 claimed (Administrative, WIP Lavanderia Print link), 7173/7176 completed in the registry; stamped on Open Production / Shipped 2026 / Cancelled POs (AN–AQ, AV, AW), Mill Blank Planning (I–L, O, P, Q=7286) and the Tracker's Open POs (G–J, M=7286). Shipped/Cancelled AP/AQ headers fixed to match Open Production.
- `_sync_spd_dashboard.js`: seven pairs appended (S1035→6178, S1036→6088, S1037→6089, S1275→6090, S1273→7176, S1274→7173, S1268→6062 with `formula: true`); `spdFormula_` (literal-URL IMAGE allow-list) and `spdSafe_` (no "=" text across files); `SPD_REVERSE_COLUMNS` + `syncToSpdDashboard` (7315→S1012, keepIfSourceBlank) called at the end of the nightly sync; self-check extended.
- `_push_tracker_open_pos.js` (new): `pushToGarmentInventoryTracker` + `installTrackerPushTrigger` (2 AM PT) + `test_trackerPush`. Ran once by hand: 51 key rows, 381 Open POs rows, 37 with status.
- Seeds: dashboard from Lavanderia 219 cells + 2 target-row ids; Lavanderia AO from S1012 122 cells (d-mmm format); RefLists!H1:N53 key table.
- Mill Blank Planning: sample row cleared, array formula in A4 (388 rows), I:N d-mmm-yyyy; formula text in `docs/mill-blank-planning-formula.md` (this folder). Stray space cleared in Open Production AS111.
- Markers: orange border on 74 synced columns per tab (dashboard row 2, Open Production row 3); seven pink target cells → grey on WIP Planned.
- Record sheet `13PYbQYl4myAocP9YKWhEep8I3CDcMivyLPKFt53iLV4` (six tabs, Image skipped) and standalone Gmail draft `r5376522016129455455` to Ody.
- Deployed: PR #17 merged (4cb7dee), live pushed from a git-archive export of main, verified by clasp pull diff (25 files).

**In progress:** nothing.

**Open questions / blockers:**
- The first live run of the new pairs and the reverse pass is the 1:24 AM PT trigger on 2026-10-06; the manual run from the editor was denied by the auto-mode classifier. Check the execution log for `syncFromSpdDashboard` and `syncToSpdDashboard` summaries.
- Tracker Open POs date cells beyond the old sample row show m/d/yyyy; one manual format pass on H:L fixes it (the push keeps formats).
- Four Tracker keys on two ledger tabs (018/025, 019/026, 035/038, 011/050): first wins until Ody merges them. 66 Open POs keys unknown to the Tracker; 278 Open Production rows without mill blank identity.
- Ody's draft has no CC and is standalone (no task-app thread found by email); send or paste into the task app.
- Earlier-session items untouched: 16 held-back tiny values, row 73 polybag qty, Costing Database refs 35–38.

**Key decisions and why:**
- Reverse pair keeps the dashboard value when Lavanderia is blank — SPD types "Stock"/"P" on new jobs before VI dates the PO.
- Reverse pass chained after the forward sync, not a second trigger — no editor step, deterministic order.
- Tracker push is its own trigger at 2 AM — different file and concern; the editor step was needed anyway for the first run.
- Only literal-URL IMAGE formulas cross files; "=" text never does — the dashboard is customer-edited (three security-review findings).
- Inventory Status is a hyperlink to the ledger tab (handoff default, confirmed).
- RefLists key table seeded by API in step 6 so column Q was not blank while waiting for deploy (Dan flagged the gap).

**Files touched:** client repo `_sync_spd_dashboard.js`, `_push_tracker_open_pos.js` (merged). work-os: this file, `CONTEXT.md` (Inventory Status, Key table), `docs/mill-blank-planning-formula.md`, `task-log.md`, `skill-usage.md`. Project memory: `lavanderia-writes-via-assign-tool-oauth.md`, `no-visible-gaps-between-steps.md`, `MEMORY.md`.

**How to verify the current state:**
- `git status` clean on the branch; `git log origin/main -1` = 4cb7dee. `clasp pull` into a temp dir from a `git archive origin/main` export + `.clasp.json` → no diffs in *.js/*.html.
- Sheets: Mill Blank Planning A4 formula, 388 rows, Q 44 non-blank; RefLists H1:N53; Tracker Open POs 381 rows; row 1 of the three workflow tabs identical (226 columns).
- Editor: `test_spdKey`, `test_trackerPush` print OK.

**Next action when resuming:** read the 2026-10-06 execution log for the 1 AM sync (forward + reverse summaries), then audit the seven pairs (0 "seed" cells, 17 flipped) and S1012 on both tabs; then send or paste Ody's draft.


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
