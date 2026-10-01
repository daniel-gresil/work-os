#!/usr/bin/env bash
# op-secrets-hook.sh — enforce the 1Password session-cache convention (see ~/.claude/CLAUDE.md).
# Two entry points, dispatched by $1:
#   session-start : run ~/.claude/op-secrets-load.sh once if the repo has a manifest
#   pre-bash      : block ad-hoc `op read` in manifest repos; nudge elsewhere
set -uo pipefail

mode="${1:-}"
input="$(cat)"

repo_root_for() {
  git -C "$1" rev-parse --show-toplevel 2>/dev/null || echo "$1"
}

cwd="$(jq -r '.cwd // empty' <<<"$input")"
[ -n "$cwd" ] || cwd="$PWD"
root="$(repo_root_for "$cwd")"
manifest="$root/.claude/op-secrets.txt"
env_file="$HOME/.cache/claude-secrets/$(basename "$root")/env.sh"

case "$mode" in
session-start)
  [ -f "$manifest" ] || exit 0
  # ponytail: freshness = cache newer than manifest. Rotated secrets linger until
  # the manifest is touched; on auth failure, rerun ~/.claude/op-secrets-load.sh.
  if [ -f "$env_file" ] && [ "$env_file" -nt "$manifest" ]; then
    echo "op-secrets: cached 1Password secrets ready — 'source $env_file' in Bash calls that need them. Do not call 'op read' directly."
    exit 0
  fi
  if "$HOME/.claude/op-secrets-load.sh" "$manifest" >/dev/null 2>&1; then
    echo "op-secrets: 1Password secrets loaded — 'source $env_file' in Bash calls that need them. Do not call 'op read' directly."
  else
    echo "op-secrets: loader failed (biometric declined or op error). Run ~/.claude/op-secrets-load.sh before secret-touching work."
  fi
  ;;
pre-bash)
  cmd="$(jq -r '.tool_input.command // empty' <<<"$input")"
  case "$cmd" in
  *op-secrets-load.sh*) exit 0 ;;
  *"op read"* | *"op item get"*) ;;
  *) exit 0 ;;
  esac
  if [ -f "$manifest" ]; then
    jq -n --arg reason "Ad-hoc 'op read' blocked: this repo uses the op-secrets manifest. If the secret is already cached, just 'source $env_file'. If it's new, append its op:// ref to .claude/op-secrets.txt, run ~/.claude/op-secrets-load.sh, then source the cache — never call op directly." \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  else
    jq -n --arg ctx "Reminder (user CLAUDE.md): if this session needs 1Password secrets, create .claude/op-secrets.txt with the op:// refs and run ~/.claude/op-secrets-load.sh so biometrics fire once per session; then 'source $env_file' in later Bash calls." \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$ctx}}'
  fi
  ;;
esac
exit 0
