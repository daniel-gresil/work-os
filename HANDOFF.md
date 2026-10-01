# Handoff

## 2026-10-01 — work-os initial build

Done: git rules, setup.sh, sync hooks, merged global CLAUDE.md and wrap-up,
plugin set, gmail-draft + draft-email-reply (tested live on MacBook),
offboard-workspace-user (offline tests only), Studio set up, repos consolidated
into ~/Developer/GitHub on both Macs.

Open:
- Studio, in person: confirm the sync hook reaches GitHub; run
  ~/.claude/op-secrets-load.sh in work-os for the Gmail credential.
- Studio: revoke the Anthropic API key in ~/.claude/settings.local.json and
  delete that rule.
- Compare the Studio's old op-secrets-load.sh (single `op run`, in
  ~/.claude/backups/work-os-setup-20260930-233409/) with the shared one.
- send-alert: move its .env key to 1Password so it works on the Studio.
- infra-stack: unpushed May commit b42fc75 (HINDSIGHT_CP_DATAPLANE_API_KEY
  docs) is only in the Studio Trash.
- Regenerate the auto-mode environment notes in claude/settings.json.
- offboard-workspace-user: never run live from Claude Code.
- Per repo, as separate tasks: untrack Claude files in the seven Lave repos;
  move each repo's memory into clients/lave/<repo>/memory.
