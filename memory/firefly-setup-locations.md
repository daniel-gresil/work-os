---
name: firefly-setup-locations
description: "Where Dan's personal Firefly III (money.gresil.com) and its Hermes skill live, and how to reach the server"
metadata:
  node_type: memory
  type: reference
  originSessionId: 625c1243-d05d-40cb-89d3-bc89420d3688
  modified: 2026-11-06T16:43:28.698Z
---

Dan's personal expense tracking is Firefly III at `https://money.gresil.com` (set up 2026-11-01), driven by Hermes Agent. It is not in work-os, so look here first:

- **Server:** `vps-c590f124.vps.ovh.us`, folder `~/firefly/` (`docker-compose.yml`, `cron.sh`, `import/simplefin.json`). Containers: `firefly`, `firefly-importer`, `firefly-db`, `firefly-cron`. SSH command is documented in `~/Developer/GitHub/infra-stack/trek/README.md`.
- **Bank sync:** the Data Importer pulls SimpleFIN at 06:30 and 18:30 Pacific; logs are in the importer container under `storage/logs/`.
- **Backup (set up 2026-11-06):** `~/firefly/backup.sh` from root's crontab at 12:00 UTC, log `~/logs/firefly-backup.log`. Archives (database dump, receipts, config) go to `~/firefly/backups/` (root-only, 14 days) and to Google Drive of daniel@gresil.com, folder `firefly-backups`, through root's rclone remote `gdrive` (scope `drive.file`). Never use Lave's shared drive or the `backup-tools` account for this: it is personal data.
- **Hermes side (runs on the Mac Studio):** skill at `~/.hermes/skills/finance/firefly/`, token in `~/.hermes/.env`, daily `firefly-sync` job in the default profile, monthly `house-report` job in the Janice profile. Receipt state is shared by all profiles in `~/.hermes/firefly/`.
- **History of the setup conversation:** Hermes `state.db` files (`~/.hermes/state.db`, `~/.hermes/profiles/*/state.db`) and Hindsight.
- **Source copy of the server files:** as of 2026-11-05 there was no `firefly/` folder in `infra-stack` main on the Mac Studio and no Claude Code transcript of the build there. The MacBook Pro was not checked.

Mask long strings when reading container logs or env files there (`sed -E "s/[A-Za-z0-9]{24,}/<masked>/g"`): on 2026-11-05 `docker logs firefly-cron` showed two secrets in clear text. That leak was fixed and both secrets replaced on 2026-11-06.

Check `hostname` before saying which Mac a session is on: on 2026-11-05 I assumed the MacBook while running on the Mac Studio.
