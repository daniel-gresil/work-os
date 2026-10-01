---
name: ask-questions-one-at-a-time
description: "Dan wants design or interview questions asked one at a time, each with a recommendation"
metadata:
  node_type: memory
  type: feedback
  originSessionId: fdb41d87-2030-499e-811b-c4afc622f339
  modified: 2026-10-01T07:55:44.547Z
---

When interviewing Dan about a design or plan, ask one question per message, give a recommendation, and wait for his answer before the next.

**Why:** Given a round of twelve questions at once (2026-10-01, work-os design), he asked to go through them one by one. He usually answers "agreed" to a clear recommendation and adds corrections inline.

Repeated with emphasis on 2026-10-01 (ADO task planning): a message that asked one question but also listed other pending decisions and questions for the customer still read to him as a pile. "Always, always, always ask one at a time."

**How to apply:** Number the question ("Q3 of 13"), restate what the last answer settled, then ask the next. The message carries that one question only: don't list the other open decisions, queued questions, or new findings alongside it; hold them for their own turn. Keep it short. State the question in plain language with a concrete example of what goes wrong or what each option does ("VP-4107 gets logged again at 11:00..."); a bare technical question got "I don't understand", and the worked example got a clear answer. Look up facts yourself first (both Macs are reachable; the Studio over Tailscale SSH as `daniels-mac-studio`).
