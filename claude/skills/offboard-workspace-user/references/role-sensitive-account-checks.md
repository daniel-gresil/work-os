# Role-sensitive workspace account checks

Use this reference when an address name suggests that the identity may be shared, automated, regulated, or a resource rather than an ordinary employee account. The local part is a risk signal, not proof: resolve the provider object type and immutable ID before deciding what may be changed.

## Shared customer-facing addresses

Examples include support, contact, customer-service, sales, and info-style addresses.

Check:

- user versus group, alias, shared mailbox, proxy, contact, or helpdesk-owned recipient;
- forwarding, delegates, send-as identities, filters, recipient permissions, and catch-all/routing dependencies;
- CRM/helpdesk ingestion, OAuth grants, webhook ownership, and ticket-system reply addresses;
- whether new inbound mail should route elsewhere, become an alias, or intentionally bounce.

Do not infer that deleting a source user should delete the live mailbox that currently owns the address as a proxy.

## Administrative-looking addresses

An address named `admin` is not necessarily privileged, but its blast radius must be proven rather than assumed.

Check:

- Google super-admin/delegated roles and Microsoft directory roles;
- billing, domain/DNS, recovery, break-glass, app/service ownership, OAuth consent, service-account/DWD impersonation, and automation dependencies;
- whether another independently verified administrator remains before any role removal;
- data transfer completion before alias/proxy handoff.

A user's statement that the account “wasn't really an admin” is policy context, not live-state evidence.

## Room and device identities

Conference-room-style addresses may be Google Calendar resources, Exchange room/resource mailboxes, Teams Rooms accounts, device identities, ordinary users, or several linked objects.

Check:

- resource type and immutable IDs on both providers;
- future bookings, delegates, auto-accept configuration, room metadata, licenses, device enrollment, and Teams Rooms associations;
- whether the instruction intentionally retires booking and device behavior as well as the address.

Deleting only a similarly named user may leave the actual room resource active; deleting the resource may cancel a business function the requester did not mean to remove.

## HR and finance identities

HR, payroll, accounting, costing, and finance-style accounts can own regulated records even when the requester reports no known legal hold.

Check:

- Vault/Purview/eDiscovery holds available through APIs;
- personnel, payroll, tax, AP/AR, costing, and statutory retention policy input;
- owned Drive/OneDrive objects and mailbox volume without exposing document names or message content in artifacts;
- unexpected owned data as a policy-changing discovery.

If a retain-nothing instruction preceded discovery of material owned data, reopen only that data decision. Record the count and reported bytes, ask whether to transfer or destroy, and require an exact recipient for transfer.

## Operational and automation identities

Inventory, logistics, sourcing, fabric-development, and similar accounts may own ERP workflows, vendor portals, shipping integrations, Apps Script projects, or OAuth grants.

Check:

- ERP/helpdesk/vendor/carrier integrations and OAuth grants;
- forwarding and filters used as lightweight automation;
- Apps Script project files, deployments, triggers, Cloud projects, execution identities, and external credentials;
- operational-record retention even when mailbox content itself may be discarded.

Revoking or abandoning an integration is a separate explicit policy decision when discovered after intake. Treat Google Voice as a separate dependency too: inventory the Voice SKU and assigned phone number, and require explicit authorization to release the number/remove the Voice license rather than assuming ordinary Workspace license removal covers it.

On Microsoft, `accessDenied` or `resourceLocked` from OneDrive/SharePoint inventory is an incomplete dependency check, not evidence of zero data. Use an authorized SharePoint/OneDrive or Exchange Online read path where available; otherwise record a separate explicit approval to delete despite unknown site contents. A zero-license user can still have a retained or locked site.

## Alias and proxy handoff

For address conversion to another user's alias:

1. Prove both source and target identities.
2. Determine whether the address is already a proxy on a third-party mailbox.
3. Transfer required data first.
4. Use a tombstone rename/readdress when deletion or soft-deletion would reserve the address.
5. Verify the desired address is released.
6. Assign it to the exact target and read it back.
7. Delete only the actual source object; leave third-party mailbox owners unchanged.

## Queue discipline

Keep destructive identities in separate audit units. When the requester says to work one at a time, do not fan out or start parallel execution; finish or reach a genuine blocker on the selected card before starting the next. A compact shared-policy confirmation may reduce intake repetition, but every identity still receives its own immutable guards and dependency inventory.
