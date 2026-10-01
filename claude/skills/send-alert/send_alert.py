#!/usr/bin/env python3
"""Send a Postgres alert email via Resend.

Reads a Markdown body file, renders it to HTML if the `markdown` package is
available (falls back to text-only otherwise), and posts a multipart message
to Resend's REST API. The API key must be in `RESEND_API_KEY` — invoke via
`op run --env-file=$HOME/.claude/skills/send-alert/.env -- python3 ...` so
1Password injects it at run time and it's never written to disk.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SENDER = "Postgres Agent <postgres-alerts@notify.laveapparel.com>"
RECIPIENT = "daniel.souza@laveapparel.com"
API_URL = "https://api.resend.com/emails"

PRIORITY_PREFIX = {"P0": "🔴 [P0]", "P1": "🟡 [P1]"}


def render_html(body_md: str) -> str | None:
    """Markdown → HTML using the `markdown` package. Returns None if it's
    not installed; caller falls back to text-only sending."""
    try:
        import markdown  # type: ignore
    except ImportError:
        return None
    body_html = markdown.markdown(body_md, extensions=["fenced_code", "tables"])
    return f"<div style='font-family:system-ui,sans-serif;max-width:720px'>{body_html}</div>"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--priority", required=True, choices=["P0", "P1"])
    p.add_argument("--subject", required=True)
    p.add_argument("--body-file", required=True, type=Path)
    args = p.parse_args()

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(
            "ERROR: RESEND_API_KEY not set. Invoke via "
            "`op run --env-file=$HOME/.claude/skills/send-alert/.env -- python3 ...`",
            file=sys.stderr,
        )
        return 2

    if not args.body_file.is_file():
        print(f"ERROR: body file not found: {args.body_file}", file=sys.stderr)
        return 2

    body_md = args.body_file.read_text()
    body_html = render_html(body_md)

    payload: dict = {
        "from": SENDER,
        "to": [RECIPIENT],
        "subject": f"{PRIORITY_PREFIX[args.priority]} {args.subject}",
        "text": body_md,
        "headers": {"X-Priority": "1" if args.priority == "P0" else "3"},
        "tags": [
            {"name": "source", "value": "postgres-expert"},
            {"name": "priority", "value": args.priority.lower()},
        ],
    }
    if body_html is not None:
        payload["html"] = body_html

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Cloudflare in front of Resend's API blocks the default
            # `Python-urllib/X.Y` UA with HTTP 403 / error 1010. Identify
            # the skill explicitly so the request looks like a normal API
            # client.
            "User-Agent": "postgres-expert-send-alert/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: Resend returned {e.code}: {body_text}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"ERROR: network/connection issue: {e.reason}", file=sys.stderr)
        return 1

    msg_id = body.get("id", "<no-id>")
    print(f"Sent: {msg_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
