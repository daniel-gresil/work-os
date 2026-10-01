## 2026-10-01 — main — Sprint 6 planning

**Goal of this session:** Create the overdue next sprint on the IT Dept board, backdated to the day after Sprint 5 ended, and draft the announcement.

**Done:**
- Created ADO iteration `IT Dept\Sprint 6` (2026-09-24 to 2026-10-07) and added it to IT Dept Team.
- Moved the 22 Doing cards into it with Start/Target dates via `.claude/skills/sprint-planning/sprint_plan.py --apply`.
- Created the Gmail draft "IT Next Sprint Report: Sep, 24th to Oct, 7th (Sprint 6)" via `newsletter.py sprint --draft`.

**In progress:**
- Nothing.

**Open questions / blockers:**
- The draft body was not read back; Dan reviews and sends it.
- Dashboard masthead not checked after the apply.

**Key decisions and why:**
- Start date 2026-09-24, not today — keeps sprints contiguous with Sprint 5 (ended 2026-09-23); about half the cards carry past dates as a result.
- Name and dates were derived from the existing team iterations, then confirmed with the dry run, instead of asked cold.

**Files touched:**
- None in the repo.

**How to verify the current state:**
- Dashboard masthead shows Sprint 6; `python3 .claude/skills/sprint-planning/sprint_plan.py --selftest`.

**Next action when resuming:**
- Next sprint planning is due 2026-10-08 (Sprint 7, 2026-10-08 to 2026-10-21 if the cadence holds).
