#!/usr/bin/env python3
"""Share a GAS project's Drive file with the read-only drift SA, then verify.

Handles both shapes (auto-detected via projects.get.parentId):
  - bound      -> share the parent Sheet;      verify SA projects.get 200 + parentId match
  - standalone -> share the script's own file; verify SA projects.getContent 200 (no parent)
Uses Daniel's clasp OAuth (~/.clasprc.json) to grant + detect; confirms with the SA itself.

Usage: share_script_with_sa.py <scriptId>
Env:   GCP_WIP_SYNC_SA = path to the SA JSON key (from the op cache).
"""
import json, os, sys
from google.oauth2.credentials import Credentials as UserCreds
from google.oauth2 import service_account
from google.auth.transport.requests import Request, AuthorizedSession

SA_EMAIL = "wip-sync-tool@sodium-diode-177520.iam.gserviceaccount.com"
RO_SCOPE = "https://www.googleapis.com/auth/script.projects.readonly"


def user_session():
    tok = json.load(open(os.path.expanduser("~/.clasprc.json")))["tokens"]["default"]
    creds = UserCreds(token=tok.get("access_token"), refresh_token=tok["refresh_token"],
                      client_id=tok["client_id"], client_secret=tok["client_secret"],
                      token_uri="https://oauth2.googleapis.com/token")
    creds.refresh(Request())
    return AuthorizedSession(creds)


def sa_session():
    creds = service_account.Credentials.from_service_account_file(os.environ["GCP_WIP_SYNC_SA"], scopes=[RO_SCOPE])
    return AuthorizedSession(creds)


def main():
    script_id = sys.argv[1]
    us = user_session()

    # 0) Detect type: parentId present => bound (share the Sheet); absent => standalone (share script file).
    g = us.get(f"https://script.googleapis.com/v1/projects/{script_id}", timeout=60)
    g.raise_for_status()
    parent = g.json().get("parentId")
    bound = bool(parent)
    target = parent if bound else script_id
    print(f"type={'bound' if bound else 'standalone'}; sharing Drive file {target}")

    # 1) Grant reader on the target file (idempotent — 'already exists' is fine).
    r = us.post(f"https://www.googleapis.com/drive/v3/files/{target}/permissions",
                params={"sendNotificationEmail": "false", "supportsAllDrives": "true"},
                json={"type": "user", "role": "reader", "emailAddress": SA_EMAIL}, timeout=60)
    if r.status_code not in (200, 201) and "already" not in r.text.lower():
        print(f"share failed ({r.status_code}): {r.text}"); sys.exit(1)
    print(f"share ok (or already present): {SA_EMAIL} -> reader on {target}")

    # 2) Verify with the SA.
    sa = sa_session()
    if bound:
        m = sa.get(f"https://script.googleapis.com/v1/projects/{script_id}", timeout=60)
        if m.status_code == 403:
            print("VERIFY 403: SA cannot read the script — share did not propagate."); sys.exit(1)
        m.raise_for_status()
        if m.json().get("parentId") != parent:
            print(f"WRONG SHEET: parentId={m.json().get('parentId')} != {parent}"); sys.exit(1)
        print(f"OK: SA reads bound script {script_id}; parentId matches {parent}")
    else:
        c = sa.get(f"https://script.googleapis.com/v1/projects/{script_id}/content", timeout=60)
        if c.status_code == 403:
            print("VERIFY 403: SA cannot read the standalone script — share did not propagate."); sys.exit(1)
        c.raise_for_status()
        print(f"OK: SA reads standalone script {script_id} ({len(c.json().get('files', []))} files)")


if __name__ == "__main__":
    main()
