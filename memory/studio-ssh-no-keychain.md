---
name: studio-ssh-no-keychain
description: Over SSH to the Mac Studio, the macOS keychain is locked, so gh/git GitHub auth and 1Password prompts do not work there
metadata:
  type: reference
---

Over `ssh daniels-mac-studio`, the login keychain refuses access ("User interaction is not allowed"). Effects: `gh auth status` reports both accounts as failed although they are logged in, git cannot push or pull to GitHub, and 1Password biometric prompts cannot be answered.

**How to apply:** To move work-os commits between the Macs without GitHub auth on the far side, push or pull over SSH directly (`git push ssh://daniels-mac-studio/~/Developer/GitHub/work-os main:refs/remotes/origin/main`, then `git merge --ff-only origin/main` there). Anything needing the keychain or Touch ID on the Studio must be run by Dan in a terminal on that Mac. On either Mac, a 1Password prompt raised from Claude's Bash tool can time out unnoticed; ask Dan to run `~/.claude/op-secrets-load.sh` himself with `!`.
