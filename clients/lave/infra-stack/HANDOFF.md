# infra-stack handoff

Newest first. Older notes (through 2026-09-22) are in the repo's tracked `.claude/HANDOFF.md`.

## 2026-11-01 — 20261101_actual_budget — Actual Budget + Hermes skill, then decision to move to Firefly III

**Goal of this session:** Give Dan a self-hosted expense tracker he drives by talking to Hermes (record spending, pull card transactions automatically, track shared "house" bills with receipts, monthly reports). Built on Actual Budget; by the end Dan decided Firefly III fits better and the Actual stack becomes a two-week fallback.

**Done:**
- Actual Budget `26.10.0` live at `https://budget.gresil.com` on `vps-c590f124` (personal VPS), second tenant behind the shared Caddy in `~/trek/`, no host ports. `actual/docker-compose.yml`, `actual/deploy.sh` (idempotent; bootstraps the server password from `ACTUAL_PASSWORD` over the Docker network *before* adding the Caddy block), `trek/caddy/Caddyfile` block appended, `actual/README.md`.
- Hermes skill `actual/hermes-skill/actual-budget/` (`actual.mjs`, 11 commands over `@actual-app/api`; `run.sh` finds Hermes's bundled node and loads `~/.hermes/.env`). Installed on the Mac Studio at `~/.hermes/skills/finance/actual-budget/` with `node_modules`, symlinked into Janice's profile. `ACTUAL_SERVER_URL/PASSWORD/SYNC_ID` plaintext in the Studio's `~/.hermes/.env` (600); 1Password item `infra/Gresil Budget`; manifest lines in `.claude/op-secrets.txt`.
- Bank sync via SimpleFIN Bridge (Dan's account, token stored in Actual server-side). Three linked accounts: Apple Card (renamed from SimpleFIN's "Daniel"), Delta SkyMiles Reserve (Amex), Prime Store Card. Unlinked **on-budget** `Checking` account receives card payments as transfers (off-budget would still demand a category).
- 121 imported transactions (Sep 2 to Oct 31) categorized via API into Food/General/Bills + 7 transfers; 53 payee rules created so future imports land categorized.
- Shared expenses: tag `#house` in notes (not an account). `match <amount> --date --payee` syncs then tags the existing card charge; no hit → `spend --shared` pending entry that Actual's import reconciliation merges later (same account, same amount, ±7 days, no bank id). `shared --month last` is the report.
- Hermes cron: `actual-sync` (default profile, daily 07:00 PT, Telegram, id `d575a02f33c1`), `house-report` (janice, 1st of month 08:00 PT, id `cc5a72646a1e`).
- Decided 2026-11-01 (late): **switch to Firefly III**. Plan and the 16 agreed categories are in the infra-stack Claude project memory `project_firefly_switch.md` (Anthropic/OpenAI/Google Workspace → Business). Actual stays running as fallback ~2 weeks.

**In progress:**
- Nothing half-built. Branch is 11 commits, clean, not pushed.

**Open questions / blockers:**
- Firefly III build is the next session (prompt handed to Dan). Needs from Dan: DNS record `money.gresil.com`, a second SimpleFIN app token, 1Password item `infra/Gresil Firefly`.
- Actual data (`~/actual/data/` on the VPS) is not backed up to Drive yet; moot if Firefly replaces it, otherwise `gdrive:actual/` with the backup-tools SA.
- Pending work-os email draft from 2026-10-29 (Azure invoice reply, Portuguese) still needs the draft-vs-sent comparison in a work-os session.

**Key decisions and why:**
- Actual over Firefly initially — one container, SQLite, MIT. Reversed because Dan is not using envelope budgeting, wants tags/attachments/detailed reports and a real REST API; Firefly has all four.
- Library + skill over the community `actual-mcp` — 60 tools clutter every Hermes turn; the CLI exposes exactly what Dan uses.
- `spend`/`income` verbs instead of signed amounts — a forgotten minus sign would log an expense as income.
- Tag instead of a "House Account" — the money leaves a real card that bank sync imports; a second account would double count.
- Password bootstrap before Caddy exposure — a fresh Actual server accepts the first password anyone submits.

**Files touched:** `actual/` (all new), `trek/caddy/Caddyfile`, `CLAUDE.md` (+1 line), `.gitignore`, `.claude/op-secrets.txt`. Outside the repo: Mac Studio `~/.hermes/skills/finance/`, `~/.hermes/.env`, `~/.hermes/profiles/janice/skills/finance` symlink; VPS `~/actual/`, `~/trek/caddy/Caddyfile`.

**How to verify the current state:**
- `curl -s https://budget.gresil.com/health` → `{"status":"UP"}`
- `ssh daniels-mac-studio '~/.hermes/skills/finance/actual-budget/run.sh sync'` → `uncategorized: []`
- `ssh daniels-mac-studio 'hermes cron list; hermes -p janice cron list'` → `actual-sync`, `house-report` active
- `./actual/deploy.sh` after `~/.claude/op-secrets-load.sh` → "already bootstrapped", "already present", healthy.

**Gotchas learned:** op-secrets cache values are `printf %q` escaped (source, never grep); Actual rate-limits failed logins per IP (`docker compose restart actual` resets); `getAccounts()` hides `account_sync_source`; `runBankSync()` returns nothing and throws on the first bank error; transfers have no category, so "uncategorized" filters must exclude them.

**Next action when resuming:**
- Push `20261101_actual_budget` and open the PR to main (title and body proposed in the session), then start the Firefly session from the prompt Dan has.
