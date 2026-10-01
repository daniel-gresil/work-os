# User-level CLAUDE.md (Daniel)

These instructions apply to every Claude Code session, in every project.

## 1Password secrets — session-start prefetch

Daniel's machine has 1Password CLI (`op`) integrated with the desktop app. Biometric prompts work from Bash subshells, but EACH call triggers one and the auth state doesn't propagate between Bash invocations. The standard below batches the biometric to one prompt at session start.

### The convention

Each repo where Claude Code work involves secrets carries a manifest at `.claude/op-secrets.txt` listing every `op://` reference the session may need. At the start of each session, run the user-level loader to fetch all of them at once into a session cache. From that point on, source the cache file in Bash calls that need secrets — no further `op` calls until a new (not-yet-listed) secret is needed.

### Files involved

| Path | Role |
|---|---|
| `<repo>/.claude/op-secrets.txt` | Per-repo manifest. Committed. Contains only `op://` refs (no secret values). |
| `~/.claude/op-secrets-load.sh` | User-level loader script. Reads the manifest, batch-fetches via `op`, writes the cache. |
| `~/.cache/claude-secrets/<repo-name>/env.sh` | Per-repo cache. Mode 600. `export` statements that subsequent Bash calls source. **Never commit.** |
| `~/.cache/claude-secrets/<repo-name>/files/<NAME>` | Per-secret file for FILE: entries (e.g., SSH keys). Mode 600. |

### Manifest format (`.claude/op-secrets.txt`)

```
# One entry per line. Comments and blank lines ignored.
#
# Simple value -> env var:
#   ENV_NAME = op://vault/item/field @ account
#
# Multi-line/binary (SSH keys etc.) -> file on disk; env var = file path:
#   FILE:ENV_NAME = op://vault/item/field @ account

ERPNEXT_STAGING_BASIC_AUTH = op://lave-agent-vault/staging-erpnext-basic-auth/password @ laveapparel.1password.com
FILE:OVH_SSH_KEY_PATH      = op://infra/vps-ed73f998.vps.ovh.us/private key             @ laveapparel.1password.com
```

Account suffix (`@ laveapparel.1password.com`) is required when more than one 1P account is configured on the machine (Daniel has two: `laveapparel.1password.com` work + `my.ent.1password.com` personal). Sign in with `op signin --account laveapparel.1password.com`. (The work account's sign-in address is `laveapparel.1password.com`, not the generic `my.1password.com` alias, which does not resolve.)

### Session-start procedure (do this EARLY, before other secret-touching work)

> **Automated since 2026-09-05:** a global SessionStart hook (`~/.claude/hooks/op-secrets-hook.sh`, wired in `~/.claude/settings.json`) runs step 1 automatically at session startup when a manifest exists, skipping the biometric entirely if the cache is already newer than the manifest. A PreToolUse hook blocks ad-hoc `op read` in manifest repos. Run step 1 manually only if the hook reported a failure or a new secret was added mid-session.

1. If the working directory has `.claude/op-secrets.txt`, run:
   ```bash
   ~/.claude/op-secrets-load.sh
   ```
   This batches biometric to one prompt for all listed secrets (1P's desktop integration caches the unlock for the duration of the run).
2. In every Bash call that needs a secret, source the cache first:
   ```bash
   source ~/.cache/claude-secrets/<repo-name>/env.sh && <command>
   ```
   `<repo-name>` is the basename of the repo root.

If `.claude/op-secrets.txt` doesn't exist yet but the session will need secrets, **create it** with the relevant entries before the first `op read`.

### Mid-session: when you need a new secret not yet in the manifest

When a task surfaces a secret that wasn't in `.claude/op-secrets.txt`:

1. **Append** the entry to `.claude/op-secrets.txt` (so future sessions get it on first run).
2. **Re-run** the loader: `~/.claude/op-secrets-load.sh`. This refreshes the cache and adds the new value. The biometric may fire once.
3. **Re-source** the cache in subsequent Bash calls.

The manifest is the source of truth. If a secret was useful enough to fetch, it's useful enough to add — don't fetch ad-hoc and forget to record it.

### Security notes

- The cache directory is mode 700, files mode 600 — accessible only to Daniel's UID.
- The cache is never committed (`.cache/` is global gitignore; the per-repo manifest only stores `op://` references, not values).
- Don't `echo` or `cat` secret values in chat output. When verifying that a secret loaded, check `[ -n "$VAR" ]` or report the length, not the value.
- Service accounts (`OP_SERVICE_ACCOUNT_TOKEN`) are an alternative but unused — Daniel prefers keeping biometric in the loop.

### When to skip

- One-off scripts that don't need persistent secrets (`op read` directly is fine).
- Sessions that won't touch any secret at all (don't run the loader pointlessly).
- Repos that aren't using the manifest pattern yet (no harm — just `op read` ad-hoc and offer to create the manifest if the pattern fits).
