---
name: wrap-up
description: End-of-session checklist for Claude Code. Use when the user says they're wrapping up, ending the session, finishing for the day, or asks to "wrap up", "finalize", "close out", or "summarize" a working session. Surfaces git state, proposes commits without making them, routes session learnings (architecture decisions, environment/infra facts, repeatable procedures) to the right docs and to Hindsight team memory, writes a handoff note for the next session, and recommends (but does not execute) merge-to-main.
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git remote:*), Bash(hindsight memory recall:*), Bash(hindsight memory retain:*), Read, Write, Edit, Glob, Grep
---

# Wrap-up: end-of-session checklist

You are wrapping up a working session. Your job is to leave the repo in a
clean, resumable state and to capture context that would otherwise evaporate
when this session ends.

## Hard rules — read these first

1. **Propose, do not execute, anything that changes git state.** Never run
   `git add`, `git commit`, `git push`, `git merge`, `git rebase`, `git reset`,
   or open a PR until the user says yes in chat. If you're unsure whether an
   action counts, ask.
2. **Show raw command output, then interpret.** Do not summarize git state
   from memory or assumption. Run the commands, paste the output, then
   explain.
3. **Work the steps in order and present results as you go.** Do not batch
   everything into one final message — the user should be able to approve or
   redirect after each step.
4. **Keep additions to docs short.** Bloated CLAUDE.md and bloated docs get
   skimmed past. If you're tempted to write more than ~10 lines into any
   single doc, consider whether it belongs in its own file instead.

## Step 1 — Surface the actual git state

Run these commands and show the output:

```
git status
git diff --stat HEAD
git log @{u}..HEAD --oneline 2>/dev/null || git log -10 --oneline
git branch --show-current
git remote -v
```

Then tell the user, in plain English:
- What's uncommitted (staged, unstaged, untracked) — group by category
- Whether anything looks unintentional: stray debug prints, commented-out
  blocks, modified config files outside the scope of the session, large
  binary files, anything in `node_modules`/`.venv`/`__pycache__`/`.DS_Store`
- Whether any new files should probably be in `.gitignore` instead of
  committed
- How far the branch is ahead of its upstream

If `git status` is clean and there's nothing ahead of upstream, skip to
Step 3 — there's nothing to commit.

## Step 2 — Propose commits for uncommitted work

Before proposing anything, **detect the repo's commit conventions**:
- Run `git log -20 --oneline` and look at recent commit messages
- Note the style: Conventional Commits (`feat:`, `fix:`), emoji prefixes,
  ticket numbers, plain prose, etc.
- Match that style in your proposals

Then for everything uncommitted that should be saved:
- Group changes into logical units (one commit per unit; do not propose a
  single mega-commit unless the changes truly are one unit)
- For each proposed commit, show:
  - The proposed commit message (matching house style)
  - The exact files included
  - One-line rationale for why these belong together
- Flag separately anything that should be **discarded, stashed, or
  gitignored** instead of committed

**Then stop and wait.** Do not run `git add` or `git commit` until the user
approves. If they approve some but not others, only act on the approved ones.

If the user has a Claude Code attribution preference (check CLAUDE.md or just
ask if it's not stated), respect it — some users want the `Co-authored-by:
Claude` trailer, some don't.

## Step 3 — Capture session learnings, routed to the right file

Ask yourself: "What did we learn, decide, or discover this session that
future-me or future-Claude needs to know to not repeat mistakes or
relitigate decisions?"

For each item, route to the **right destination** — do NOT dump everything
into CLAUDE.md, and do NOT dump everything into Hindsight:

| Type of learning                                                                | Goes in                                          |
|---------------------------------------------------------------------------------|--------------------------------------------------|
| Project-wide conventions, "how we work here"                                    | `CLAUDE.md`                                      |
| Domain knowledge, data model, business rules                                    | repo markdown docs (`docs/`, `README.md`, etc.)  |
| Architectural decisions with tradeoffs                                          | `docs/adr/NNNN-title.md` (create dir if needed)  |
| Reusable workflows we'd invoke again                                            | `.claude/skills/<name>/SKILL.md`                 |
| Gotchas, bugs, and their fixes                                                  | `TROUBLESHOOTING.md` or inline code comments     |
| Coding rules that should be enforced                                            | `.claude/rules/` or CLAUDE.md "Rules" section    |
| Cross-repo technical knowledge: infra runbooks, command recipes, debugging notes, architecture lessons — anything an agent in **any** Lave code repo would want to recall | Hindsight bank `lave-tech` (via the `hindsight-self-hosted` skill) |
| Business / operational knowledge: company processes, vendor relationships, finance/legal workflows, product/brand decisions, team norms — anything not tied to a code repo | Hindsight bank `lave-business` (via the `hindsight-self-hosted` skill) |

Before writing, **check what already exists**: glob for `CLAUDE.md`, `docs/`,
`docs/adr/`, `TROUBLESHOOTING.md`, `.claude/rules/`. Don't propose creating
files in directories that don't fit the project's structure.

**Hindsight vs repo files:** repo files are the source of truth for things
tied to *this* codebase; Hindsight is shared cross-session, cross-repo,
cross-agent team memory. If the learning is repo-local ("how this codebase
does X"), put it in the repo. If it would help future-Claude working in a
*different* Lave repo, also `retain` it to `lave-tech`. Routing rule for
Hindsight: agent-in-a-repo → `lave-tech`; human-running-the-business →
`lave-business`. When in doubt for tech-adjacent items, prefer `lave-tech`.

For each learning, propose:
- The exact file path **or** Hindsight bank + the exact `retain` text
- Where in it (append / which section / new file) for repo destinations
- The exact text to add (kept short — usually 1–5 lines)

**Then stop and wait for approval before writing or `retain`ing.**

If there are no real learnings — sometimes a session is just routine
implementation — say so and skip this step. Don't manufacture content.

## Step 4 — Write a handoff note

Create or update `.claude/HANDOFF.md`. If it doesn't exist, create it. If it
exists, prepend a new dated section at the top (newest first) so the file
stays useful over time.

Use this template:

```markdown
## YYYY-MM-DD — <branch name> — <one-line topic>

**Goal of this session:** <one paragraph: the actual goal, not the task list>

**Done:**
- <bullet, with file refs like `path/to/file.py:42`>
- ...

**In progress:**
- <what's half-built and where to pick up>

**Open questions / blockers:**
- <anything deferred or unresolved>

**Key decisions and why:**
- <decision> — <one-line rationale>

**Files touched:**
- <list>

**How to verify the current state:**
- <commands to run: tests, lint, type checks, manual checks>

**Next action when resuming:**
- <one concrete next step>
```

Be concrete. "Refactored the data loader" is useless; "Refactored
`ingest/loader.py` to use Polars instead of pandas; benchmarks pending in
`tests/bench_loader.py`" is useful.

This file should be committed (it's a note for the team and future-you), so
include it in commit proposals if it's new or changed.

## Step 5 — Decide on merge-to-main

Before recommending anything, gather the facts:

- Run the project's test command if there is one (check `package.json`,
  `pyproject.toml`, `Makefile`, or recent CI config to find it). If you can't
  find it, ask the user.
- Run lint / type checks if configured.
- Check `git log main..HEAD --oneline` (or `master`, whichever the repo uses)
  to see what would be merged.

Then present a recommendation with reasoning:

- **Is the work a complete logical unit, or mid-stream?**
- **Are tests / lint / types green?** (Show output.)
- **Is the branch reviewable as one thing, or has it grown into multiple
  unrelated changes that should be split?**
- **Does the repo's history suggest direct merges to main, or PR review?**
  (Check recent main commits — are they merge commits, squashes, or direct?)

Recommend exactly ONE of:

- **(a) Stay on branch, not ready.** Reason: <...>
- **(b) Open a PR.** Propose title + description body (don't open it yet).
- **(c) Squash-merge to main.** Only recommend this if the work is small,
  self-contained, green, and matches how this repo handles merges. Show the
  exact commands you'd run.

**Wait for the user's decision.** Do not push, open PRs, or merge until they
say yes.

## Step 6 — Final summary

End with a 5-line status the user can paste into standup notes or save
elsewhere:

```
DONE:    <what got done>
PENDING: <what's still open>
BLOCKED: <what's blocked, if anything>
WHERE:   <branch + key files>
NEXT:    <very next action when resuming>
```

Keep this terse. No prose, just the five lines.

## When to skip steps

- Clean working tree, nothing ahead of upstream → skip 1, 2, 5; just do 3,
  4, 6 if there are learnings worth capturing.
- Pure exploration session with no code changes → just do 4 and 6.
- User says "just commit and wrap up" → still propose first, but be brief
  about it.
