---
name: credentials-once-per-session
description: "Dan is prompted once for credentials per session; cache them, never let scripts or agents call 1Password repeatedly"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1c4946bc-8acf-4798-9358-d627595202bf
  modified: 2026-10-09T07:00:51.329Z
---

Ask for a credential once and keep it in the environment for the rest of the session. Never run, or let a sub-agent run, a script that calls `op` on its own and triggers a biometric prompt each time.

**Why:** On 2026-10-09 a sub-agent ran the qb_sync_tool refresh locally; the script reads 1Password itself, and Dan got prompt after prompt. He said: "You ask once and save it in the environment, so you don't have to keep asking all the time."

**How to apply:** Prefer a route that needs no local credential (a GitHub Action, an existing cache under `~/.cache/claude-secrets/<repo>/env.sh`). If a repo has no secrets manifest, create one in `work-os/clients/<client>/<repo>/op-secrets.txt`, symlink it, load it once with `~/.claude/op-secrets-load.sh`, and source the cache in every call. Tell sub-agents the same rule in their prompt. See [[studio-ssh-no-keychain]].
