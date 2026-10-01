---
name: gmail-draft
description: Use when the user asks to create an email draft in their Gmail, add something to their drafts, email someone or a team, or send an email as daniel.souza@laveapparel.com — from any repo. Also use when tempted to reach for a Gmail MCP connector or clasp/Apps Script MailApp: this Gmail API script is the canonical path (MCP is not wanted; Apps Script has gmail.send but cannot create drafts).
---

# Gmail draft (any repo)

Creates a Gmail draft (default) or sends an email as daniel.souza@laveapparel.com
via the Gmail API. Generic layer — recipient lists are the caller's job (e.g.
9025_WIP's notify-wip-users pulls its UsersList tab, then could hand off here).

## Prerequisites

1. `$CLASP_CLI_CREDS` in the environment — source any repo's op cache:
   ```bash
   source ~/.cache/claude-secrets/<repo>/env.sh
   ```
   (Every Lave repo's `.claude/op-secrets.txt` includes `FILE:CLASP_CLI_CREDS`.)
2. Account-scoped token at `~/.cache/claude-secrets/gmail/token.json`. If
   missing, ask the user to run the one-time consent in their session:
   ```
   ! source ~/.cache/claude-secrets/<repo>/env.sh && python3 ~/.claude/skills/gmail-draft/scripts/authorize_gmail.py
   ```
   Scope is `gmail.compose` only.
3. Python needs `requests` (and `google_auth_oauthlib` for authorize only).
   If the system python lacks them, use/create a scratchpad venv.

## Workflow

1. Write the email body as an HTML file in the scratchpad. Lave team emails
   are bilingual — English section, `<hr>`, Spanish section — when addressed
   to the whole team; single-language is fine for individuals.
2. Show the user subject + body and get a go-ahead before creating anything
   that will be sent to others. A draft to Daniel himself needs no confirmation.
3. Create:
   ```bash
   python3 ~/.claude/skills/gmail-draft/scripts/gmail_draft.py \
     --subject "..." --html /path/body.html \
     [--to a@b.com] [--bcc x@y.com,z@w.com | --bcc-file addrs.txt] [--send]
   ```
   Defaults: draft only, To: = sender. Group emails go in **BCC** (To: stays
   the sender) so addresses aren't exposed to reply-all. `--send` ONLY when
   the user explicitly asked to send without reviewing in Gmail.

## Failure notes

- `token.json missing` → one-time consent (prereq 2).
- Refresh error `invalid_grant` → consent revoked/expired; re-run authorize.
- Drafts/Sent in Gmail are the audit log; no log file is kept.
