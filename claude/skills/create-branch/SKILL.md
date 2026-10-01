---
name: create-branch
description: Create a new git branch the standard way — fast-forward the source branch from remote, name it YYYYMMDD_short_description, optionally put it in a .claude/worktrees/ worktree and move the session there. Use when the user says "create a branch", "new branch", "branch off <x>", "start a branch for <y>", or "start a worktree for <y>". Works from any repo.
---

# Create branch

Ask, don't guess, for anything not stated. Then run the steps in order.

## 1. Gather inputs (one AskUserQuestion, skip anything already given)

- **Source branch** — never assume; `main` and `development` both exist in most repos.
- **Short description** — becomes `YYYYMMDD_short_description` (today's date, snake_case). If the
  working tree has uncommitted work, offer a name inferred from it as the default.
- **Worktree?** — "Move this session into a worktree at `.claude/worktrees/<branch>`?" (yes/no).
  Recommend **yes**: the main checkout stays on `main`, which the user relies on.
- **Uncommitted changes?** — only if `git status --porcelain` is non-empty: list the files and ask
  "Move these changes to the new branch, or leave them here?" Default: **leave**.

## 2. Update the source from remote — always, whatever the source

    git fetch origin --prune
    git branch -f <src> origin/<src>      # if <src> is checked out here: git pull --ff-only instead

## 3. Create

**Worktree = yes** (run from the main checkout, which stays on `main`):

    git worktree add .claude/worktrees/<branch> -b <branch> <src>

then `EnterWorktree` with `path: <abs path to .claude/worktrees/<branch>>`. Verify with `pwd` and
`git status -sb`; the tip SHA must equal `origin/<src>`.

**Worktree = no**:

    git checkout -b <branch> <src>

## 4. Uncommitted work in the main checkout

Leave it where it is unless the user answered "move" in step 1. The worktree starts as exactly
the branch tip, nothing else. If they chose move:
`git stash push -u -m "<tag>"` in the main checkout → `git stash apply <sha>` in the worktree →
drop the stash entry. Never bare `git stash pop` (the stash stack is shared across worktrees).
Worktree = no and move: nothing to do — `git checkout -b` carries the changes along.

## Renaming later

    git branch -m <old> <new>
    git worktree move .claude/worktrees/<old> .claude/worktrees/<new>
    ExitWorktree(keep) → EnterWorktree(path: <new>)   # the session tracker pins the old path

## Hard rules

- The main checkout (`/…/<repo>`) stays on `main`. Never `git checkout <branch>` there when a
  worktree was requested.
- Never `git -C <main checkout> …` from inside a worktree session — the harness refuses it.
- Never bare `git stash` / `git stash pop`.
- Never mention this tooling in tracked files, commits, or PRs.
