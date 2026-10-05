# WIP Lavanderia & Print

Vintage Industries' production WIP spreadsheet and the nightly syncs that move data between it, the SPD Mfg Dashboard and the Garment Inventory Tracker.

## Language

### Sheets

**Lavanderia**:
The WIP Lavanderia & Print spreadsheet; Open Production is its live tab, Shipped 2026 and Cancelled POs its history tabs with the same column order. Older shipped tabs live in the Archive.
_Avoid_: VI WIP, Lav, Web Lavanderia

**Archive**:
WIP Lavanderia & Print - ARCHIVE 2026-10-05 (Shipped 2022-2025): a full copy of Lavanderia as of 2026-10-05 holding Shipped 2022, Shipped 2023 and Shipped Old (2024–2025). Those tabs no longer exist in Lavanderia.

**Dashboard**:
The SPD Mfg Dashboard, the customer-facing sheet SPD edits. WIP Planned and WIP Shipped are the tabs the syncs read and write.
_Avoid_: SPD WIP

**Tracker**:
The LAI & VI Garment Inventory Tracker, where mill blank stock is kept; one ledger tab per blank.

**Ledger tab**:
A Tracker tab named by a three-digit number (001, 002, …) holding the movement history of one blank (supplier + style + colorway).
_Avoid_: history tab, inventory tab

### Columns

**Column ID**:
The number in row 1 that identifies a column regardless of its letter or header. Lavanderia and Tracker IDs come from the central column registry; Dashboard IDs are file-local S-numbers.

**Pair**:
One Dashboard column and one Lavanderia column kept equal by a sync; the source side owns the value.

**Target row**:
Row 2 of the Dashboard, where the Lavanderia ID a column is meant to reach is written. Pink means planned, grey with an orange border means synced.

**Owner row**:
Row 3 of the Dashboard (row 3 on Lavanderia), naming who types into the column: SPD, VI, or a person.

**Job key**:
The VI job number plus split that matches a row across sheets; a blank split means 01, TBD means no key.

### Syncs

**Dashboard sync**:
The nightly pass that copies Dashboard-owned pairs into Open Production for matched jobs.

**Reverse sync**:
The nightly pass that copies Lavanderia-owned pairs up to the Dashboard (first pair: Blank PO Issue Date → Issued).

**Seed**:
A one-time copy that fills the owner side from the other side before a pair goes live, so the first run loses nothing.

**Mill Blank Planning view**:
The Lavanderia tab listing mill blank POs not yet picked up: both Blank Pick Up Date and Blank Rcv Greitzer Date are blank. Read-only, derived from Open Production.

**Open POs view**:
The Tracker tab listing mill blank POs not yet received at VI (Blank Rcv VI Date blank), pushed from Open Production nightly.

**Inventory Status**:
The ledger tab number of a job's blank, derived by matching supplier + style + colorway against the Tracker. Replaces the In-stock and Availability lookups. Looked up in the Key table (RefLists!H:N) and shown as a link to the ledger tab; on the Tracker's Open POs view it carries id 7286.

**Key table**:
RefLists!H:N in Lavanderia: Tab, Supplier, Customer, Div, Style #, Colorway, Tab link (ids 7286–7291 in row 1, data from row 3), copied from the Tracker's Inventory tab each night by the Tracker push. Empty ledgers are skipped; a key on two ledger tabs keeps the first.
