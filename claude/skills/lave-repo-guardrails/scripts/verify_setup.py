#!/usr/bin/env python3
"""End-to-end verification for a lave-repo-guardrails setup.
Usage: verify_setup.py <org>/<repo> <scriptId> [repo_path]
Env:   GCP_WIP_SYNC_SA = path to SA key.
"""
import json, os, subprocess, sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

RO_SCOPE = "https://www.googleapis.com/auth/script.projects.readonly"


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def main():
    repo, script_id = sys.argv[1], sys.argv[2]
    repo_path = sys.argv[3] if len(sys.argv) > 3 else "."
    org = repo.split("/")[0]
    fails = []

    # 1) Branch protection
    p = json.loads(gh("api", f"repos/{repo}/branches/main/protection").stdout or "{}")
    if not p:
        fails.append("branch protection: not set")
    else:
        if (p.get("required_pull_request_reviews") or {}).get("required_approving_review_count") != 0:
            fails.append("branch protection: approvals != 0")
        if p["allow_force_pushes"]["enabled"] or p["allow_deletions"]["enabled"]:
            fails.append("branch protection: force-push/deletions not blocked")

    # 2) Team access
    teams = json.loads(gh("api", f"repos/{repo}/teams").stdout or "[]")
    if not any(t["slug"] == "lave-team" and t["permission"] == "push" for t in teams):
        fails.append("team: lave-team lacks push")

    # 3) Secrets present
    secs = gh("secret", "list", "--repo", repo).stdout
    for s in ("GCP_SA_KEY", "TEAMS_WEBHOOK_URL"):
        if s not in secs:
            fails.append(f"secret missing: {s}")

    # 4) SA read access (bound/standalone agnostic — getContent must return 200)
    creds = service_account.Credentials.from_service_account_file(os.environ["GCP_WIP_SYNC_SA"], scopes=[RO_SCOPE])
    c = AuthorizedSession(creds).get(f"https://script.googleapis.com/v1/projects/{script_id}/content", timeout=60)
    if c.status_code != 200:
        fails.append(f"SA cannot read script content ({c.status_code})")

    # 5) Drift files present in the checkout
    need = [".github/workflows/live-drift-check.yml", ".github/scripts/fetch_live.py",
            ".github/scripts/check_drift.py", ".github/scripts/materialize_live.py", ".claspignore"]
    for f in need:
        if not os.path.exists(os.path.join(repo_path, f)):
            fails.append(f"file missing in repo: {f}")

    # Report + org owners (informational — they bypass protection)
    owners = gh("api", f"orgs/{org}/members?role=admin", "--jq", ".[].login").stdout.split()
    print(f"org owners (bypass protection): {owners or '[]'}")
    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("PASS: all lave-repo-guardrails checks green")


if __name__ == "__main__":
    main()
