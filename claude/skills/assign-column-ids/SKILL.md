---
name: assign-column-ids
description: Assign Lave column IDs — claim free rows in the central column registry (file 9085) and stamp the IDs into row 1 of any Google Sheet tab that follows the row-1-ID convention. Use when the user asks to assign, register, or fill in missing column IDs for a sheet. Never inserts columns.
---

# Assign column IDs

**Level: L2.** Dan naming the tab and the columns that need IDs is the approval;
anything beyond that list (other tabs, re-stamping an existing ID) needs his yes first.

Every Lave sheet tab carries a numeric column ID in row 1 (human header on the
next row). IDs come from the **central column registry** ("9085"):
`1KM8vJCuAIGoWP5nmIBnnXZPcsz4Qzn459aIyk1V4eCY`, tab `1) Column Headers`,
header row 3, data from row 6. A=ID, B–E=Column Header 1–4, F=Department,
H=Assigned Date, **P=Hyperlink**, **W=Notes**. A row with blank B is free.

Free IDs live in two places: leftover rows inside a department's block (most
departments have a few; Finance has almost none), and the block **7272–7500
reserved for Vintage Industries** (marker in C, no department) — use it for
VI files and set F to the requesting department.

Exception: "SPD Mfg - Dashboard" (1AMN1Ivy…) keeps its own file-local S-numbered IDs in its
`Column Config` tab (ID | name | tab). Do not claim registry rows for it; pick the next free
S-ID (recorded in that repo's CLAUDE.md), stamp row 1, and append the row to Column Config.

This skill only fills in IDs. It never adds a column to a sheet and never
appends rows to the registry. Inserting columns in 9025 is a separate,
file-specific skill in the 9025_WIP repo.

All access goes through `assign_column_ids.py` in this folder (stdlib only;
OAuth via the cached creds in `lave-file-access-audit/.cf_creds.json`, or `op`).

## Steps

1. **Read the target tab's header row** (row 2, or the frozen-row count) and
   row 1, and list the columns whose row-1 cell is blank. Confirm the list and
   the department with the user.

2. **Find free IDs:**
   ```
   python3 assign_column_ids.py find --dept <Department> -n <count>
   python3 assign_column_ids.py find --vintage -n <count>     # VI files
   ```
   `find --vintage` lists the lowest free Vintage-marked rows first (6009+), not
   the 7272–7500 block; pick from 7272–7500 by hand. A free registry row can
   already be stamped on a sheet (6228 was): check each candidate ID against
   row 1 of every tab in the target file before claiming.

   Before claiming, grep the registry for an existing row with the same header
   in the same department/file; if one exists, tell the user and offer to
   reuse it instead of claiming a new ID.

3. **Claim each ID** (re-verifies the row is free; writes B, F, H, P, W and any
   of C/D/E given — C keeps its reservation marker unless `--h2` is passed):
   ```
   python3 assign_column_ids.py claim --id 7272 --h1 "TxnDate" --h3 "Invoice VI" \
     --dept Finance --file 7002 --notes "Invoice date sent to QBO as TxnDate"
   ```
   `--file` is the Lave file number (9025, 7001 and 7002 are known; otherwise pass `--url`).
   `--notes` is a one-line description of what the column is used for.

4. **Stamp the IDs into row 1** of the target tab. Checks each ID is claimed,
   refuses to overwrite a non-blank row-1 cell unless `--force`, prints the
   header it is pairing with, then writes numbers:
   ```
   python3 assign_column_ids.py stamp --sheet <spreadsheet id or url> --tab Invoices \
     C=7272 F=7273 I=7274
   ```

5. Report the ID ↔ header table to the user, plus anything odd you saw
   (an ID whose registry header does not match the column it sits on, other
   tabs still missing IDs).
