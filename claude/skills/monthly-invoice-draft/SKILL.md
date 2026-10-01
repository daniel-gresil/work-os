---
name: monthly-invoice-draft
description: Create the Gmail draft of Dan's monthly invoice to Lave Apparel for the calendar month just ended - counts the weekdays, computes hours and amount, writes the body with the remittance block from 1Password, and verifies the draft. Use when Dan says "create the invoice", "monthly invoice", "invoice for <month>", or "send Lave the invoice". Drafts only; never sends.
---

# Monthly invoice draft

**Autonomy: L1** — drafts only. Dan reviews and sends it himself.

Ported from the Hermes `monthly-invoice-draft` v0.1.1 (Janice profile). Hermes no longer owns this task; Dan runs it here by hand, usually on the 1st.

## The rule

- **Period:** the calendar month before today, in `America/Los_Angeles`.
- **Amount:** Monday–Friday days in that month (holidays are not subtracted) × 3 hours × USD 35.
- **From:** Daniel de Souza, `daniel.souza@laveapparel.com`. **To:** Tatiana Braun. **CC:** Ody Demetriadi.
- **Subject:** `Invoice for <Month> / <Year>`.
- **Body:** greeting to Tati, one line with the month and amount, the remittance block, "Thank you, Daniel". Plain text.
- **Remittance block:** 1Password Secure Note `invoice-remittance-details` (vault `hermes-crew`), cached by the work-os manifest as `INVOICE_REMITTANCE`. It never goes into the repo, memory, Hindsight, or the chat.

## Run

```bash
R=~/.claude/skills/gmail-draft/run.sh; S=~/.claude/skills/monthly-invoice-draft/monthly_invoice_draft.py
$R --script $S preview    # the numbers only; no credentials, no Gmail
$R --script $S check      # Gmail auth and remittance cache; no write
$R --script $S create     # one draft, read back and verified
```

1. Run `preview` and show Dan the month, weekdays, hours and amount.
2. Run `create`. It is safe to rerun: an invoice already in Sent means no write, and an existing draft with the same subject is verified and reused instead of duplicated.
3. Success is `status: ok`, every entry under `checks` true, `remittance_block_present` true, `DRAFT` in the labels and `SENT` not. Report the period, amount and `draft_id`.

`--today YYYY-MM-DD` overrides the date, for a late invoice or a test.

## Rules

1. `status: blocked` is a hard stop. Report the error; never build the draft another way.
2. "remittance block not cached" or "credential not cached": run `cd ~/Developer/GitHub/work-os && ~/.claude/op-secrets-load.sh`, then retry.
3. Two drafts with the same subject, or a draft whose remittance text differs: stop and tell Dan. Never overwrite a draft he may have edited.
4. After a timeout on `create`, rerun `create` (it checks before writing); do not call `gmail-draft` directly.
5. Never print the remittance block or the draft body.

## Check the tool itself

```bash
~/.claude/skills/gmail-draft/.venv/bin/python ~/.claude/skills/monthly-invoice-draft/test_monthly_invoice_draft.py   # offline
```
