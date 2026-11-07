---
name: mac-studio-is-hermes-host
description: The Mac Studio is the authoritative Hermes host; the MacBook's Hermes is only a remote client, so skills, env values and cron jobs are installed on the Studio
metadata:
  type: feedback
---

Install Hermes skills, `.env` values and cron jobs on the Mac Studio over `ssh daniels-mac-studio`, never on the MacBook. The MacBook's `~/.hermes` is a remote client of the Studio's gateway; anything placed there is not used.

**Why:** Dan reminded me of this on 2026-11-01 after I installed the Actual Budget skill on the MacBook first; the MacBook copy then had to be stripped of its plaintext secrets and cache.

**How to apply:** install to `~/.hermes/skills/<group>/<skill>/` on the Studio, write env values to the Studio's `~/.hermes/.env` (mode 600), test there with Hermes's bundled node (`~/.hermes/node/bin/node`), and create jobs with `hermes -p <profile> cron create`. Keep a secret-free copy on the MacBook only for editing. See [[studio-ssh-no-keychain]] for what cannot be done over SSH there.
