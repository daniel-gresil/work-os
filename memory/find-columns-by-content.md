---
name: find-columns-by-content
description: "When a sheet column cannot be found by header text, search the data for known values before saying it does not exist"
metadata:
  node_type: memory
  type: feedback
  originSessionId: d0ee4e47-84f1-4388-b3c1-f8e3ca9fcaa3
  modified: 2026-10-01T08:39:43.103Z
---

When a column in a Lave sheet cannot be found by its header text, search the sheet's data for known values (a style number, a supplier name, a colour) and identify the column from where they appear. Only then report it as missing.

**Why:** On 2026-10-01 I told Dan that Open Production had no supplier, blank style or blank colour columns. They existed under headers I did not expect ("Mill Blank Brand Name", one with no header text). Dan had to tell me to search by content.

**How to apply:** Take sample values from the other file in the match (for example the tracker's style numbers), scan every column for them, and report the column by its row-1 ID; see [[column-id-means-row-1-number]]. Browser exports drop merged header cells, so headers alone are unreliable.
