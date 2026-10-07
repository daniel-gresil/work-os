---
status: accepted
date: 2026-10-06
---

# Cell-by-cell writes for columns a script cannot write back

The Dashboard sync writes a pair by reading the whole Lavanderia column, replacing the matched rows and writing the whole column back. That put back cells the sync does not own, and two kinds of content refuse it: a pasted in-cell picture (Image column, "Service error: Spreadsheets") and a hand-typed value outside a strict dropdown (COO, "violates the data validation rules"). One refused cell failed the run, and because Apps Script buffers writes, every pending write went with it: the three pairs added on 2026-10-05 never ran, nor did the link pairs or the reverse sync after them. Pairs flagged `formula: true` or `cells: true` are now written cell by cell, only where the value changes, each write flushed inside a `try` so a refused cell is logged (`cellsNotWritten`) and skipped.

## Considered options

- Cell-by-cell for every pair: one write path, but about 70 pairs have run whole-column for weeks without a fault, and a flush on this file takes seconds; a day with many changed cells could pass the 6-minute limit.
- Correct the sheet instead (remove pasted pictures, fix the COO values): the cells belong to the users, and the next paste would stop the sync again.

## Consequences

- A new pair whose Lavanderia column has a strict dropdown or can hold pictures needs `cells: true` (or `formula: true`); `test_spdKey` asserts the current list.
- A cell pair does not support `keepIfSourceBlank` or `numberFormat`; the self-check refuses that combination.
- The first run after a bulk change is slower: about 30 changed cells added two minutes on 2026-10-06 (4 min 18 s in total).
