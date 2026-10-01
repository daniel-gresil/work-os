#!/usr/bin/env bash
# Apply + verify the canonical Lave branch-protection policy on <org>/<repo> main.
# Usage: apply_protection.sh <org>/<repo> [branch-protection.json]
set -euo pipefail
REPO="${1:?usage: apply_protection.sh <org>/<repo> [json]}"
JSON="${2:-$(dirname "$0")/../templates/branch-protection.json}"
BRANCH="${BRANCH:-main}"

echo "Applying branch protection to $REPO ($BRANCH)…"
gh api -X PUT "repos/$REPO/branches/$BRANCH/protection" --input "$JSON" >/dev/null

gh api "repos/$REPO/branches/$BRANCH/protection" | python3 -c '
import json,sys
p=json.load(sys.stdin)
got={
 "require_PR": p.get("required_pull_request_reviews") is not None,
 "required_approvals": (p.get("required_pull_request_reviews") or {}).get("required_approving_review_count"),
 "admins_exempt": not p["enforce_admins"]["enabled"],
 "force_push_blocked": not p["allow_force_pushes"]["enabled"],
 "deletions_blocked": not p["allow_deletions"]["enabled"],
}
want={"require_PR":True,"required_approvals":0,"admins_exempt":True,"force_push_blocked":True,"deletions_blocked":True}
bad={k:{"got":got[k],"want":want[k]} for k in want if got[k]!=want[k]}
print("effective:",json.dumps(got))
if bad: print("MISMATCH:",json.dumps(bad)); sys.exit(1)
print("OK: branch protection matches canonical policy")
'
