---
name: workspace-user-lifecycle
description: "Use when managing Google Workspace or Microsoft 365 users."
version: 1.3.0
author: Scotty
license: MIT
metadata:
  hermes:
    tags: [google-workspace, microsoft-365, admin-sdk, microsoft-graph, identity, offboarding, provisioning]
    related_skills: [google-workspace-account-routing, secrets-management, productivity-data-and-document-apis]
---

# Workspace User Lifecycle

## Operating posture

Use scripts and direct provider APIs for Google Workspace and Microsoft 365 user administration. Do not use browser automation for tenant-user creation, suspension, licensing, or deletion. A human may need Admin Console for domain-wide-delegation grants when no supported administration API exists for that configuration.

Dan expects exact identity resolution, fail-closed destructive actions, independent read-back, and a durable audit trail. Never map cross-platform users by local part alone.

Load this skill at the start of every Workspace/Microsoft user-lifecycle task and reuse its established runner/policy patterns. A pending packaging or improvement card does not make the current skill unavailable. Do not rebuild the lifecycle engine, invoke a coding agent, generate bespoke tests, or auto-decompose routine delete-only identities; add only genuinely new provider operations to the shared implementation.

## Providers and authentication

### Google Workspace

Use Admin SDK Directory, Enterprise License Manager, Drive, Gmail/Vault where policy requires them, and a domain-wide delegated service account impersonating an explicitly selected super-admin. Materialize the delegated key to `GOOGLE_APPLICATION_CREDENTIALS` from the file attachment `op://hermes-crew/google-workspace-lave-service-account/credential` — it carries the `admin.directory.user`, drive, sheets, and script scopes; do NOT use the older `google-sheets-service-account`, which lacks the directory scope and 403s on user deletion. Impersonation subject: `op://hermes-crew/google-workspace-lave-service-account/impersonation subject` (`daniel.souza@laveapparel.com`). Keep credential files mode 0600, request narrow token scopes, and remove temporary files in a trap. See `google-workspace-account-routing` for the exact retrieval command.

### Microsoft 365

Use Microsoft Graph through Azure CLI authentication, a Graph SDK, or a least-privilege app identity. Resolve the tenant ID and exact directory object before writes. Treat an overprivileged delegated token as a reason to constrain code to an explicit method allowlist—not as permission to broaden the task.

## Lifecycle modes

A reusable tool should expose four modes:

1. **Inventory:** GET-only provider discovery and exact identity resolution.
2. **Plan/dry-run:** convert explicit business policy into ordered intended writes.
3. **Apply:** execute only authorized actions after fresh drift checks.
4. **Verify:** independently read back state and prove idempotent reruns.

Produce sanitized machine-readable JSON and concise Markdown evidence. Credentials, access tokens, and raw mailbox content never belong in artifacts.

### Reusable runner

This skill ships one tested remove-user engine instead of generating per-user scripts:

- `scripts/user_lifecycle.py`: inventory, plan/dry-run, apply/resume, and verify CLI;
- `scripts/lifecycle_engine.py`: policy, approval digest, exact-ID action allowlist, checkpoint, and audit engine;
- `scripts/provider_adapters.py`: Google Workspace and Microsoft 365 API adapters;
- `templates/remove-request.example.json` and `templates/approval.example.json`: synthetic inputs;
- `references/request-and-audit-contract.md`: fields, scopes, limitations, checkpoint states, and rollback boundary;
- `tests/`: offline safety fixtures.

Provisioning requests are validated but intentionally plan-only in version 1.1. The proven live paths are offboarding and, since 1.3, the Google Drive ownership transfer operation; adding provider creation writes without a separate pilot would mislabel unproven automation as safe.

From this skill directory, install dependencies and run a safe inventory:

    python3 -m pip install -r scripts/requirements.txt
    python3 scripts/user_lifecycle.py inventory \
      --request request.json --output inventory.json \
      --google-credential "$GOOGLE_APPLICATION_CREDENTIALS" \
      --google-admin-subject "$GOOGLE_WORKSPACE_ADMIN_SUBJECT"

Plan with zero writes, then bind approval to the exact digest and literal confirmation emitted by the plan:

    python3 scripts/user_lifecycle.py dry-run \
      --request request.json --inventory inventory.json --output plan.json
    python3 scripts/user_lifecycle.py apply \
      --request request.json --plan plan.json --approval approval.json \
      --checkpoint checkpoint.json --output audit.json \
      --google-credential "$GOOGLE_APPLICATION_CREDENTIALS" \
      --google-admin-subject "$GOOGLE_WORKSPACE_ADMIN_SUBJECT"

Repeat the same apply command after interruption; never delete the checkpoint to force a retry. Independent final/idempotency verification is:

    python3 scripts/user_lifecycle.py verify \
      --request request.json --output verification.json \
      --google-credential "$GOOGLE_APPLICATION_CREDENTIALS" \
      --google-admin-subject "$GOOGLE_WORKSPACE_ADMIN_SUBJECT"

Platform-specific execution is valid: mark the other provider `skip`. An `absent` provider is still selected and requires its adapter, exact tenant/customer binding, and complete recipient inventory before it becomes a verified no-op.

The example defaults `policy.accepted_unknowns` to `[]`. Live adapter limitations block planning until each is resolved or explicitly accepted by the approver. For Google, reconcile `license_product_ids` against the current official catalog and tenant products, then explicitly set `license_product_catalog_complete=true`; every configured listing must complete. Read-only inventories are bounded across providers and Google license products, while writes remain serialized.

### Drive ownership transfer operation

`operation=transfer_drive_ownership` (see `templates/transfer-request.example.json`) runs through the same four modes with the same digest/approval/checkpoint rules. It is Google-only, moves every non-trashed object owned by an exact suspended source to an exact active destination through the Admin SDK Data Transfer API (application `55656082996`, `PRIVACY_LEVEL=["SHARED","PRIVATE"]`), and never writes Drive permissions, deletes the source, or touches Gmail, groups, or licenses. The confirmation literal is `APPLY-DRIVE-TRANSFER:<source>-><destination>:<digest>`.

    python3 scripts/user_lifecycle.py inventory --request transfer.json --output inventory.json \
      --google-credential "$GOOGLE_APPLICATION_CREDENTIALS" --google-admin-subject "$GOOGLE_WORKSPACE_ADMIN_SUBJECT"
    python3 scripts/user_lifecycle.py dry-run --request transfer.json --inventory inventory.json --output plan.json
    python3 scripts/user_lifecycle.py apply --request transfer.json --plan plan.json --approval approval.json \
      --checkpoint checkpoint.json --output audit.json --poll-interval-seconds 30 --max-wait-seconds 1800 \
      --google-credential "$GOOGLE_APPLICATION_CREDENTIALS" --google-admin-subject "$GOOGLE_WORKSPACE_ADMIN_SUBJECT"
    python3 scripts/user_lifecycle.py verify --request transfer.json --plan plan.json --checkpoint checkpoint.json \
      --output verification.json \
      --google-credential "$GOOGLE_APPLICATION_CREDENTIALS" --google-admin-subject "$GOOGLE_WORKSPACE_ADMIN_SUBJECT"

Apply records the provider transfer id in the checkpoint before polling. `transfer_pending` after the bounded wait is not a failure: re-run the same apply command (it polls the recorded id and never resubmits) or run verify. Verify requires zero remaining source-owned objects and destination ownership of the sampled pre-transfer file IDs, and reports the Google-created transfer folder name only when Drive metadata resolves it; otherwise it says so explicitly. The listing runs as the delegated admin, so the count is bounded to that admin's visibility; the approver accepts `google_drive_transfer_inventory_bounded_to_admin_subject_visibility` in `accepted_unknowns`. Details: `references/request-and-audit-contract.md`.

Verify the package offline:

    python3 -m unittest discover -s tests -v
    python3 -m py_compile scripts/lifecycle_engine.py scripts/provider_adapters.py scripts/user_lifecycle.py

### Routine fast path

For an exact, previously inventoried delete-only account with explicit retain-nothing, bounce, and hold policy, target completion within five minutes:

1. Load and reuse the existing tested inventory/apply/verify tooling; do not generate account-specific frameworks, invoke a coding agent, or create bespoke test suites.
2. Run one bounded parallel read-only preflight across both providers.
3. Stop only for a material new dependency or immutable-identity drift.
4. Execute serialized exact-ID writes and immediate independent read-back.
5. For Google auto-assigned licenses, delete the authorized immutable user and verify license release afterward; do not gate deletion on an unsupported direct license removal.
6. Emit one concise audit record and an idempotent verification result.

Data transfer, Gmail migration, alias handoff, Voice numbers, production automation, and room/device retirement are exception modes and are not subject to the five-minute target because provider/data-volume work may dominate. Even there, reuse the same tooling and add only the exception-specific operation; do not rebuild the lifecycle engine.

### Repeated and batch intake

When Dan supplies several users with the same policy, do not make him answer the full questionnaire for every address. After the first complete policy is established, offer one compact confirmation per new identity: platforms, retain/transfer choice, inbound routing, and hold status. Record that confirmation on the identity's own audit card. Never silently inherit destructive policy across users—unexpected owned data, resources, or integrations still reopen only the affected decision.

Keep each identity in a separate execution/audit unit unless an explicitly reviewed batch tool provides per-user immutable guards and fail-closed continuation. Concurrency is bounded; report queue state honestly and do not let later high-priority cards silently starve an already approved deletion.

## Identity guards

For Google, pin both the primary email and immutable Directory user ID. Mutate and delete by immutable ID after asserting the current primary email still matches.

For Microsoft, search active users, deleted users, UPN, mail, proxy addresses, alternate mail/sign-in identities, groups, organizational contacts, shared/resource mailboxes, and room/device accounts. A same-localpart account on another domain is a protected false positive unless an exact identity field proves the relationship. If no exact object exists, record Microsoft as an explicit no-op.

An email address is not necessarily a user. It may be a proxy on another mailbox, a Google alias, group, shared mailbox, contact, Calendar resource, Teams Rooms identity, or provider-managed derived alias. Mutate the resolved object type only. If an address is merely a Microsoft proxy on another person's mailbox, move only that proxy; never block, unlicense, or delete the mailbox owner.

## Required inventory

Before offboarding, collect:

- account status, immutable ID, tenant/customer ID, and organizational unit;
- aliases and alternate identities;
- groups and directory/admin roles;
- assigned licenses, SKUs, and service plans;
- owned Drive/OneDrive data;
- Gmail/Exchange mailbox existence, send-as identities, forwarding, delegates, filters, OAuth grants, and recipient permissions when relevant;
- app/service ownership, recovery/break-glass use, billing, device, room-booking, automation, ERP/helpdesk, and other integration dependencies suggested by the account's role;
- retention, Vault, Purview, eDiscovery, legal-hold, and applicable business-record policy inputs;
- exact transfer recipients when data must survive, including recipient identity/capacity checks;
- Apps Script project files plus their deployments, installable triggers, OAuth grants, and external credentials as separate dependencies.

An empty result after API errors is **unknown**, not zero. Store completeness flags and per-endpoint errors.

## Policy gate

No destructive action runs until the decision record explicitly states:

- exact target on each provider, or provider-specific absence;
- retain, transfer, or delete choice for mail and files;
- transfer destination where required;
- known legal/retention holds;
- alias/group/role treatment;
- license removal timing;
- immediate versus delayed deletion;
- approver for irreversible data loss.

Every planned write must carry a risk class, authorization, verification method, rollback limit, and drift condition. Missing input means blocked, not guessed.

### Mid-flight policy changes

A newer user instruction supersedes every earlier policy record immediately. When policy changes while a worker may be mutating external state:

1. Freeze the task and terminate the running worker before it can cross the old policy boundary.
2. Record the replacement policy in affirmative, unambiguous terms such as `PRESERVE every Drive object; TRANSFER all objects to <exact recipient>`; avoid relying on a negation that log redaction or truncation could obscure.
3. Read back the exact provider state and report which writes completed, which did not, and whether recovery is needed.
4. Resume from a checkpoint rather than rerunning already-completed provider writes.
5. If the original card moved to triage after the emergency stop and cannot be directly resumed, create one non-decomposing replacement execution card pinned to the original immutable IDs and evidence.

See `references/midflight-policy-change.md` for the emergency-stop and resume checklist.

## Google execution sequence

1. Mint narrowly scoped delegated credentials and run harmless reads for every required scope.
2. Verify backing APIs are enabled in the service account's GCP project.
3. Freshly resolve primary email and immutable ID; compare with the approved plan.
4. Re-run dependency and license inventory; drift voids approval.
5. Suspend the user and independently read back `suspended=true`.
6. Revoke sessions with `users.signOut`. Google returns HTTP 204 but exposes no universal human-session read-back. For Dan's workflow, HTTP 204 plus independently verified `suspended=true` is sufficient provider evidence. Do not use a DWD-impersonated Drive request as an access-denial test: domain-wide delegation can still succeed and says nothing about the user's browser/device sessions.
7. Recheck aliases, groups, roles, OAuth grants, Gmail settings, holds, and Drive ownership.
8. Remove only an exact manually removable license assignment and verify release. If Google rejects removal because the SKU is auto-assigned, do not change tenant-wide auto-assignment and do not keep retrying; when immutable-user deletion is already authorized, proceed to that deletion and verify release afterward.
9. Delete by immutable ID.
10. Verify absence from active directory, expected deleted-user state where supported, and license release through complete assignment listings.
11. Rerun verification mode; already deleted must be a safe no-op.

Deletion and Gmail loss are not reliably reversible. Undelete is best effort and does not guarantee mailbox restoration.

## Microsoft execution sequence

For a verified exact object:

1. Re-resolve object ID and all identity fields.
2. Recheck licenses, groups, roles, Exchange dependencies, OneDrive ownership, and retention policy. Graph `accessDenied` or `resourceLocked` means OneDrive is unknown, not empty—even when the user has no current license or active Exchange mailbox. Prefer an authorized SharePoint/OneDrive or Exchange Online read path; otherwise require an explicit decision to delete despite unknown data.
3. Block sign-in and revoke sessions; read back both actions.
4. Transfer or preserve mailbox and OneDrive data according to policy.
5. Remove only approved licenses/service plans and verify recovery.
6. Delete the exact object ID.
7. Verify deleted-user state and protected false positives remain unchanged.
8. Rerun in idempotency mode.

If no exact object exists, every Microsoft write is forbidden.

## Address handoff and alias conversion

When deleting a mailbox but preserving its address as an alias/proxy on another account, prove the exact target first and avoid a delete-and-wait race:

1. Inventory source and target by immutable ID and confirm the address is not a group, shared/resource mailbox, contact, or proxy on a third account.
2. Complete and verify required data transfer before releasing the address.
3. Suspend/block and revoke sessions on an actual source user.
4. Where provider semantics require it, rename/readdress the source to a unique tombstone identity; verify the desired address is released.
5. Add the alias/proxy to the exact target and independently verify target ownership and routing.
6. Remove only source licenses and delete only the tombstoned source object; verify target and protected third-party mailboxes remain unchanged.

Google-managed derived test-domain aliases may disappear with the source only when they are proven tied to the same immutable user and policy explicitly allows it. On Microsoft, a requested address may already be a lowercase SMTP proxy on another live mailbox; moving that proxy is the entire Microsoft action.

Resolve alias targets independently per provider. A valid Google target does not prove that a Microsoft target exists and never authorizes creating one. When provider states differ, freeze an explicit per-provider outcome such as `Google: move alias to exact target; Microsoft: delete source with no replacement`. Preserve same-localpart identities on other domains as false positives. Do not force symmetric behavior across providers.

## Data and Apps Script transfer

For Drive transfer, use the runner's `transfer_drive_ownership` operation: it enumerates source-owned non-trashed objects, records count and reported bytes, transfers to the exact approved recipient through the Data Transfer API, then verifies recipient ownership and zero remaining source-owned objects before deletion. Unexpected owned data reopens the policy gate even when the initial answer was “retain nothing.” Google shortcuts may not accept the same ownership transfer as ordinary files/folders; when a shortcut is the only non-transferable object, recreate it under the approved recipient with the same target, verify the replacement, and account explicitly for transferred files, transferred folders, recreated shortcuts, and zero remaining source ownership.

For Gmail migration between Workspace users, preflight `gmail.readonly` on the source and `gmail.insert` on the destination. Add `gmail.labels` when custom labels must survive. Label IDs are mailbox-local: map system labels deliberately, recreate custom labels by name, and apply destination label IDs rather than copying source IDs. Migrate raw message content with stable deduplication keys, record per-message failures, and verify destination counts/samples before source deletion; a successful insert response alone is not proof of a complete mailbox migration.

Apps Script projects are Drive files, but transferring the file does not prove that deployments, installable triggers, OAuth grants, execution identities, Cloud projects, or external credentials moved. Preserve project IDs and inventory each dependency separately; report unsupported ownership transitions rather than claiming success.

## Google scope and API preflight

Common scopes for offboarding:

```text
https://www.googleapis.com/auth/admin.directory.user
https://www.googleapis.com/auth/admin.directory.group.readonly
https://www.googleapis.com/auth/admin.directory.rolemanagement.readonly
https://www.googleapis.com/auth/admin.directory.user.security
https://www.googleapis.com/auth/apps.licensing
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/admin.datatransfer
https://www.googleapis.com/auth/gmail.settings.basic
https://www.googleapis.com/auth/gmail.settings.sharing
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.insert
https://www.googleapis.com/auth/gmail.labels
https://www.googleapis.com/auth/ediscovery.readonly
```

`apps.licensing` is read/write; Google exposes no read-only licensing scope. `users.signOut` requires `admin.directory.user.security`. Validate it before any write through a harmless token-list read. An `unauthorized_client` token-exchange failure proves the DWD client lacks the requested scope.

OAuth scope authorization does not enable the backing API. Enterprise License Manager may return HTTP 403 while `licensing.googleapis.com` is disabled; Vault reads similarly require `vault.googleapis.com`. Verify Service Usage state separately, then rerun the real inventory.

Gmail settings list endpoints can legitimately return HTTP 204 with an empty body; treat that as a successful empty collection, not a JSON parser failure. Probe `gmail.settings.basic` and `gmail.settings.sharing` before writes. Use `ediscovery.readonly` for available Vault matter/hold inspection, while documenting that Google does not expose every tenant retention rule through the same API.

Google auto-licensing can reject deletion of an individual assignment with HTTP 400. Do not disable tenant-wide auto-assignment to force it. If policy authorizes user deletion, delete only the exact immutable user and then verify release through complete product/SKU assignment listings and exact-user lookup.

## Post-delete Microsoft data cleanup

Deleting an Entra user and recovering its licenses proves identity offboarding, not immediate OneDrive/SharePoint personal-site purge. Report these as separate states:

- `identity_deleted_verified` — active user absent and deleted-user state handled as authorized;
- `licenses_recovered_verified` — exact SKUs absent and capacity recovered;
- `personal_site_cleanup_pending|purged_verified` — exact OneDrive personal site retained by provider policy or independently removed and verified.

When policy says delete everything without content inspection, skip content enumeration but still resolve the exact personal-site target before deletion. On macOS, prefer cross-platform `PnP.PowerShell` (`Connect-PnPOnline`, `Remove-PnPTenantSite`) over assuming the Windows-oriented SharePoint Online Management Shell exposes `Connect-SPOService`. A tenant-consented Entra client and SharePoint admin-capable principal are prerequisites. Purge both active and deleted-site stages when immediate permanent removal is authorized, then independently prove the exact site is absent; never infer site purge from user deletion alone.

## Per-user completion reporting

When summarizing a batch, produce one clearly labeled section per exact requested email address rather than a general narrative. Each section states Google final state, Microsoft final state, data disposition and recipient, alias/proxy outcome, groups/licenses/OAuth/Voice/resources, verification evidence, and residual limitations. Distinguish account deletion from residual provider-retained data such as a OneDrive personal site. Programmatically compare the section-heading set against the requested-account manifest so every account appears exactly once, then finish with concise totals. Create a draft only unless sending was explicitly requested.

If a blocked, timed-out, or triaged account card is completed through a replacement execution card, repair the fan-in graph immediately: make the final report depend on the verified replacement, and either close the superseded original with the replacement handoff or remove it from the gate. A completed replacement must not leave the final summary waiting forever on an obsolete parent.

## Verification requirements

- A successful write response is not proof of final state.
- Independently read the exact object after each mutation.
- Preserve request timestamps and sanitized identifiers.
- Verify protected false positives are unchanged.
- Treat session revocation as lacking a simple universal state field; use the approved HTTP 204 plus suspended-state evidence standard and do not invent a DWD-based denial test.
- Prove license inventory completeness and license release, including the auto-licensing path where user deletion releases a non-removable assignment.
- Test absent targets, ambiguous identities, partial completion, failed verification, policy omissions, and repeated execution.

See `references/offboarding-pilot-pattern.md` for concrete provider quirks and a proven fail-closed pilot pattern. See `references/role-sensitive-account-checks.md` for extra inventory and policy gates for shared mailboxes, administrative-looking identities, room resources, HR/finance records, operational automation accounts, and alias handoffs. See `references/offboarding-throughput-and-batch-operations.md` for the five-minute routine target, batch intake, anti-rebuild rule, material-exception threshold, and concise audit pattern. See `references/midflight-policy-change.md` for safely stopping and resuming when the user changes transfer/destruction policy during execution. See `references/per-user-completion-report.md` for exact-heading coverage and the per-account final email contract. See `references/cross-provider-alias-and-fanin.md` for asymmetric alias targets and replacement-card dependency repair.
