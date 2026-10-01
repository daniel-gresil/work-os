#!/usr/bin/env python3
"""Fetch the live Apps Script source + project metadata using a service-account key,
via the standard SA JWT flow (no IAM Credentials API / Token Creator role needed).

Reads from env:
  GCP_SA_KEY  — the service-account JSON key (contents, not a path)
  SCRIPT_ID   — the Apps Script project id

Writes live.json (projects.getContent) and meta.json (projects.get) to cwd.
Read-only scope only.
"""
import os, json
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SCOPE = "https://www.googleapis.com/auth/script.projects.readonly"

def main():
    info = json.loads(os.environ["GCP_SA_KEY"])
    script_id = os.environ["SCRIPT_ID"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    s = AuthorizedSession(creds)
    base = f"https://script.googleapis.com/v1/projects/{script_id}"

    content = s.get(f"{base}/content", timeout=60)
    content.raise_for_status()
    json.dump(content.json(), open("live.json", "w"))

    meta = s.get(base, timeout=60)
    meta.raise_for_status()
    json.dump(meta.json(), open("meta.json", "w"))

    n = len(content.json().get("files", []))
    print(f"fetched live: {n} files; meta updateTime={meta.json().get('updateTime')}")

if __name__ == "__main__":
    main()
