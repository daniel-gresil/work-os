---
name: column-id-means-row-1-number
description: "At Lave, \"column ID\" means the unique number in row 1 of a sheet column, used to identify the column"
metadata:
  node_type: memory
  type: feedback
  originSessionId: d0ee4e47-84f1-4388-b3c1-f8e3ca9fcaa3
  modified: 2026-10-01T08:04:46.795Z
---

When Dan says "column ID", he means the number in row 1 of that column in a Lave Google Sheet. The numbers are unique and identify each column regardless of its position or header text.

**Why:** Lave sheets get columns moved and renamed; scripts and specs find columns by the row-1 ID (for example `getSheetCols()`), not by letter or header.

**How to apply:** In specs, cards and code, refer to and match columns by their row-1 ID (for example "Style# (6095)"). When Dan names a column, look up its ID in row 1 of the sheet rather than asking him or using the column letter.
