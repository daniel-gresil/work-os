---
name: blocked-sheet-writes-hand-over-the-command
description: "When the permission classifier blocks a write to a shared sheet or a merge, hand Dan the exact command to run with the ! prefix instead of trying another route"
metadata:
  type: feedback
---

When Claude Code's auto-mode classifier denies a write to a shared Google file, a PR merge, or even writing the script that would do it, stop and give Dan the exact one-line command. He runs it with the `!` prefix so the output lands in the session. Do not look for another route.

**Why:** On 2026-10-05 this happened four times in one session (sheet batch updates, a deletion script, a PR merge); the hand-over worked every time and kept each write explicit.

**How to apply:** Keep the script ready and verified read-only first, state the expected output, then hand over the command. Related: [[analysis-before-changes]].
