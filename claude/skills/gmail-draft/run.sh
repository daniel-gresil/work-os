#!/bin/bash
# Runs a script from this skill in a skill-local venv, created on first use.
#   run.sh <gmail_draft.py args>            draft tool (default)
#   run.sh --script /path/to/other.py ...   another script needing the same venv
D="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$D/.venv/bin/python" ]; then
  { python3 -m venv "$D/.venv" && "$D/.venv/bin/pip" -q install google-auth requests; } >&2 || exit 1
fi
export GMAIL_DRAFT_CREDENTIAL_HELPER="$D/scripts/cache_credential_helper.sh"
SCRIPT="$D/scripts/gmail_draft.py"
[ "$1" = --script ] && { SCRIPT="$2"; shift 2; }
exec "$D/.venv/bin/python" "$SCRIPT" "$@"
