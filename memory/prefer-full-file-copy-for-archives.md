---
name: prefer-full-file-copy-for-archives
description: "Archive sheet tabs by making a full copy of the file, then deleting the tabs; not tab-by-tab copies"
metadata:
  type: feedback
---

To archive old tabs out of a Google Sheet, Dan makes a full copy of the file (File > Make a copy, done by his account) and the old tabs are then deleted from the live file. Do not build a tab-by-tab copy into a new spreadsheet.

**Why:** On 2026-10-05 a scripted tab-by-tab archive broke cross-tab formulas, showed images as pending and needed a freeze step; Dan asked "Isn't it easier just to make a backup?". The full copy keeps everything intact and doubles as the rollback point.

**How to apply:** Ask Dan for the copy (the service account has no Drive storage), verify it tab by tab through the API, share it without notifications, then delete the tabs. See [[analysis-before-changes]].
