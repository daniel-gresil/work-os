---
name: vps-c590f124-personal-server
description: "vps-c590f124.vps.ovh.us is Dan's server for his personal systems, not a Lave server"
metadata:
  node_type: memory
  type: reference
  originSessionId: 625c1243-d05d-40cb-89d3-bc89420d3688
  modified: 2026-11-06T16:33:31.949Z
---

`vps-c590f124.vps.ovh.us` is for Dan's personal systems (Dan said so on 2026-11-06). On 2026-11-06 it ran Trek (`trip.gresil.com`), Firefly III (`money.gresil.com`, see [[firefly-setup-locations]]) and the old Actual Budget container, behind one shared Caddy. The Lave systems (Snipe-IT, Zammad, Grafana, ERPNext) are on `vps-ed73f998`.

**Why:** on 2026-11-06 I recommended backing Firefly up to Lave's shared drive because that was the existing backup pattern, without noticing the data was personal.

**How to apply (my reading):** anything on this server is personal data. Keep it off Lave resources: Lave's shared drive, the `backup-tools` service account, Lave mailboxes. Use Dan's own daniel@gresil.com Google Workspace account instead. Before reusing a pattern from another server, check which side (personal or Lave) that server belongs to.
