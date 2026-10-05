# Mill Blank Planning tab (WIP Lavanderia) — the formula

Written 2026-10-05. The tab is a read-only view over Open Production: row 1 = column ids, row 2 = headers,
row 3 blank, one array formula in **A4** (nothing else on the tab). Columns A–P pull Open Production by the ids in
`$A$1:$P$1`; Q (id 7286) is the Inventory Status. Date columns I:N are formatted `d-mmm-yyyy`.

Rows kept: job (6059) not empty, Blank Pick Up Date (7317) blank and Blank Rcv Greitzer Date (6162) blank.

```
=ARRAYFORMULA(LET(
hdr, 'Open Production'!$1:$1,
body, 'Open Production'!$A$6:$ZZ,
c, LAMBDA(id, INDEX(body, 0, MATCH(id, hdr, 0))),
ids, $A$1:$P$1,
keep, (c(6059)<>"") * (c(7317)="") * (c(6162)=""),
data, REDUCE(c(INDEX(ids, 1)), SEQUENCE(COLUMNS(ids) - 1, 1, 2), LAMBDA(acc, k, HSTACK(acc, c(INDEX(ids, k))))),
key, c(6115) & "|" & c(6116) & "|" & c(6117),
rk, RefLists!$I$3:$I & "|" & RefLists!$L$3:$L & "|" & RefLists!$M$3:$M,
tab, IF(key = "||", "", IFERROR(XLOOKUP(key, rk, RefLists!$H$3:$H), "")),
status, IF(tab = "", "", HYPERLINK(XLOOKUP(key, rk, RefLists!$N$3:$N), tab)),
IFERROR(FILTER(HSTACK(data, status), keep), "No mill blank POs waiting for pick up")
))
```

## Key table it reads: RefLists!H:N

Copied every night by `pushToGarmentInventoryTracker` (`_push_tracker_open_pos.js`) from the Tracker's Inventory tab.
Row 1 ids `7286 7287 7288 7289 7290 7291` (N1 blank), row 2 headers `Tab, Supplier, Customer, Div, Style #, Colorway,
Tab link`, data from row 3. Ledgers with no supplier / style / colorway are skipped; a key on two ledger tabs keeps the
first. The match is supplier|style|colorway, case-insensitive (XLOOKUP).

## Known ceilings

- `$A$6:$ZZ` assumes Open Production stays under 702 columns (228 today).
- A stray space in 7317 or 6162 hides the row (row 111 had one on 2026-10-05; cleared).
