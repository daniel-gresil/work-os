---
name: send-alert
description: Send an email alert via Resend. Use when a Postgres health check finds P0 or P1 issues that need human attention, or when an unexpected critical error occurs between scheduled runs. Do not use for routine status reports or P2 items — those go to the log file only.
---

# send-alert

Sends a transactional email via Resend to the on-call address.

## When to send

- **P0** (immediate action): out-of-memory, disk >90%, replication broken, FATAL/PANIC in logs, failed backup, security event (unexpected superuser login, pg_hba changed, brute-force auth attempts).
- **P1** (action this week): disk >80% trending up, autovacuum lagging on a large table, slow query regression, cert/version EOL approaching.
- **Do not send** for P2 items, clean health checks, or routine status. Those go to the daily log only.

If a single run produces multiple findings, send ONE email summarizing all of them — never one email per finding.

## Usage

```bash
op run --env-file="$HOME/.claude/skills/send-alert/.env" -- \
  "$HOME/.claude/skills/send-alert/.venv/bin/python3" \
  "$HOME/.claude/skills/send-alert/send_alert.py" \
    --priority P0 \
    --subject "Postgres: disk at 92% on db01" \
    --body-file /tmp/alert-body.md
```

Body file should be Markdown. The script renders it to HTML and sends both parts (multipart text + HTML).

## Configuration

| Setting | Value | Where |
|---|---|---|
| Sender | `Postgres Agent <postgres-alerts@notify.laveapparel.com>` | Hardcoded in `send_alert.py` (`SENDER`) |
| Recipient | `daniel.souza@laveapparel.com` | Hardcoded in `send_alert.py` (`RECIPIENT`) |
| API key | resolved from 1Password | `op://infra/resend/credential` (referenced by `.env` in this directory) |

The Resend domain `notify.laveapparel.com` must be verified in the Resend dashboard before sends will succeed. Without verification, the API returns 403.

The API key is injected at run time by `op run --env-file=.env --` so it's never written to disk on the calling host.

## Dependencies

The script uses Python 3 stdlib for HTTP (`urllib.request`) and the `markdown` package for Markdown→HTML rendering. The skill ships its own venv at `.venv/` so it doesn't pollute system Python or fight PEP 668 on Homebrew/Debian.

To recreate the venv on a fresh host (the OVH VPS, a new laptop, etc.):

```bash
python3 -m venv "$HOME/.claude/skills/send-alert/.venv"
"$HOME/.claude/skills/send-alert/.venv/bin/pip" install --upgrade pip markdown
```

If the `markdown` package can't be loaded for any reason, the script falls back to sending plain-text only (still works, just no rendered HTML).

## Files

- `SKILL.md` — this file.
- `send_alert.py` — the sender script.
- `.env` — declares `RESEND_API_KEY=op://infra/resend/credential` for `op run` to resolve.
- `.venv/` — dedicated virtualenv with the `markdown` package. Not committed to git; recreate with the command above.
