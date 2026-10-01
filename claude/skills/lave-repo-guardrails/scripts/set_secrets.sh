#!/usr/bin/env bash
# Populate GCP_SA_KEY + TEAMS_WEBHOOK_URL GitHub secrets from the 1Password op cache.
# Precondition: ~/.claude/op-secrets-load.sh has run and the repo env cache is sourced.
# Usage: set_secrets.sh <org>/<repo>
set -euo pipefail
REPO="${1:?usage: set_secrets.sh <org>/<repo>}"
: "${GCP_WIP_SYNC_SA:?source the op cache first (GCP_WIP_SYNC_SA unset)}"
: "${LAVE_DRIFT_TEAMS_WEBHOOK:?source the op cache first (LAVE_DRIFT_TEAMS_WEBHOOK unset)}"

gh secret set GCP_SA_KEY --repo "$REPO" < "$GCP_WIP_SYNC_SA"
printf '%s' "$LAVE_DRIFT_TEAMS_WEBHOOK" | gh secret set TEAMS_WEBHOOK_URL --repo "$REPO"
echo "secrets set on $REPO:"
gh secret list --repo "$REPO"
