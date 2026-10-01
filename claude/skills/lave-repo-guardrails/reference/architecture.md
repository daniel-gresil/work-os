# lave-repo-guardrails — architecture & the "why"

Read this before "improving" anything. Several steps look redundant but encode hard-won
fixes; reverting them silently breaks monitoring or `clasp`.

## The three layers
- **A — GitHub governance:** branch protection (PR required, 0 approvals, force-push/deletions
  blocked, admins exempt) + `lave-team` push. Org owners always bypass; report them, don't fight it.
- **B — clasp wiring:** `.clasp.json` (no `rootDir`), `.claspignore` (allowlist), `.gitignore`
  hygiene, and `clasp run` enablement (`executionApi: MYSELF` + GCP-project binding).
- **C — drift detection:** hourly GitHub Action reads live source read-only and alerts Teams when
  live ≠ repo.

## Baked-in facts (do not revert)

1. **CI-auth landmine.** `fetch_live.py` mints the Google token from the SA key via the standard
   JWT flow (`google-auth`), scope `script.projects.readonly`. Do **NOT** switch to
   `google-github-actions/auth` with `token_format: access_token` — that calls the IAM Credentials
   API and needs the "Service Account Token Creator" role the SA lacks, so it fails. No auth action,
   no `token_format`.

2. **`.claspignore` is an allowlist.** Once present, clasp pushes **only** the negated allowlist
   (`!appsscript.json`, `!*.js`, `!*.html`). Always re-run `clasp status` after writing it — it must
   still list every `*.js`/`*.html`/`appsscript.json` and must NOT list `.github/`, `.claude/`,
   `*.md`. This keeps CI files out of the live project.

3. **Bound-script access = share the container Sheet.** You cannot share a bound Apps Script
   project directly; you share its **container Drive file (the Sheet)** with the SA as reader, which
   grants read on the bound script. For a **standalone/add-on** script the project *is itself* a
   Drive file — share it by its own id (`fileId == scriptId`). `share_script_with_sa.py`
   auto-detects which via `projects.get.parentId` (present → bound; absent → standalone) and
   verifies with the SA (bound: `projects.get` 200 + parentId match; standalone: `getContent` 200).

4. **Anti-spam state.** The drift signature is persisted between runs via `actions/cache`
   (`prev-sig.txt`); Teams is posted only when the signature changes (`NOTIFY=true`), not every
   hourly run. `concurrency: group live-drift-check, cancel-in-progress: false`.

5. **Org owners bypass protection.** Repo settings can't stop an org owner. `verify_setup.py` lists
   current org owners each run so the bypass set is a fresh fact, not a stale assumption (membership
   drifts). Never modify org membership automatically.

6. **Teams webhook is Power Automate "Workflows"** → the payload is an Adaptive Card (v1.4) wrapped
   in `{type:message, attachments:[{contentType:"application/vnd.microsoft.card.adaptive", …}]}`
   (built by `check_drift.py`). Success = HTTP 200/201/202 (Power Automate returns 202).

## `clasp run` requires owner login
`clasp run` (`executionApi.access: MYSELF`) executes as the **logged-in clasp account**, which must
be the script **owner**. It also needs the script bound to the standard GCP project
`sodium-diode-177520` (#833364097545) — an Apps Script editor setting (Project Settings → GCP), not
something clasp/REST can flip. If a repo's script is owned by a **different account/domain**
(e.g. an add-on owned by `admin@vintageindustries.mx`), `clasp run` won't execute as
`daniel.souza@laveapparel.com` — push/pull still work; skip `clasp run` or log in as the owner.

## Constants (shared Lave infrastructure)
- Org `Lave-Apparel`; dev team `lave-team` (push).
- Read-only drift SA `wip-sync-tool@sodium-diode-177520.iam.gserviceaccount.com`; GCP project
  `sodium-diode-177520` (#833364097545); Apps Script API already enabled there.
- Secrets from 1Password → each repo's `GCP_SA_KEY` + `TEAMS_WEBHOOK_URL` GitHub secrets.
