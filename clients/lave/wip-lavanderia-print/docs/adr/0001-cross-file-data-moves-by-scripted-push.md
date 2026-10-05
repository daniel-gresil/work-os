---
status: accepted
date: 2026-10-05
---

# Cross-file data moves by scripted push from this repo, never IMPORTRANGE

Lavanderia exchanges rows with two other spreadsheets: the SPD Mfg Dashboard (pairs in both directions) and the Garment Inventory Tracker (Open POs view, Inventory key table). IMPORTRANGE was removed from these files earlier because it made them slow and broke silently when a source file moved or a column shifted. We decided that every cross-file move is a nightly Apps Script pass in this repo that resolves columns by row-1 ID and writes plain values, so one codebase owns all the movements and the sheets stay formula-free across file boundaries. Within one file, a derived tab (Mill Blank Planning) may still be a formula over its own data.

## Considered options

- IMPORTRANGE + QUERY in the receiving file: zero code, but reintroduces the load and the silent #REF! failures that led to its removal.
- A script inside each receiving file: same result, but the Tracker and Dashboard have no repo, drift check or deploy path, so changes there are invisible.

## Consequences

- A new cross-file need (e.g. the Tracker's Inventory key table in Lavanderia's RefLists) is a new pass here, not a formula in the other file.
- The receiving file sees data as of the last nightly run, not live.
