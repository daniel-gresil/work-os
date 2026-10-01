# Request and audit contract

## Request

`schema_version` is `1`. `operation` is `remove` for live offboarding, `transfer_drive_ownership` for the Google-only Drive ownership transfer described below, or `add`, which is accepted only for a safe plan-time refusal in this release.

`target.email` is the exact human-reviewed address.

Each `platforms` entry uses one disposition:

- `present`: requires the provider immutable ID and `customer_id` (Google) or `tenant_id` (Microsoft).
- `absent`: requires complete API inventory proving no exact recipient; no write is planned.
- `skip`: provider is outside scope.

Google also requires a non-empty, duplicate-free `license_product_ids` list plus literal `license_product_catalog_complete=true`. The operator must reconcile that list against Google's current official catalog and the tenant's ordered products; the packaged example is a starting point, not a timeless completeness claim. `expected_licenses` is always an explicit list and pins every exact product/SKU pair observed at approval time. Microsoft `expected_license_sku_ids` likewise lists every exact assigned SKU ID (or an explicit empty list). A fresh mismatch blocks before license writes.

Removal policy fields are mandatory:

- `mail`, `files`: `delete`, `transfer`, or `retain`;
- `transfer_destination`: exact address when either mode is `transfer`;
- `legal_hold`: `none_known` or `present`;
- `license`: `release_on_delete`, `remove_then_delete`, or `retain`;
- `deletion`: `immediate` or `delayed`;
- `approver`: durable human/change-record identity.
- `accepted_unknowns`: explicit list of live-adapter limitations accepted by that approval; default `[]` blocks rather than silently accepting incomplete dependency coverage.

Unknown or omitted policy is never coerced to a destructive default. `files=transfer` inside a `remove` request and delayed execution remain blocked in the fast-path runner; run `operation=transfer_drive_ownership` as its own approved operation, verify it, and only then plan deletion.

## Inventory completeness

Google inventory resolves the exact Directory user and exact group recipient, then collects groups, delegated roles, configured product license listings, owned non-trashed Drive object count/type, and Gmail profile presence. An alias that resolves to another primary user is a non-user match and blocks deletion.

Microsoft inventory enumerates active users, deleted users, groups, and organizational contacts across UPN, mail, proxy addresses, alternate mail, and sign-in identities. Same-localpart users are audit-only protected false positives.

Any endpoint error sets `complete=false`; an empty failed collection is unknown, not zero.

The live fast-path adapters do not inventory Vault/Purview tenant policy, Gmail delegates/settings, Exchange forwarding/delegates, SharePoint personal sites, Voice numbers, Calendar resources, device assignments, or external automation ownership. Use the main skill checklist and an exception-specific extension when the account role suggests those dependencies. Do not force the generic runner through an exception.

## Plan and approval

The plan hashes material provider inventory and all policy/identity/action fields with canonical JSON. `required_confirmation` is derived from the hash and excluded from its own digest to avoid a circular value.

Approval is a separate artifact containing:

- `decision=approve`;
- exact `approved_by` matching request policy;
- exact `plan_digest`;
- exact literal confirmation.

Changing any bound field invalidates approval. Apply performs a fresh bounded GET-only inventory and compares material hashes before writes.

## Checkpoint states

Per action:

- `about_to_write`: durable marker written before the request; after a crash this is indeterminate and never falls through to a blind retry;
- `write_sent`: response captured, verification pending;
- `verified`: independent read-back passed;
- `verification_failed` or `write_error`: stop; do not resend.

On resume, `verified` actions are rechecked and skipped. Sent/unverified actions are read back first; they are marked recovered only if the desired state is already proven. Otherwise status is `indeterminate_prior_write_not_retried` and human review is required.

## Audit contract

Every report contains schema/record type, UTC timestamps, mode, target, plan digest where applicable, action status, write count, provider evidence, terminal verification, and whether human review is required. Provider bodies are minimized. Credentials, tokens, private keys, and raw mail/file content are forbidden.

## Google post-delete license proof

For every configured `license_product_ids` value, enumerate all assignments with pagination using at most four read workers and deterministic result ordering. Release is verified only when every listing completed and no assignment matches either the exact target email or immutable ID. This is the independent proof when a direct lookup returns provider-specific HTTP 400 after the user disappears.

## Drive ownership transfer (`transfer_drive_ownership`)

Google-only. `platforms.google_workspace` is `present` with the source's `immutable_id` and `customer_id`; `platforms.microsoft_365` must be `skip`. License fields are not required. `target.email` is the exact **suspended** source user. `transfer.destination` pins the exact destination `email` and `immutable_id`, which must differ from the source. `policy.approver` and `policy.accepted_unknowns` are mandatory. Nothing in the request names the Drive application or privacy levels: the engine binds the fixed Data Transfer application ID `55656082996` and `PRIVACY_LEVEL=["SHARED","PRIVATE"]` into every plan.

### Inventory (GET-only)

Directory `users.get` resolves source and destination by exact primary email and reports `suspended`; an alias hit is a non-user match. Drive v3 `files.list` runs as the delegated admin subject with the literal query `'<source-email>' in owners and trashed = false`, paginated to completion, and returns `owned_nontrashed_count`, `total_reported_bytes` (sum of every present `size`), `objects_without_reported_size` (Docs-native files, folders, shortcuts carry no size), `by_type`, and a deterministic `sample` of the first 25 objects by ascending file ID (`id`, `mime_type`, `size`, `parents`; never names or content). Because the listing is the admin's view, the inventory always carries the limitation `google_drive_transfer_inventory_bounded_to_admin_subject_visibility`; the approver accepts it in `accepted_unknowns` or planning stays blocked.

### Plan and approval

Plan/dry-run performs zero writes and blocks on: incomplete inventory, unaccepted limitations, source or destination absent/ambiguous/non-user, email or immutable-ID drift, either user outside the approved `customer_id`, source not suspended, destination suspended, or an unknown Drive count. The single action `google:transfer_drive_ownership` carries `old_owner_user_id`, `new_owner_user_id`, both emails, `customer_id`, `application_id`, and `application_transfer_params`; the plan also embeds `pre_transfer_inventory` (count, bytes, types, sample) and the inventory signature, all under the plan digest. The literal confirmation is `APPLY-DRIVE-TRANSFER:<source>-><destination>:<digest>`, deliberately distinct from `APPLY-OFFBOARD:`. Approval binding rules are the same as offboarding, and `request.transfer` must match the approved plan exactly.

### Apply

1. Fresh GET-only inventory; guard errors or a material signature change refuse before any write.
2. Checkpoint `about_to_submit`, then the only write: `POST https://admin.googleapis.com/admin/datatransfer/v1/transfers` (scope `https://www.googleapis.com/auth/admin.datatransfer`, its own delegated session) with body `{"oldOwnerUserId","newOwnerUserId","applicationDataTransfers":[{"applicationId":"55656082996","applicationTransferParams":[{"key":"PRIVACY_LEVEL","value":["SHARED","PRIVATE"]}]}]}`. The adapter re-asserts both identities, source suspension, destination activity, and that the body equals the approved IDs and fixed constants (exact-ID allowlist) immediately before posting. There are no Drive `permissions` ownership writes anywhere.
3. Checkpoint `submitted` with the provider `transfer_id`; the audit JSON carries it at top level and the CLI echoes `transfer_id=` on stderr.
4. Poll `transfers.get` every `--poll-interval-seconds` (default 30) until `COMPLETED`, `FAILED`, or `--max-wait-seconds` elapses (default 1800, hard ceiling 7200).
5. `COMPLETED` triggers independent verification (below); success checkpoints `verified` and reports `completed_and_verified`.

Outcomes: `transfer_pending` (wait expired; checkpoint keeps `submitted` + id; `resume` block explains the apply/verify paths; no failure is claimed), `transfer_failed` (Google reported FAILED; never resubmitted; human review), `partial_failure` (verification failed or an indeterminate prior submit), `refused` (approval/preflight).

Resume rules: a checkpoint with a recorded `transfer_id` is polled again and never resubmitted. `about_to_submit` or `submit_error` without an id is indeterminate: the runner reads back Drive state and either marks `recovered_by_readback_no_write` or stops with `indeterminate_prior_submit_not_retried`. `verified` reruns are GET-only and report `verified_complete_no_write`. A polled transfer whose owner IDs differ from the approved action is never treated as complete.

Google sends one confirmation email to the new owner, old owner, and admin. Trashed objects are excluded. The source stays suspended; nothing deletes it or touches Gmail, groups, or licenses.

### Verify

`verify --plan plan.json [--checkpoint checkpoint.json]` is GET-only: a fresh admin-subject listing must return zero source-owned non-trashed objects, every sampled pre-transfer file ID from the plan must read back with the destination as sole owner, identity/suspension guards must still hold, and a recorded transfer id (from the checkpoint) must read `COMPLETED`. The Google-created transfer folder is reported only when Drive metadata resolves it deterministically: a folder owned by the destination that appears as a new parent of a sampled file. Otherwise `transfer_folder.resolution=unresolved` with the reason; the Data Transfer API itself does not expose the folder, and the runner never renames or reorganizes anything.

## Rollback limits

Suspension/blocking and license assignment may be reversible before deletion. Session revocation is not. Deletion restore windows and data survival are provider-specific; Google Gmail and Microsoft Exchange/OneDrive restoration are not guaranteed by directory-object restore. Record recovery as a new approved operation and verify it independently.
