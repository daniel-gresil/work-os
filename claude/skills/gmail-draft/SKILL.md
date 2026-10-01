---
name: gmail-draft
description: Create or update one Gmail draft in daniel.souza@laveapparel.com and verify it by reading it back; supports reply-in-thread, HTML, inline images and attachments. It cannot send or delete. Use when Dan asks for an email draft, to add something to his drafts, or to email someone or a team, from any repo. For replying to an email he received, use draft-email-reply, which calls this. Do not use a Gmail MCP connector or Apps Script for drafts.
---

# Gmail draft

**Autonomy: L1** — drafts only. This tool has no send or delete operation; never look for another way to send.

Ported from the Hermes `gmail-draft` v1.2.0. `scripts/gmail_draft.py` is unchanged from that version; only the credential helper and wrapper differ.

## Setup

- Auth is the Lave service account with domain-wide delegation, impersonating `daniel.souza@laveapparel.com`, scopes `gmail.compose` and `gmail.readonly`.
- The credential comes from the `work-os` 1Password cache. If a command fails with "credential not cached", run `cd ~/Developer/GitHub/work-os && ~/.claude/op-secrets-load.sh` (one biometric prompt).
- Always call `~/.claude/skills/gmail-draft/run.sh`; it creates the Python venv on first use.

```bash
~/.claude/skills/gmail-draft/run.sh auth-check     # no Gmail write; run when unsure
```

## Create a draft

Write bodies to files in the scratchpad (absolute paths) so shell quoting cannot alter them. Provide both plain text and HTML when practical.

```bash
~/.claude/skills/gmail-draft/run.sh create \
  --to 'Name <person@example.com>' --cc 'copy@example.com' \
  --subject 'Subject' \
  --plain-body-file /abs/body.txt --html-body-file /abs/body.html \
  --inline-image shot=/abs/screenshot.png \
  --attach /abs/file.pdf
```

- `--to`, `--cc`, `--bcc`, `--inline-image`, `--attach` repeat. Recipients are optional; omit them when Dan will add them.
- An inline image is `CID=/abs/path` and must appear exactly once in the HTML as `<img src="cid:CID">`.
- Whole-team Lave emails are bilingual: English, `<hr>`, Spanish.

## Reply inside a thread

Add `--reply-to-query` with a specific Gmail search (sender, subject, date window) and omit `--subject`. The newest match is the message replied to; the draft lands in that thread with the right `In-Reply-To` and `References`.

```bash
~/.claude/skills/gmail-draft/run.sh create \
  --reply-to-query 'from:person@example.com subject:"Quote request" newer_than:30d' \
  --plain-body-file /abs/body.txt --html-body-file /abs/body.html
```

- `To` defaults to the original sender only. For reply-all, pass every `--to` and `--cc` explicitly.
- If nothing matches, fix the query. Do not fall back to a new, non-thread draft without asking Dan.
- Confirm `original_thread_id` in the output is the thread you meant.

## Update a draft

`update --draft-id <id>` with the same options replaces that one draft in place.

## Rules

1. Show Dan the recipients, subject and body before creating a draft addressed to anyone but himself.
2. Call `create` or `update` once. Never retry after a timeout without first checking whether the draft exists: `create` is not idempotent and a retry makes a duplicate.
3. Success means every entry under `checks` in the output is `true`, `DRAFT` is in the labels and `SENT` is not. Report the `draft_id` to Dan.
4. Never print or copy the credential.

## Check the tool itself

```bash
cd ~/.claude/skills/gmail-draft && .venv/bin/python -m unittest -q test_gmail_draft.py   # offline
```
