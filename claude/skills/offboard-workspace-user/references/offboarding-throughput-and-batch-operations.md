# Offboarding throughput and batch operations

## Why this reference exists

The first identity in a new tenant deserves a careful pilot. Repeating pilot-level engineering for every later identity is an anti-pattern. In the September 2026 Lave pilot, per-account code generation, coding-agent runs, bespoke tests, repeated decomposition, and redundant policy gates stretched routine deletion work into hours. The safety controls were useful; rebuilding them per user was not.

## Service target

For an exact delete-only identity with recorded policy, working credentials, and no newly discovered material dependency, target completion in five minutes. The target includes fresh identity/dependency reads, exact-ID deletion, license-release verification, and a concise audit record.

Do not promise five minutes for provider-bound data movement:

- Gmail message migration;
- thousands of Drive/OneDrive objects;
- Apps Script deployment/trigger/execution-identity migration;
- alias handoffs waiting on address release;
- Google Voice number release;
- room/device retirement.

## Reuse rule

Load `workspace-user-lifecycle` at intake. Reuse one tested runner and policy-manifest schema. Do not invoke a coding agent, create a new framework, generate a bespoke test suite, or decompose a routine identity into inventory/plan/reconcile/apply subcards. Extend the common runner only when a genuinely new provider operation is required, then test that operation once and feed the improvement back into the shared skill.

A pending card to improve or package the runner does not mean this procedural skill is unavailable. Follow the current skill immediately and let packaging improve the implementation separately.

## Kanban orchestration controls

Routine account cards should use `goal_mode=false` and stay as one execution/audit unit. Do not let a retry or block-loop send a simple deletion to triage and fan it into inventory/reconcile/apply subgraphs. If the board has global auto-decomposition enabled, disable it for a focused cleanup batch or create non-decomposing replacement execution cards from already-verified evidence. Raising worker concurrency trades higher model/API usage and provider rate-limit pressure for throughput; use bounded concurrency and serialize mutations that share a provider or address namespace.

When a long transfer worker exhausts its iteration budget after durable progress, resume from its checkpoint in one non-decomposing completion card. Never restart Gmail/Drive migration or repeat completed provider writes merely because the orchestration run ended.

## Three execution modes

1. `delete`: retain nothing; suspend/block, sign out, delete exact immutable identities, verify deleted state and license recovery.
2. `transfer-delete`: transfer named data to an exact recipient, verify zero remaining ownership, then delete.
3. `alias-handoff`: verify the recipient, release or tombstone the source address, attach it to the recipient, verify routing, then delete the source.

Room/device, Voice, and production-automation cases are exception extensions, not separate lifecycle engines.

## Batch intake

For several identities with the same business policy:

1. Capture the common policy once.
2. Ask one compact confirmation per identity rather than repeating a long questionnaire.
3. Run provider inventories in bounded parallel.
4. Produce one exception list containing only new material dependencies.
5. Resolve exceptions one at a time.
6. Serialize mutating operations per provider and address namespace.
7. Keep immutable guards and audit results per identity so one failure does not broaden or corrupt the batch.

## Material exception threshold

Stop only when fresh evidence changes the approved risk:

- unexpected owned data;
- additional aliases, forwarding, delegates, or shared-resource semantics;
- group/admin roles not covered by policy;
- OAuth, automation, billing, recovery, Voice, device, or room dependencies;
- legal/retention holds;
- inaccessible OneDrive/mailbox state when policy did not already accept that unknown;
- immutable-ID or target-address drift.

Do not reopen decisions already answered explicitly. Broad phrases such as “delete and abandon all” may authorize named discovered dependencies only when the user has seen their material scope; record the concrete expansion on the card.

## Provider lessons

- Google auto-assigned licenses may reject direct assignment deletion. Do not modify tenant-wide auto-assignment. Delete the authorized immutable user and verify assignment absence afterward.
- `users.signOut` HTTP 204 plus independently verified suspension is the approved evidence; a DWD Drive request is not a human-session test.
- Gmail settings list endpoints may return HTTP 204 for a valid empty collection.
- Microsoft user deletion and OneDrive personal-site purge are separate lifecycles. Report them separately; do not claim site purge from Entra deletion. A retain-nothing decision authorizes destruction but does not grant SharePoint permissions: if the exact residual site must be purged, use a SharePoint Administrator or least-required Graph/SharePoint site-deletion identity, target only the deterministic personal site, and verify site absence.
- An SMTP proxy on another mailbox is not a user. Move only the proxy and protect the mailbox owner.

## Audit output

One concise result per identity is enough:

- immutable IDs and exact addresses;
- approved mode and exceptions;
- writes attempted and provider results;
- independent final reads;
- license recovery;
- remaining provider-retention state or unresolved risk.

Do not flood the board with implementation narration or create redundant artifacts when the shared runner already emits the evidence.

For a multi-account cleanup, create one final summary-email task gated on the terminal cleanup task for every identity—not on stale parent cards. Draft only after all dependencies finish. The draft should distinguish completed, partial, no-op, and residual states per account; include transfers, aliases, groups, licenses, OAuth/Voice/room cleanup, and provider-specific leftovers; read the draft back and verify per-account coverage before claiming completion. Never send unless separately authorized.
