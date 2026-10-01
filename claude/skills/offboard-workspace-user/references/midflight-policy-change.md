# Mid-flight offboarding policy changes

Use this checklist when a user changes retain, destroy, transfer, alias, or provider scope after execution has started.

## Immediate stop

1. Append the replacement policy to the account's audit card.
2. Move the card out of running state and terminate the worker process if it is still alive. A card-state update alone is not proof that external writes stopped.
3. Use affirmative wording: `PRESERVE every object`, `TRANSFER all objects to <exact identity>`, or `DESTROY the enumerated objects`. Include immutable source ID and exact recipient.
4. Never let an earlier broad phrase such as “delete all” outrank a newer specific transfer instruction.

## State reconciliation

Read each provider independently and record:

- user active/suspended/deleted state;
- completed group, license, OAuth, alias, and session actions;
- source-owned data count and recipient-owned count;
- whether any object was deleted before the stop and its recoverability;
- protected false positives and already-completed provider actions that must not repeat.

If one provider completed before the policy change, preserve that verified result and resume only the incomplete provider lane.

## Safe resume

- Reuse the original workspace, evidence, and checkpoints.
- Transfer data before deleting the source.
- Verify recipient identity/capacity, recipient ownership, and zero remaining source ownership.
- Resume cleanup and immutable-user deletion only after transfer verification.
- Use a single replacement execution card with `goal_mode=false` when the original card was escalated to triage and cannot be directly resumed; link back to the original card in its body and forbid decomposition/bespoke tooling.

## Audit wording

A completion summary must distinguish:

- actions completed before the policy change;
- actions prevented by the emergency stop;
- transfer results under the replacement policy;
- any irreversible loss and recovery attempt;
- final exact provider state.
