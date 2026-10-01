---
name: lave-repo-guardrails
description: >-
  Apply Lave Apparel's standard repo protection + clasp wiring + live-vs-GitHub
  drift detection to a GitHub repo that mirrors a Google Apps Script project. Use
  WHENEVER setting up, hardening, or "configuring guardrails" on a Lave GAS repo:
  branch protection, granting the lave-team, .clasp.json/.claspignore/executionApi +
  clasp run enablement, and the hourly drift monitor that alerts Teams when the live
  Apps Script diverges from GitHub. Handles both container-bound (Sheet) and
  standalone/add-on scripts. Trigger phrases: "set up lave-repo-guardrails on this
  repo", "config this repo with the Lave guardrails", "protect this GAS repo",
  "add drift detection to this repo".
---

# Lave repo guardrails

Reproducibly configures a GitHub repo that mirrors a Google Apps Script (GAS) project with
Lave's standard governance + `clasp` wiring + live⟷GitHub drift detection. Read
`reference/architecture.md` for the "why" behind every step before changing anything — the
non-obvious steps encode fixes that break silently if reverted.

## When to use
The user says something like "set up lave-repo-guardrails / the Lave guardrails on this repo",
"protect this GAS repo", or "add drift detection". Works for a brand-new mirror repo or to
harden an existing one (all steps are idempotent).

## Constants (do not ask the user for these)
- Org `Lave-Apparel`; dev team `lave-team` (granted `push`).
- Read-only drift SA `wip-sync-tool@sodium-diode-177520.iam.gserviceaccount.com`; GCP project
  `sodium-diode-177520` (#`833364097545`), Apps Script API already enabled.
- Secrets sourced from 1Password (refs in `templates/op-secrets.txt`).

## Per-repo inputs to collect
- **Repo slug** — `gh repo view --json nameWithOwner` in cwd, or ask.
- **scriptId** — read `.clasp.json`; if absent, ask (it's in the Apps Script editor URL).
- **Script type + share target** — *derived*, don't ask: `share_script_with_sa.py` calls
  `projects.get` and branches on `parentId` (present → bound, share that Sheet; absent →
  standalone/add-on, share the script's own Drive file).

`SKILL="$HOME/.claude/skills/lave-repo-guardrails"` in the snippets below.

---

## Phase 0 — Preconditions & secrets
1. `gh auth status` — must be an org admin/owner of `Lave-Apparel`.
2. `clasp --version` present; and (for `clasp run`) logged in as the script **owner** via
   `clasp login --creds $CLASP_CLI_CREDS`. Usually already done machine-level.
3. Load shared secrets into this repo's op cache. If the repo has no `.claude/op-secrets.txt`,
   copy the template first:
   ```bash
   mkdir -p .claude && cp "$SKILL/templates/op-secrets.txt" .claude/op-secrets.txt
   ~/.claude/op-secrets-load.sh                       # one biometric prompt
   source ~/.cache/claude-secrets/$(basename "$PWD")/env.sh
   ```
   Confirm (never echo values): `[ -n "$GCP_WIP_SYNC_SA" ] && [ -n "$LAVE_DRIFT_TEAMS_WEBHOOK" ] && echo secrets-ok`.
   - **One-time:** if `op read op://infra/lave-drift-teams-webhook/url` fails, the Teams webhook
     isn't in 1Password yet — create that item once (Power Automate Workflows URL), then re-run.

## Phase 1 — Governance (layer A)
```bash
"$SKILL/scripts/apply_protection.sh" Lave-Apparel/<REPO>
gh api -X PUT "orgs/Lave-Apparel/teams/lave-team/repos/Lave-Apparel/<REPO>" -f permission=push
gh api "orgs/Lave-Apparel/members?role=admin" --jq '.[].login'   # report the bypass set
```
Report the current org owners to the user (they bypass protection). **Never** change org
membership. `apply_protection.sh` reads the policy back and asserts it — must print
`OK: branch protection matches canonical policy`.

## Phase 2 — Hygiene + clasp wiring (layer B)
1. `.clasp.json` = `{"scriptId":"<id>"}` — **no `rootDir`**.
2. `.claspignore` (allowlist) then verify:
   ```bash
   cp "$SKILL/templates/claspignore" .claspignore
   clasp status   # must list every *.js/*.html/appsscript.json; must NOT list .github/ .claude/ *.md
   ```
3. Merge the hygiene block into `.gitignore` (skip lines already present):
   ```bash
   cat "$SKILL/templates/gitignore-block.txt" >> .gitignore
   ```
4. **`clasp run` enablement** (only when the script is owned by the logged-in clasp account —
   see the cross-owner note below):
   - Ensure `appsscript.json` has `"executionApi": { "access": "MYSELF" }`.
   - **Guided:** bind the script to the standard GCP project — Apps Script editor → Project
     Settings (⚙️) → Google Cloud Platform (GCP) Project → Change project → `833364097545`.
     Pause until the user confirms.
   - Smoke test: `clasp run <trivial fn>` returns without "Script function not found".
   - **Cross-owner:** if the script is owned by another account/domain, `clasp run` won't execute
     as the current user — skip it (push/pull still work). See `reference/architecture.md`.

## Phase 3 — Drift detection (layer C)
1. **Seed live source first** (fresh mirror repos): if the repo has no `*.js`/`*.html`/
   `appsscript.json` (e.g. only a README), pull the live source and commit it, or the first check
   flags everything as drift:
   ```bash
   clasp pull        # writes live source into the repo (rootDir = ".")
   ```
2. Install the workflow + scripts and set the scriptId:
   ```bash
   mkdir -p .github/workflows .github/scripts
   cp "$SKILL/templates/live-drift-check.yml" .github/workflows/live-drift-check.yml
   cp "$SKILL/templates/fetch_live.py" "$SKILL/templates/check_drift.py" "$SKILL/templates/materialize_live.py" .github/scripts/
   # set env.SCRIPT_ID in the workflow to this repo's scriptId:
   sed -i '' 's|SCRIPT_ID: ".*"|SCRIPT_ID: "<scriptId>"|' .github/workflows/live-drift-check.yml
   ```
3. Share the script with the SA (auto-detects bound vs standalone) and verify:
   ```bash
   python3 "$SKILL/scripts/share_script_with_sa.py" <scriptId>
   ```
4. Populate the two repo secrets from 1Password:
   ```bash
   "$SKILL/scripts/set_secrets.sh" Lave-Apparel/<REPO>
   ```
5. Commit `.github/` + clasp files. `main` is protected (PR required); if you are an org owner you
   may commit directly (admins are exempt), otherwise open a PR and merge.

## Phase 4 — Test & verify
```bash
gh workflow run "Live vs GitHub drift check" --repo Lave-Apparel/<REPO>
# then confirm the run succeeded and did not false-positive when live == repo:
gh run list --repo Lave-Apparel/<REPO> --workflow "Live vs GitHub drift check" --limit 1
python3 "$SKILL/scripts/verify_setup.py" Lave-Apparel/<REPO> <scriptId> .
```
`verify_setup.py` must print `PASS: all lave-repo-guardrails checks green`. Report the summary +
the current org-owner bypass set + detection latency (≤ hourly).

## Notes
- Everything is idempotent — safe to re-run on an already-configured repo.
- Bound vs standalone is auto-handled; the only real per-repo variable is the scriptId.
- If `clasp run` is not applicable (foreign-owned script), say so explicitly in the summary.
