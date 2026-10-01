#!/usr/bin/env python3
"""Create (or send) a Gmail draft as daniel.souza@laveapparel.com.

Generic Gmail layer extracted from 9025_WIP's notify-wip-users skill —
recipient sourcing (UsersList tabs etc.) is the caller's job; this script
just takes addresses and content.

Default is a DRAFT so it can be reviewed in Gmail before sending.

Usage:
  source ~/.cache/claude-secrets/<repo>/env.sh   # sets $CLASP_CLI_CREDS
  gmail_draft.py --subject "..." --html body.html                 # draft, To: self
  gmail_draft.py --subject "..." --html body.html --to a@b.com
  gmail_draft.py --subject "..." --html body.html --bcc-file addrs.txt
  gmail_draft.py ... --send                                       # send immediately

Requires a one-time `authorize_gmail.py` (gmail.compose consent);
token cached at ~/.cache/claude-secrets/gmail/token.json.
"""
import argparse
import base64
import json
import os
import sys
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

SENDER = "daniel.souza@laveapparel.com"
TOKEN_PATH = os.path.expanduser("~/.cache/claude-secrets/gmail/token.json")


def gmail_token():
    creds_path = os.environ.get("CLASP_CLI_CREDS")
    if not creds_path:
        sys.exit("ERROR: $CLASP_CLI_CREDS not set. Source a repo's op cache env.sh first.")
    if not os.path.exists(TOKEN_PATH):
        sys.exit(f"ERROR: {TOKEN_PATH} missing. Run authorize_gmail.py once (interactive).")
    tok = json.load(open(TOKEN_PATH))
    c = json.load(open(creds_path))
    c = c.get("installed") or c.get("web")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).json()
    if "access_token" not in r:
        sys.exit(f"ERROR refreshing Gmail token: {r}")
    return r["access_token"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--html", required=True, help="path to HTML body file")
    ap.add_argument("--to", default=SENDER, help="To: address (default: sender)")
    ap.add_argument("--bcc", help="comma-separated BCC addresses")
    ap.add_argument("--bcc-file", help="file with one BCC address per line")
    ap.add_argument("--send", action="store_true", help="send immediately instead of leaving a draft")
    ap.add_argument("--image", action="append", default=[], metavar="CID=PATH",
                    help="inline image; reference it in the HTML as <img src=\"cid:CID\">. Repeatable.")
    args = ap.parse_args()

    bcc = [a.strip() for a in (args.bcc or "").split(",") if a.strip()]
    if args.bcc_file:
        bcc += [l.strip() for l in open(args.bcc_file) if l.strip()]

    html = MIMEText(open(args.html).read(), "html", "utf-8")
    if args.image:
        msg = MIMEMultipart("related")
        msg.attach(html)
        for spec in args.image:
            cid, path = spec.split("=", 1)
            img = MIMEImage(open(path, "rb").read())
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
            msg.attach(img)
    else:
        msg = html
    msg["From"] = SENDER
    msg["To"] = args.to
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = args.subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    h = {"Authorization": f"Bearer {gmail_token()}"}
    r = requests.post("https://gmail.googleapis.com/gmail/v1/users/me/drafts",
                      json={"message": {"raw": raw}}, headers=h)
    if r.status_code != 200:
        sys.exit(f"ERROR creating draft: {r.status_code} {r.text[:500]}")
    draft = r.json()
    print(f"Draft created: id={draft['id']}  https://mail.google.com/mail/u/0/#drafts")

    if args.send:
        r = requests.post("https://gmail.googleapis.com/gmail/v1/users/me/drafts/send",
                          json={"id": draft["id"]}, headers=h)
        if r.status_code != 200:
            sys.exit(f"ERROR sending draft (it still exists in Drafts): {r.status_code} {r.text[:500]}")
        n = len(bcc) if bcc else 1
        print(f"SENT ({n} recipient{'s' if n != 1 else ''}).")


if __name__ == "__main__":
    main()
