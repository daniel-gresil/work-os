---
name: live-editor-edits-not-adopted
description: "Apps Script code edited directly in the editor without a PR is not imported into git; the nightly drift action resets live to main"
metadata:
  type: project
---

For Lave GAS repos, code that someone edits directly in the Apps Script editor is not adopted. Do not open a PR to import it; the daily drift action resets the live project to `main`. The owner of the edit must go through a branch and PR.

**Why:** Dan's decision on 2026-10-05 when a pull-sheet PDF feature ("papeletas") appeared live in WIP Lavanderia & Print without a PR: "whoever edited live made a mistake, and it's not going to be added".

**How to apply:** Before `clasp push`, diff live against main; report live-only edits to Dan, do not merge them. Push from a clean export of main (see the repo memory on clasp push). Related: [[no-github-issues]].
