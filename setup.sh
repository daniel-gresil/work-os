#!/bin/bash
# Run once per Mac, safe to rerun. Links the curated parts of work-os into
# ~/.claude and the global git config. Anything it would replace is moved to a
# dated backup folder first; nothing is deleted.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
EXPECTED="$HOME/Developer/GitHub/work-os"
[ "$REPO" = "$EXPECTED" ] || { echo "work-os must live at $EXPECTED (found $REPO)"; exit 1; }

BACKUP="$HOME/.claude/backups/work-os-setup-$(date +%Y%m%d-%H%M%S)"

link() { # link <file-or-dir-in-repo> <path-under-home>
  local src="$1" dst="$2"
  [ "$(readlink "$dst" 2>/dev/null || true)" = "$src" ] && return 0
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    local kept="$BACKUP/${dst#"$HOME"/}"
    mkdir -p "$(dirname "$kept")"
    mv "$dst" "$kept"
    echo "backed up  $dst -> $kept"
  fi
  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
  echo "linked     $dst"
}

link "$REPO/claude/CLAUDE.md"      "$HOME/.claude/CLAUDE.md"
link "$REPO/claude/settings.json"  "$HOME/.claude/settings.json"
link "$REPO/claude/statusline.sh"  "$HOME/.claude/statusline.sh"
link "$REPO/claude/hooks/op-secrets-load.sh" "$HOME/.claude/op-secrets-load.sh"

# Skills, agents and hooks are linked one by one: ~/.claude/skills/synced is
# managed by claude.ai, and a Mac may hold items not yet merged into the repo.
for d in "$REPO"/claude/skills/*/; do d="${d%/}"; link "$d" "$HOME/.claude/skills/$(basename "$d")"; done
for f in "$REPO"/claude/agents/*.md; do link "$f" "$HOME/.claude/agents/$(basename "$f")"; done
for f in "$REPO"/claude/hooks/*; do link "$f" "$HOME/.claude/hooks/$(basename "$f")"; done
for f in "$REPO"/claude/docs/agents/*.md; do link "$f" "$HOME/.claude/docs/agents/$(basename "$f")"; done

# Global git rules: ignore file, per-org identity and login (see git/config).
git config --global --get-all include.path | grep -qxF "$REPO/git/config" \
  || git config --global --add include.path "$REPO/git/config"

for tool in gh jq git; do command -v "$tool" >/dev/null || echo "WARNING: $tool is not installed"; done
for acct in daniel-gresil daniel0souza; do
  gh auth token --user "$acct" >/dev/null 2>&1 || echo "WARNING: gh is not logged in as $acct (run: gh auth login)"
done

echo "done. Backups, if any: $BACKUP"
