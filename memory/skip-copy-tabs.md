---
name: skip-copy-tabs
description: "Leave \"Copy of…\" and personal copy tabs out when listing sheet tabs that need work"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 6ee053b1-94f4-45a4-a123-cfedaf4f6fa0
  modified: 2026-10-01T09:41:45.210Z
---

When listing the tabs of a Lave sheet that need work (cards for developers, fixes, column ID changes), leave out `Copy of …` tabs and personal copies such as `<name> Copy`. Only the real working tabs count.

**Why:** On 2026-10-01 Dan had an ADO card narrowed to the two real tabs after it listed two copy tabs too, and confirmed this as a general rule.

**How to apply:** Still scan every tab to find where something appears, but report and assign work only for the non-copy tabs. Mention the copies in chat only if they matter. A person-named tab that is not a copy (for example a person's own working tab) stays in. Related: [[column-id-means-row-1-number]].
