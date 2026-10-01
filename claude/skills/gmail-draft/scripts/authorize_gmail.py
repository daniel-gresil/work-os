#!/usr/bin/env python3
"""One-time Gmail authorization for the gmail-draft skill.

Runs the OAuth desktop flow (opens a browser) for daniel.souza@laveapparel.com
with the gmail.compose scope — create AND send drafts, nothing else. The
refresh token is cached at ~/.cache/claude-secrets/gmail/token.json (mode 600),
account-scoped so every repo shares it.

Uses the same OAuth desktop client as clasp ($CLASP_CLI_CREDS — source any
repo's op cache env.sh first).

Run interactively (needs a browser):  python3 authorize_gmail.py
"""
import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
TOKEN_PATH = os.path.expanduser("~/.cache/claude-secrets/gmail/token.json")


def main():
    creds_path = os.environ.get("CLASP_CLI_CREDS")
    if not creds_path:
        sys.exit("ERROR: $CLASP_CLI_CREDS not set. Source a repo's op cache env.sh first.")

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump({"refresh_token": creds.refresh_token, "scopes": SCOPES}, f)
    os.chmod(TOKEN_PATH, 0o600)
    print(f"OK: refresh token saved to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
