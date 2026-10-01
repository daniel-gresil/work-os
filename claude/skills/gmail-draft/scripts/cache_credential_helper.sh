#!/bin/bash
# Credential helper for gmail_draft.py: "doc ITEM OUT_PATH".
# Copies the Lave service-account JSON from the work-os 1Password session cache
# (manifest: work-os/.claude/op-secrets.txt) instead of calling `op` each time.
[ "$1" = doc ] && [ -n "$3" ] || { echo "usage: cache_credential_helper.sh doc ITEM OUT_PATH" >&2; exit 2; }
SRC="$HOME/.cache/claude-secrets/work-os/files/GMAIL_SA_CREDENTIAL"
[ -s "$SRC" ] || { echo "credential not cached; run: cd ~/Developer/GitHub/work-os && ~/.claude/op-secrets-load.sh" >&2; exit 1; }
install -m 600 "$SRC" "$3"
