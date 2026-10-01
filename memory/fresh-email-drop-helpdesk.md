---
name: fresh-email-drop-helpdesk
description: "When starting a fresh email from a helpdesk ticket thread, leave helpdesk@ off and copy people's direct addresses"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 3dfd87ec-1cc9-4bc0-9c13-a38ddb1867a4
  modified: 2026-10-01T09:20:07.146Z
---

When Dan asks for a fresh email (not a reply) based on a helpdesk ticket thread and says "copy the same people", leave `helpdesk@laveapparel.com` off the recipients and copy each person's direct address instead (Gerardo is `itsupport@`). Say in the summary that helpdesk was left off.

**Why:** a fresh email to the helpdesk address would open a new Zammad ticket (assumed, not tested). Dan accepted the draft built this way on 2026-10-01. One occurrence so far; treat as a default, not a hard rule.

**How to apply:** only for new threads. Replies inside the ticket thread keep helpdesk, as in [[approve-means-proceed]] do it and report it rather than asking.
