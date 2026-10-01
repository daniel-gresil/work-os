# Per-user completion report contract

Use this after multi-account provisioning or offboarding runs.

## Required section set

Build the expected section-heading set from the exact requested account manifest. Normalize only for comparison; render the original exact addresses. Assert:

- every requested address appears exactly once;
- no unrequested address appears as a user section;
- completed, partial, blocked, and provider-no-op outcomes remain distinct;
- a deleted identity is not presented as full data purge when OneDrive/SharePoint or another provider-retained resource remains.

## Per-user fields

1. Exact email address.
2. Google Workspace final state and immutable-ID evidence.
3. Microsoft 365 final state and immutable-ID evidence.
4. Mail/file disposition and transfer recipient.
5. Alias/proxy/routing outcome.
6. Groups, licenses, OAuth grants, Voice numbers, room/device resources, and automation dependencies.
7. Independent verification performed.
8. Residual limitation or accepted unknown.

## Email workflow

Create one concise Gmail draft from the selected account. Verify draft owner, recipient, subject, exact heading set, and totals by API read-back. Never send unless explicitly requested. Do not include raw mailbox contents, personnel data, secrets, tokens, or unnecessary file names.