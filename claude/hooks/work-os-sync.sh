#!/bin/bash
# Keeps work-os in step between the two Macs.
#   start: commit leftovers, pull, push   (SessionStart; stdout goes into Claude's context)
#   end:   commit, push                   (SessionEnd; best-effort, may be cut off)
# Stays silent unless something needs Dan. Never resolves a conflict itself.
# ponytail: no lock, two sessions ending at once may race on the git index; the
# loser's changes are picked up by the next start.

REPO="$HOME/Developer/GitHub/work-os"
cd "$REPO" 2>/dev/null || exit 0
say() { [ "$1" = start ] && echo "work-os sync: $2"; }

if [ "$(git branch --show-current)" != main ]; then
  say "$1" "skipped, work-os is not on main."
  exit 0
fi

commit() {
  # Allowlist: only these paths are ever auto-committed. .gitignore additionally
  # keeps .env, .state/, .venv/ and settings.local.json out.
  local p
  for p in claude git clients memory .claude setup.sh .gitignore ':(glob)*.md'; do
    git add -A -- "$p" 2>/dev/null
  done
  git diff --cached --quiet || git commit -qm "sync: $(hostname -s) $(date '+%Y-%m-%d %H:%M')"
}

commit

if [ "$1" = start ]; then
  if ! git fetch -q origin 2>/dev/null; then
    say start "could not reach GitHub; working from the local copy."
    exit 0
  fi
  if ! out=$(git rebase -q origin/main 2>&1); then
    git rebase --abort 2>/dev/null
    say start "this Mac and GitHub both changed the same file. Nothing was merged. Tell Dan now and help resolve it before other work. git said: $out"
    exit 0
  fi
  [ -L "$HOME/.claude/settings.json" ] || say start "~/.claude/settings.json is no longer a symlink into work-os (Claude Code replaced it). Tell Dan; rerun setup.sh after copying any new settings into claude/settings.json."
fi

if [ -n "$(git rev-list origin/main..main 2>/dev/null)" ]; then
  git push -q origin main 2>/dev/null || say "$1" "push failed; changes are committed on this Mac only."
fi
exit 0
