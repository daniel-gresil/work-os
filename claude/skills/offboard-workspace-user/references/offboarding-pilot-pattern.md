# Offboarding pilot pattern

This reference captures concrete lessons from a scripted Google Workspace/Microsoft 365 sunset pilot. Apply the pattern generically; do not reuse a pilot identity without fresh resolution.

## Proven workflow

1. Inventory Google and Microsoft independently with GET-only code.
2. Resolve exact identities; protect same-localpart false positives.
3. Record retention and transfer policy before writes.
4. Verify every delegated scope through a harmless live read.
5. Verify backing APIs are enabled separately from OAuth delegation.
6. Produce and approve a machine-readable policy gate. For repeated identities, use a compact per-user confirmation rather than silently inheriting another user's destructive policy.
7. Run a dry-run that prints exact ordered writes and resolved object types—not every email address is a user.
8. Re-read for drift, then suspend/revoke, transfer or release addresses/data as authorized, remove the exact license where supported, and delete by immutable ID.
9. Read back after every write and rerun safely after completion.
10. Package scripts, fixtures, and redacted JSON/Markdown evidence.

## Google provider quirks

### DWD scope probes

A DWD client may have Directory-user access but still lack group, role-management, licensing, or user-security delegation. Build credentials separately for the narrow scope used by each probe. An `unauthorized_client` during token exchange is a missing DWD authorization, not proof that the impersonated administrator lacks privileges.

Useful harmless probes include:

- exact user GET;
- group membership list;
- delegated role assignment list;
- license assignment lookup;
- Drive query for files owned by the target;
- user token list for `admin.directory.user.security`.

### Session revocation

`POST /admin/directory/v1/users/{userKey}/signOut` requires:

```text
https://www.googleapis.com/auth/admin.directory.user.security
```

Preflight that scope before suspension. Do not begin tenant writes and discover the missing scope halfway through the sequence.

A successful `users.signOut` returns HTTP 204. Google has no universal session-state read-back. In Dan's workflow, independently verified `suspended=true` plus HTTP 204 is sufficient. A Drive request made by DWD impersonation is not a valid user-session denial probe because delegated administrator access may continue to succeed.

### Gmail settings and Vault

Useful dependency scopes are:

```text
https://www.googleapis.com/auth/gmail.settings.basic
https://www.googleapis.com/auth/gmail.settings.sharing
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/ediscovery.readonly
```

Inventory forwarding, delegates, send-as identities, filters, OAuth grants, and available Vault matter/hold state. Gmail list endpoints may return HTTP 204 with no body for an empty collection; accept that as success. Vault calls require `vault.googleapis.com` to be enabled independently of DWD scope authorization.

### Gmail migration and label preservation

A true mailbox transfer is different from forwarding or alias handoff. Source reads need `gmail.readonly`; destination writes need `gmail.insert`. Add `gmail.labels` when preserving custom labels. Do not copy source label IDs directly because IDs are mailbox-local: map system labels, create missing custom labels by name, then apply the destination IDs. Use deterministic message keys for safe resume, preserve raw MIME, record every failed insert, and verify destination counts/samples before deleting the source.

### Drive transfer edge cases

Count object classes, not just a grand total. Ordinary files and folders can transfer ownership, while a shortcut may need to be recreated under the recipient. A verified transfer report should reconcile source count into transferred files, transferred folders, recreated shortcuts, explicit skips, and zero remaining source-owned non-trashed objects. For Apps Script MIME types, preserve project IDs and separately inventory deployments, triggers, OAuth clients, execution identities, Cloud projects, and external credentials.

### Licensing

Enterprise License Manager requires:

```text
https://www.googleapis.com/auth/apps.licensing
```

The scope is read/write. Record errors and a `complete` flag; an empty assignments array is not evidence of no license when product calls failed.

Scope delegation and API activation are separate. If the API returns a project-level disabled-service error, enable `licensing.googleapis.com` in the credential's GCP project with an authorized operator, verify enabled state, and rerun inventory before approval.

If Google auto-assignment rejects an exact license DELETE with HTTP 400, do not change tenant-wide auto-licensing. Continue only when exact user deletion is authorized, then verify the user is absent and complete product/SKU listings contain zero target assignments.

### Identity and deletion

Use email for human review and immutable Directory ID for execution. Before each write assert both still refer to the same active account. After deletion, do not search by local part or fall back to a nearby account.

## Alias/proxy handoff pattern

For `source@example.com` → alias on `target@example.com`, avoid delete-and-wait. Verify both immutable identities, finish required transfer, tombstone/readdress the source where needed, prove the desired address is released, add it to the target, verify target ownership/routing, then delete only the tombstoned source. On Microsoft, if the desired address is already a proxy on a third mailbox, move only that proxy and keep both mailbox owners active.

For Drive transfer, verify the source-owned object count reaches zero and recipient ownership is visible before deletion. An Apps Script project's Drive ownership does not prove its deployments, triggers, OAuth grants, Cloud project, or credentials transferred.

Room-like addresses require resource-specific inventory: Calendar resources, resource/shared mailboxes, Teams Rooms identities, devices, and future bookings. Deleting a normal user is not a substitute for retiring those objects.

## Microsoft Graph identity resolution

Check active users, deleted users, groups, and organizational contacts across:

- `userPrincipalName`;
- `mail`;
- `proxyAddresses`;
- `otherMails`;
- sign-in identities.

Same-localpart accounts on unrelated domains are false positives. Include them in the audit as protected objects, then prove they remain unchanged. If no exact object exists, Microsoft is a verified no-op and mailbox/OneDrive/license inventory is not applicable to the nonexistent target.

## Fail-closed guards

Block execution when any of these is true:

- identity is ambiguous or immutable ID changed;
- required retention/transfer/legal-hold decision is missing;
- any inventory endpoint failed or returned incomplete data;
- a required scope fails its harmless probe;
- a backing API is disabled;
- aliases, groups, roles, ownership, or licenses drift after approval;
- independent read-back cannot verify a preceding write.

Blocked dry-run reports are useful artifacts: they prove zero writes occurred and identify the exact prerequisite without exposing credentials.

## Evidence fields

Recommended JSON fields:

- generated timestamp and execution mode;
- provider and tenant/customer identifiers;
- target email plus immutable object ID;
- identity-resolution status and protected false positives;
- inventory completeness and per-endpoint errors;
- policy decisions and approver;
- ordered actions with risk/authorization/verification/rollback;
- before/after snapshots stripped of secrets and raw content;
- write count, skipped/no-op actions, and final verification;
- hashes of scripts and reports;
- residual risks.
