# Cross-provider alias handoff and fan-in repair

## Resolve each provider independently

An address-handoff request can legitimately produce different outcomes by provider:

- Google may have an exact active destination user while Microsoft has no matching destination object.
- Microsoft may already store the requested address as a proxy on a third mailbox while Google has a standalone source user.
- A same-localpart object on another domain is never a destination substitute.

Freeze provider-specific outcomes before writes. Examples:

- `Google: tombstone source, add alias to exact target, delete source.`
- `Microsoft: delete exact source; create no destination and add no proxy.`
- `Microsoft: move only the existing proxy between exact immutable mailbox IDs; delete neither mailbox owner.`

Never create a missing cross-provider target merely to make both sides symmetrical unless the user separately authorizes provisioning.

## Address release sequence

1. Resolve source and destination independently on each provider.
2. Verify exact immutable IDs and global address ownership.
3. Complete required data transfer first.
4. Suspend/block and revoke source sessions.
5. Tombstone or readdress the source where needed.
6. Verify the desired address is globally unowned.
7. Add the alias/proxy only to the exact destination.
8. Verify sole ownership and protected destination fields.
9. Delete only the source object and verify license release.

## Replacement execution cards

A timed-out or triaged card may need a small non-decomposing replacement that resumes from durable checkpoints. When that replacement finishes:

1. Record the replacement's exact final-state handoff on the original account thread.
2. Update downstream summary/review dependencies to include the replacement.
3. Close or remove the obsolete original gate where the board permits it.
4. Verify the final fan-in task is no longer waiting on a superseded parent.

Do this immediately. A verified external result is not enough if the board graph still represents the account as incomplete.
