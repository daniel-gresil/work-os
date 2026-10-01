# 1. Claude memory lives in work-os, per project

Date: 2026-10-01

## Context

Claude Code stores auto memory in `~/.claude/projects/<path-key>/memory/`, local to one Mac and keyed by the project's path. Dan works on two Macs, and client repos must contain nothing Claude-related.

## Decision

Each project's memory is a folder in this repo: `memory/` for work-os sessions, `clients/<client>/<repo>/memory/` for a client repo. The `autoMemoryDirectory` setting points there, from `.claude/settings.json` here and from each client repo's git-ignored `.claude/settings.local.json`.

## Alternatives rejected

- One shared memory for everything: the index loaded each session is capped at 200 lines, and code detail from one repo would crowd out the rest.
- Symlinking `~/.claude/projects/*/memory`: depends on identical repo paths on both Macs and on undocumented symlink behaviour.
- Leaving client-repo memory machine-local: the two Macs would keep diverging.

## Consequences

Memory syncs through the normal work-os git sync. Notes about client projects are committed to this private repo, so they must never hold credentials or email content. A client repo gets its pointer the first time it is worked on after setup.
