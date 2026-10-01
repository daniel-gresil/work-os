---
name: offboard-workspace-user
description: Use when Dan asks to offboard, remove, suspend or delete a Google Workspace or Microsoft 365 user at Lave, or to transfer a departing user's Google Drive files to someone else. Runs a tested script in four stages (inventory, dry run, apply, verify) and stops for Dan's approval of the exact plan before anything is changed.
---

# Offboard a Workspace user

**Autonomy: L2** — acts only after Dan approves the dry-run plan. Deleting an account is irreversible.

The engine in `scripts/` is the Hermes `workspace-user-lifecycle` v1.3.0, unchanged. It enforces the approval in code: `apply` refuses to run unless the approval file carries the digest of the exact plan. Provider quirks, identity guards and policy details are in `references/hermes-skill-v1.3.0.md`; read it before the first live run and whenever something unexpected comes back.

## Rules

1. **You are not the loop.** The script does the work. Never perform a removal step by hand through an API call or admin console, and never write a per-user script.
2. **Stages run in order, and you stop after the dry run.** Show Dan the plan and wait. Only Dan writes the approval; never fill in `approval.json` yourself from an earlier "yes".
3. **Missing input means blocked, not guessed.** If the policy for mail, files, transfer recipient, legal hold or deletion timing is not stated, ask.
4. **One user per run folder.** For several users, confirm the policy once, then run each user through all four stages separately. An unexpected finding for one user reopens the decision for that user only.
5. **Never delete a checkpoint to force a retry.** Rerun the same `apply`; it resumes.
6. Run files hold client data. They stay in `.state/` and are never committed.

## Setup

```bash
cd ~/Developer/GitHub/work-os
source ~/.cache/claude-secrets/work-os/env.sh     # GMAIL_SA_CREDENTIAL, GOOGLE_WORKSPACE_ADMIN_SUBJECT
LC="$HOME/.claude/skills/gmail-draft/run.sh --script $HOME/.claude/skills/offboard-workspace-user/scripts/user_lifecycle.py"
RUN_DIR=.state/offboarding/$(date +%Y%m%d)-<user-localpart> && mkdir -p $RUN_DIR
GOOGLE="--google-credential $GMAIL_SA_CREDENTIAL --google-admin-subject $GOOGLE_WORKSPACE_ADMIN_SUBJECT"
```

Microsoft 365 uses Azure CLI authentication (`az login`); mark it `skip` in the request when the task is Google-only.

## Stages

**1. Request.** Copy `templates/remove-request.example.json` (or `transfer-request.example.json` for a Drive transfer) to `$RUN_DIR/request.json` and fill it from what Dan said: exact email, platforms, and the policy block (mail, files, transfer destination, legal hold, license, deletion timing, approver). Show Dan the policy block.

**2. Inventory** (read-only):

```bash
$LC inventory --request $RUN_DIR/request.json --output $RUN_DIR/inventory.json $GOOGLE
```

Summarise for Dan what the account owns: aliases, groups, roles, licenses, Drive data, anything unknown. An empty result after an API error is unknown, not zero.

**3. Dry run** (no writes):

```bash
$LC dry-run --request $RUN_DIR/request.json --inventory $RUN_DIR/inventory.json --output $RUN_DIR/plan.json
```

Show Dan the ordered list of intended writes, any guard errors, and the plan's `plan_digest` and `required_confirmation`. **Stop here.**

**4. Approval.** Dan approves by stating the confirmation text. Then create `$RUN_DIR/approval.json` from `templates/approval.example.json` with his name, the exact digest and the exact confirmation.

**5. Apply:**

```bash
$LC apply --request $RUN_DIR/request.json --plan $RUN_DIR/plan.json --approval $RUN_DIR/approval.json \
  --checkpoint $RUN_DIR/checkpoint.json --output $RUN_DIR/audit.json $GOOGLE
```

For a Drive transfer add `--poll-interval-seconds 30 --max-wait-seconds 1800`. `transfer_pending` after the wait is not a failure: rerun the same command or go to verify.

**6. Verify** (independent read-back):

```bash
$LC verify --request $RUN_DIR/request.json --output $RUN_DIR/verification.json $GOOGLE
```

For a transfer, also pass `--plan` and `--checkpoint`. Report to Dan per user: final state on each provider, what happened to data and who received it, licenses released, and anything left over.

## Check the tool itself

```bash
cd ~/.claude/skills/offboard-workspace-user && ~/.claude/skills/gmail-draft/.venv/bin/python -m unittest discover -s tests   # offline
```
