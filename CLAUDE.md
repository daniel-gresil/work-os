# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Dan's work OS: the single source of his Claude Code setup (global instructions, skills, agents, hooks, settings, git rules, memory, client context), shared by his MacBook and Mac Studio. It must sit at `~/Developer/GitHub/work-os` on both. Sessions for non-code work (email, admin, tickets, research, cross-repo design) start here; code work starts in the client repo. Terms are defined in `CONTEXT.md`.

## How it is wired

- `setup.sh` symlinks `claude/` into `~/.claude/` (CLAUDE.md, settings.json, statusline, each skill, agent and hook one by one) and adds `git/config` to the global git config. Rerunnable; it backs up whatever it replaces to `~/.claude/backups/`.
- **Edit the files here, never through `~/.claude/...`**: Edit and Write refuse to write through a symlink.
- A new skill is a new folder under `claude/skills/`; run `./setup.sh` to link it. `~/.claude/skills/synced/` belongs to claude.ai and is not ours.
- `claude/hooks/work-os-sync.sh` runs on every session start (commit leftovers, rebase on GitHub, push) and end (commit, push). It only auto-commits an allowlist of paths; a new top-level folder must be added to that list or it will not sync. It never resolves a conflict: if it reports one, tell Dan and resolve it with him first.
- `git/config` picks commit identity and GitHub login by repo owner: `Lave-Apparel` remotes use `daniel0souza <daniel.souza@laveapparel.com>`, everything else `daniel-gresil <daniel@gresil.com>`. `git/ignore` hides Claude files in every repo; this repo's `.gitignore` re-includes them.
- Memory for sessions in this repo is `memory/` (set by `.claude/settings.json`). Each client repo's CLAUDE.md, secrets manifest and memory live in `clients/<client>/<repo>/` and are symlinked or pointed to from the repo's `.claude/settings.local.json`.
- `.state/` is git-ignored and machine-local: pending email drafts and offboarding run files. Client email text and credentials never get committed.

## Checks

```bash
./setup.sh                                  # idempotent; a second run prints only "done"
bash -n setup.sh claude/hooks/*.sh          # syntax
claude/hooks/work-os-sync.sh start          # run the sync by hand; silent means clean
git -C <any Lave repo> config user.email    # must print daniel.souza@laveapparel.com
```
