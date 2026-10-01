---
name: spd-column-sync
description: Add one SPD Dashboard -> WIP Lavanderia sync column end to end - compare values, add the pair to SPD_SYNC_COLUMNS, build the client comparison record sheet via the Sheets API, and save the client reply draft. Use when Daniel gives an S-id / column-id pair for the wip-lavanderia-print SPD sync.
---

Repo: `~/Documents/GitHub/wip-lavanderia-print` (cwd for git work). Tools live with this skill, not in the repo: `~/.claude/skills/spd-column-sync/tools/` (never commit them). Run every command as
`uv run --with google-api-python-client --with google-auth ~/.claude/skills/spd-column-sync/tools/spd_compare.py ...`.
Credentials come from 1Password in-process, Lave Apparel account (`laveapparel.1password.com`):
`op://hermes-crew/google-workspace-lave-service-account/credential` (workspace SA impersonating
daniel.souza@laveapparel.com: creates the record sheet in his Drive, edits sheets, saves Gmail drafts).
Never write the key to disk. Daniel no longer creates or shares sheets: pass `new` as the record id.

Match key is job + split (S1005+S1242 <-> 6059+7285, blank split = 01), in both the engine and the tool.

Inputs per column: the S-id / column-id pair and the client's email (subject + sender). Nothing else.

Per pair `<S-id> <lav_id>`:
1. **Compare** (no writes): `build` needs a record sheet, so for a first look run the compare only:
   `python3 -c` is not needed; just run `build` once Daniel gives the record sheet, or run
   `format`-free compare by calling `compute()`; report matched / same / different / blank counts and
   the pattern of the differences (e.g. price revision 0.22 -> 0.27).
   Dashboard row 2 usually holds the intended Lave target id: confirm it equals `<lav_id>`.
   If the dashboard column is all blank/zero (e.g. S1103 -> 6190), hold the pair and say why.
2. **Config**: add `{ src: "<S-id>", lav: <lav_id>, label: "<label>" }` to `SPD_SYNC_COLUMNS` in
   `_sync_spd_dashboard.js`. Commit on the feature branch; Daniel opens the PR at the end.
3. **Record sheet** (when there are differences): run `build new <S-id> <lav_id> "<label>"` (or `run new ...`
   to also draft). It creates the file in Daniel's My Drive, names it
   `WIP Lavanderia - <label> (<id>) comparison (<date>)`, tab `<label> <id>`, writes all matched rows
   (differences first), header/freeze/filter/Y-N dropdown, yellow only on rows that are not "same".
   Wording is "Lave", never "Lav".
4. **Reply draft** (never send): prefer `run <record_ss_id> <S-id> <lav_id> "<label>" "<gmail search>"`
   (build + draft, ONE 1Password prompt). Draft-only: `draft <record_ss_id> <S-id> <lav_id> "<label>" "<gmail search>"`
   where the search identifies the client's email (e.g. `from:x@y.com subject:"..." newer_than:30d`).
   Body: column added to the sync as approved in ADO, next run overwrites, link to the record sheet,
   counts, what changes. Paste the draft id and body back to Daniel.

Report in chat: counts table, what changes on the first run, sheet link, draft id. Keep it short.

Draft / tool notes:
- No email thread? Pass `"to:<addr>"` as the search and set `DRAFT_SUBJECT`; the draft is a fresh email, no "Re:".
- `DRAFT_BODY` skips the record-URL substitution: put the sheet link in the body yourself.
- When the JS pair has a `derive`, add the same transform to `DERIVE` in the skill's `tools/spd_compare.py` so compare/build agree with the sync.

## Adding a brand-new dashboard column (seeded from Lavanderia)
When Ody asks for a value that has no dashboard column yet, Daniel adds it to the dashboard and seeds it
once from Lavanderia; afterwards the dashboard owns it and the normal sync applies. Run
`uv run --with google-api-python-client --with google-auth ~/.claude/skills/spd-column-sync/tools/spd_add_column.py <after_sid> <new_sid> <lav_id> "<group>" "<sizes>" "<label>"`
(several 6-arg groups in one call). New S-ids = max row-1 S-id across all dashboard tabs + 1 (S1264 used on 2026-09-22; Garment Inventory holds S1247-S1263). Then add `{ src, lav, label }` to SPD_SYNC_COLUMNS and confirm `compare` reports all "same".
