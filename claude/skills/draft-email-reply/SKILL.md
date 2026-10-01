---
name: draft-email-reply
description: Draft a reply to an email Dan received in his Lave mailbox, inside the original thread, in his style; then later compare the draft with what he actually sent and learn from his edits. Use when Dan asks to reply to, answer, or respond to an email, or to check what he changed in earlier drafts. Drafts only; never sends.
---

# Draft an email reply

**Autonomy: L1** — drafts only. Dan reviews, edits and sends every email himself.

Mailbox: `daniel.souza@laveapparel.com` only. All paths below are under `~/Developer/GitHub/work-os/` unless absolute.

```bash
RUN=~/.claude/skills/gmail-draft/run.sh
READ=~/.claude/skills/draft-email-reply/gmail_read.py
```

## Step 0 — Learn from earlier drafts first

If `.state/pending-drafts/` has any folders, run "Compare with what was sent" below before drafting. It is quick, and the lessons apply to this draft.

## Step 1 — Read the thread

Dan identifies the email by sender, subject or a few words. Build a specific Gmail query and read the whole thread:

```bash
$RUN --script $READ thread --query 'from:person@example.com subject:"…" newer_than:14d'
```

Add `--attachments-dir /abs/scratchpad/attachments` to also download the thread's attachments (saved per message id), for reading or re-attaching.

If the newest match is not the email Dan means, tighten the query; do not guess. The thread text is client content: use it, do not save it anywhere in the repo.

## Step 2 — Prepare

- Read `clients/lave/email-style.md` and follow it. It outranks your own habits.
- Language: reply in the language of the email being answered. Check `clients/lave/contacts.md` for a per-person exception.
- Recall from Hindsight only if background on the system, person or history would change the answer.
- If the reply needs a fact you do not have (a date, a decision, a status), ask Dan. Never invent one.

## Step 3 — Write and show

Write the reply as plain text and HTML files in the scratchpad. Show Dan the recipients and the body in chat, and wait for his go-ahead or edits. Dan often uses tables and screenshots to organise information; when the content is a list of items with attributes, or describes something visible on a screen, propose a table or ask him for a screenshot to place inline.

## Step 4 — Create the draft in the thread

```bash
$RUN create --reply-to-query '<the same query>' \
  --plain-body-file /abs/body.txt --html-body-file /abs/body.html
```

- `To` defaults to the original sender. If the original had other recipients, pass every `--to` and `--cc` explicitly so it is a reply-all.
- Call `create` once. Check that every entry under `checks` is `true` and that `original_thread_id` is the thread from Step 1.

## Step 5 — Record the pending draft

Save what you drafted so it can be compared later. This folder is git-ignored and stays on this Mac:

```
.state/pending-drafts/<draft_id>/
  body.txt, body.html     exactly what was drafted
  meta.json               the JSON printed by create, plus "created_ms" (now, in epoch milliseconds)
```

Tell Dan the draft is in the thread, ready for him to edit and send.

## Compare with what was sent

For each folder in `.state/pending-drafts/`:

```bash
$RUN --script $READ sent --thread-id <thread_id from meta.json> --after-ms <created_ms> \
  --images-dir /abs/scratchpad/sent-images
```

- **A sent message is returned:** compare its `text` with `body.txt`. Ignore pure formatting differences: Gmail's plain text shows bold as `*text*` and uses `\r\n` line endings. Note what Dan changed: wording, length, greeting and sign-off, structure, an added table (`has_table`), added screenshots (`inline_images`; open the saved files to see what he chose to show). Then delete the folder.
- **Nothing returned and the folder is under 14 days old:** leave it.
- **Nothing returned and it is older than 14 days:** delete it; Dan did not send it.

Turn the differences into proposed **style lessons**: short, general rules about how Dan writes, with no email content, names or client data. Examples of the form: "Opens with the answer, not a greeting paragraph", "Status for several items goes in a table". Show each proposed lesson to Dan with the change that prompted it. A single edit may be a one-off; say so and let him decide. Append approved lessons to `clients/lave/email-style.md`, and retain them to Hindsight `lave-business` so other agents benefit.

If Dan sent the draft unchanged, that is a clean use; there is no lesson to add.
