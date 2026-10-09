---
name: explain-designs-before-after
description: Explain a multi-part design as a plain "today / after this change" story before the column-level spec
metadata:
  type: feedback
---

When a design has several moving parts (a script, a tab, an email, a formula), first tell it as two
numbered stories in plain words: what happens today, step by step, and what happens after the change.
Only then show the spec with column IDs and function names.

**Why:** on 2026-10-05, after a column-level revision of the SPD AR Ledger design, Dan said
"Can you explain it better? I don't understand it." The before/after version landed at once.
**How to apply:** avoid words like "upsert" or "script-owned columns" in the story; say who types
what, where, and what the script does with it. Related: [[ask-questions-one-at-a-time]].
