#!/usr/bin/env python3
"""Read-only Gmail access for draft-email-reply. Never writes.

  thread --query Q                    print the thread of the newest message matching Q
  sent --thread-id T --after-ms N     print what Dan sent in thread T after time N
                                      [--images-dir DIR] also saves inline images there

Run through ../gmail-draft/run.sh --script so it shares that skill's venv and credential.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gmail-draft" / "scripts"))
import gmail_draft as gd  # noqa: E402


def get(session, path, **params):
    response = session.get(f"{gd.GMAIL_API}/users/me/{path}", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def text_of(payload):
    """Plain text of a message; falls back to HTML with tags stripped."""
    plain = gd._mime_text(payload, "text/plain")
    if plain.strip():
        return plain
    raw = gd._mime_text(payload, "text/html")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", "", raw))


def describe(message):
    payload = message.get("payload") or {}
    headers = gd._header_map(payload)
    raw_html = gd._mime_text(payload, "text/html")
    files = [p for p in gd._walk_parts(payload) if p.get("filename")]
    return {
        "id": message["id"],
        "internal_date_ms": int(message.get("internalDate", 0)),
        "labels": message.get("labelIds", []),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "date": headers.get("date", ""),
        "subject": headers.get("subject", ""),
        "text": text_of(payload).strip(),
        "has_table": "<table" in raw_html.lower(),
        "inline_images": [p["filename"] for p in files if gd._content_id(p)],
        "attachments": [p["filename"] for p in files if not gd._content_id(p)],
    }


def save_images(session, message, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for part in gd._walk_parts(message.get("payload") or {}):
        attachment_id = (part.get("body") or {}).get("attachmentId")
        if attachment_id and part.get("mimeType", "").startswith("image/"):
            data = get(session, f"messages/{message['id']}/attachments/{attachment_id}")["data"]
            (directory / Path(part["filename"] or attachment_id).name).write_bytes(gd._b64url_decode(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--account", default=gd.DEFAULT_SUBJECT_ACCOUNT)
    sub = parser.add_subparsers(dest="command", required=True)
    thread = sub.add_parser("thread")
    thread.add_argument("--query", required=True)
    sent = sub.add_parser("sent")
    sent.add_argument("--thread-id", required=True)
    sent.add_argument("--after-ms", type=int, required=True)
    sent.add_argument("--images-dir")
    args = parser.parse_args()

    with gd.delegated_credentials(
        args.account, gd.DEFAULT_CREDENTIAL_ITEM, gd.os.environ["GMAIL_DRAFT_CREDENTIAL_HELPER"]
    ) as credentials:
        session = gd.api_session(credentials)
        if args.command == "thread":
            matches = get(session, "messages", q=args.query, maxResults=1).get("messages") or []
            if not matches:
                sys.exit(f"no message matched {args.query!r}")
            thread_id = matches[0]["threadId"]
        else:
            thread_id = args.thread_id
        messages = get(session, f"threads/{thread_id}", format="full").get("messages", [])
        if args.command == "sent":
            messages = [
                m for m in messages
                if "SENT" in m.get("labelIds", []) and int(m.get("internalDate", 0)) > args.after_ms
            ]
            if args.images_dir:
                for message in messages:
                    save_images(session, message, Path(args.images_dir) / message["id"])
        output = {"thread_id": thread_id, "messages": [describe(m) for m in messages]}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
