---
name: wrap-up
description: End-of-session checklist for Claude Code. Use when the user says they're wrapping up, ending the session, finishing for the day, or asks to "wrap up", "finalize", "close out", or "summarize" a working session. Surfaces git state, proposes commits without making them, routes session learnings to the right docs and to Hindsight, writes a handoff note, recommends (but does not execute) merge-to-main, then runs the reflection: what Dan corrected, what repeated, what preferences he showed, the task log, skill usage, and pending email drafts. In a non-code session it runs only the reflection.
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git remote:*), Bash(hindsight:*), Read, Write, Edit, Glob, Grep
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

5. **Nothing Claude-related goes into a client repo.** No attribution or
   co-author lines in any proposed commit or PR. Never propose committing
   `CLAUDE.md` or anything under `.claude/` in a client repo; those live in
   `~/Developer/GitHub/work-os/clients/<client>/<repo>/`.
6. **Nothing is written until Dan approves it.** Every memory, skill edit,
   Hindsight `retain`, log line and style lesson is proposed first.

## Step 0 — Which kind of session was this?

- **Code session** (started in a client repo, code changed): run every step.
- **Non-code session** (started in `work-os`: email, admin, tickets, research,
  design): skip Steps 1, 2, 4 and 5. `work-os` commits and pushes itself
  through its sync hook. Run Steps 3, 3b and 6.

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

Proposed commit messages never mention Claude. Before proposing, run
`git config user.email` and show it: `Lave-Apparel` repos must show
`daniel.souza@laveapparel.com`, everything else `daniel@gresil.com`. If it is
wrong, stop and say so.

## Step 3 — Capture session learnings, routed to the right file

Ask yourself: "What did we learn, decide, or discover this session that
future-me or future-Claude needs to know to not repeat mistakes or
relitigate decisions?"

For each item, route to the **right destination** — do NOT dump everything
into CLAUDE.md, and do NOT dump everything into Hindsight:

| Type of learning                                                                | Goes in                                          |
|---------------------------------------------------------------------------------|--------------------------------------------------|
| Project-wide conventions, "how we work here"                                    | The repo's `CLAUDE.md`, which for a client repo is `work-os/clients/<client>/<repo>/CLAUDE.md` |
| Domain knowledge, data model, business rules                                    | repo markdown docs (`docs/`, `README.md`, etc.)  |
| Architectural decisions with tradeoffs                                          | `docs/adr/NNNN-title.md` (create dir if needed)  |
| Reusable workflows we'd invoke again                                            | `work-os/claude/skills/<name>/SKILL.md` (see Step 3b for when) |
| Gotchas, bugs, and their fixes                                                  | `TROUBLESHOOTING.md` or inline code comments     |
| Coding rules that should be enforced                                            | The repo's `CLAUDE.md` "Rules" section (in `work-os` for client repos) |
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

## Step 3b — Reflection: learn how Dan works

All paths are under `~/Developer/GitHub/work-os/`. Present one short list of
proposals covering the six parts below, then wait. Write only what Dan
approves. Skip any part with nothing real to report.

**1. Corrections and preferences.** Go back through the session for every
place Dan corrected you, rejected an approach, or stated how he wants
something done. For each, propose where it goes:

| What it is | Goes in |
|---|---|
| Applies to every session, must never be missed | `claude/CLAUDE.md` |
| Applies to one skill | that skill's `SKILL.md` |
| How Dan likes to work, in this project | the project's memory folder (`memory/`, or `clients/<client>/<repo>/memory/`) |
| A fact about Lave (system, person, vendor, incident, reason) | Hindsight `lave-tech` or `lave-business` |

A one-off edit is not a preference. Say when you are unsure whether something
is a pattern, and let Dan decide.

**2. Task log.** Read `task-log.md`. Show Dan the existing task types and
propose either a match or a new type for this session's task. After he
confirms, append one line:

```
YYYY-MM-DD | <client> | <task type> | <a few words on what was done>
```

No email content, names of external people, or client data in this file.

**3. Third occurrence.** If that task type now appears three or more times and
has no skill, say so and offer to draft one from those sessions' notes,
starting at L0 or L1. If Dan says "not yet", ask again at the next occurrence.

**4. Skill usage.** For each `work-os` skill used this session, append a line
to `skill-usage.md`:

```
YYYY-MM-DD | <skill> | <level> | clean   (or: corrected — <what Dan changed>)
```

If a skill's last five lines are all `clean` and you have not asked since that
streak began, ask whether to raise its level, and list what would have to
change in the skill to do so. Never raise a level yourself. Never propose a
level above L2 for a skill that sends or deletes.

**5. Pending email drafts.** If `.state/pending-drafts/` holds drafts, run the
`draft-email-reply` skill's comparison step: find the ones Dan has since
sent, compare each with what he sent, and propose style lessons for
`clients/lave/email-style.md`. Drop drafts older than 14 days.

**6. Glossary.** If a term was settled or changed this session, propose the
edit to `CONTEXT.md`.

## Step 4 — Write a handoff note

Create or update the repo's handoff file. For a client repo this is
`~/Developer/GitHub/work-os/clients/<client>/<repo>/HANDOFF.md`, so it reaches
both Macs and never touches the client repo. If it exists, prepend a new dated
section at the top (newest first) so the file stays useful over time.

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

Do not include this file in commit proposals. It lives in `work-os`, which
syncs on its own.

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

- Non-code session → Steps 3, 3b and 6 only (see Step 0).
- Clean working tree, nothing ahead of upstream → skip 1, 2, 5.
- Pure exploration session with no code changes → 3b, 4 and 6.
- Step 3b is never skipped entirely: the task log line is always proposed.
- User says "just commit and wrap up" → still propose first, but be brief
  about it.
