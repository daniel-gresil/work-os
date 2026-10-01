#!/usr/bin/env python3
"""Create, update, and verify Gmail drafts with delegated credentials.

This helper deliberately exposes no send or delete operation.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, getaddresses
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SCOPES = [GMAIL_COMPOSE_SCOPE, GMAIL_READONLY_SCOPE]
REPLY_METADATA_HEADERS = ["Message-ID", "References", "Subject", "From"]
DEFAULT_SUBJECT_ACCOUNT = "daniel.souza@laveapparel.com"
DEFAULT_CREDENTIAL_ITEM = "google-workspace-lave-service-account"
DEFAULT_CREDENTIAL_HELPER = str(Path(__file__).with_name("op_credential_helper.py"))
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


class DraftVerificationError(RuntimeError):
    """Raised when Gmail read-back does not match the requested draft."""


class ReplyLookupError(RuntimeError):
    """Raised when --reply-to-query matches nothing usable."""


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _header_map(payload: Dict[str, Any]) -> Dict[str, str]:
    return {
        item["name"].lower(): item["value"]
        for item in payload.get("headers", [])
        if item.get("name") and item.get("value") is not None
    }


def _walk_parts(payload: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    yield payload
    for part in payload.get("parts", []) or []:
        yield from _walk_parts(part)


def _part_headers(part: Dict[str, Any]) -> Dict[str, str]:
    return _header_map(part)


def _content_id(part: Dict[str, Any]) -> str:
    return _part_headers(part).get("content-id", "").strip().strip("<>")


def _content_disposition(part: Dict[str, Any]) -> str:
    return _part_headers(part).get("content-disposition", "").split(";", 1)[0].lower()


def _body_text(payload: Dict[str, Any]) -> str:
    values: List[str] = []
    for part in _walk_parts(payload):
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        try:
            values.append(_b64url_decode(data).decode("utf-8", errors="replace"))
        except (ValueError, TypeError):
            continue
    return "\n".join(values)


def _mime_text(payload: Dict[str, Any], mime_type: str) -> str:
    values: List[str] = []
    for part in _walk_parts(payload):
        if part.get("mimeType") != mime_type:
            continue
        data = (part.get("body") or {}).get("data")
        if data:
            values.append(_b64url_decode(data).decode("utf-8", errors="replace"))
    return "\n".join(values)


def _addresses(value: str) -> List[str]:
    return [address.lower() for _, address in getaddresses([value]) if address]


@contextmanager
def delegated_credentials(
    subject: str,
    credential_item: str,
    credential_helper: str,
) -> Iterator[service_account.Credentials]:
    """Yield delegated credentials, deleting service-account JSON on exit."""
    fd, name = tempfile.mkstemp(prefix="gmail-draft-sa-", suffix=".json")
    os.close(fd)
    path = Path(name)
    try:
        path.chmod(0o600)
        command = [credential_helper, "doc", credential_item, str(path)]
        if credential_helper.endswith(".py"):
            command.insert(0, sys.executable)
        helper_env = os.environ.copy()
        configured_home = os.environ.get("GMAIL_DRAFT_CREDENTIAL_HOME")
        helper_path = Path(credential_helper).expanduser()
        if configured_home:
            helper_env["HOME"] = configured_home
        elif helper_path.is_absolute() and helper_path.parent.name == "bin":
            # Approved profile-local wrappers live at HOME/.local/bin/lave-secret.
            helper_env["HOME"] = str(helper_path.parents[2])
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, env=helper_env
        )
        credentials = service_account.Credentials.from_service_account_file(
            str(path), scopes=GMAIL_SCOPES
        ).with_subject(subject)
        yield credentials
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def build_message(
    sender: str,
    to: Sequence[str],
    cc: Sequence[str],
    bcc: Sequence[str],
    subject: str,
    plain_body: Optional[str],
    html_body: Optional[str],
    attachments: Sequence[Path],
    inline_images: Mapping[str, Path],
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> EmailMessage:
    if not plain_body and not html_body:
        raise ValueError("provide --plain-body-file and/or --html-body-file")

    if inline_images and html_body is None:
        raise ValueError("--inline-image requires --html-body-file")

    body = EmailMessage(policy=SMTP)
    if plain_body is not None:
        body.set_content(plain_body)
        if html_body is not None:
            body.add_alternative(html_body, subtype="html")
    else:
        body.set_content(html_body or "", subtype="html")

    if inline_images:
        message = EmailMessage(policy=SMTP)
        message.make_related()
        message.attach(body)
        for cid, path in inline_images.items():
            _validate_file(path, "inline image")
            if not cid or any(char.isspace() for char in cid) or cid in "<>\"":
                raise ValueError(f"invalid inline image CID: {cid!r}")
            if (html_body or "").count(f"cid:{cid}") != 1:
                raise ValueError(f"HTML must reference cid:{cid} exactly once")
            content_type, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
            image = EmailMessage(policy=SMTP)
            image.set_content(
                path.read_bytes(), maintype=maintype, subtype=subtype, cte="base64"
            )
            image.add_header("Content-ID", f"<{cid}>")
            image.add_header("Content-Disposition", "inline", filename=path.name)
            message.attach(image)
    else:
        message = body

    message["From"] = sender
    if to:
        message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    message["Subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references

    for path in attachments:
        _validate_file(path, "attachment")
        content_type, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
        )
    return message


def _validate_file(path: Path, label: str) -> None:
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")


def _parse_inline_images(values: Sequence[str]) -> Dict[str, Path]:
    result: Dict[str, Path] = {}
    for value in values:
        cid, separator, filename = value.partition("=")
        if not separator or not cid or not filename:
            raise ValueError("--inline-image must use CID=/absolute/path")
        if cid in result:
            raise ValueError(f"duplicate inline image CID: {cid}")
        result[cid] = Path(filename)
    return result


def _normalize_ws(value: str) -> str:
    return " ".join(value.split())


def lookup_reply_target(session: AuthorizedSession, query: str) -> Dict[str, str]:
    """Return metadata for the newest message matching ``query``; never bodies."""
    list_response = session.get(
        f"{GMAIL_API}/users/me/messages",
        params={"q": query, "maxResults": 1},
        timeout=60,
    )
    list_response.raise_for_status()
    matches = list_response.json().get("messages") or []
    if not matches:
        raise ReplyLookupError(f"no message matched --reply-to-query {query!r}")
    provider_id = matches[0]["id"]  # users.messages.list is newest-first
    meta_response = session.get(
        f"{GMAIL_API}/users/me/messages/{provider_id}",
        params={"format": "metadata", "metadataHeaders": REPLY_METADATA_HEADERS},
        timeout=60,
    )
    meta_response.raise_for_status()
    original = meta_response.json()
    headers = _header_map(original.get("payload") or {})
    result = {
        "provider_message_id": provider_id,
        "thread_id": original.get("threadId") or "",
        "message_id": headers.get("message-id", "").strip(),
        "subject": headers.get("subject", "").strip(),
        "from": headers.get("from", "").strip(),
        "references": headers.get("references", ""),
    }
    missing = [key for key in ("thread_id", "message_id", "subject", "from") if not result[key]]
    if missing:
        raise ReplyLookupError(
            f"message {provider_id} lacks required reply metadata: {', '.join(missing)}"
        )
    return result


def reply_metadata(original: Mapping[str, str], explicit_to: Sequence[str]) -> Dict[str, Any]:
    subject = original["subject"]
    if not re.match(r"re:", subject, re.IGNORECASE):
        subject = f"Re: {subject}"
    return {
        "thread_id": original["thread_id"],
        "in_reply_to": original["message_id"],
        "references": _normalize_ws(f"{original['references']} {original['message_id']}"),
        "subject": subject,
        "to": list(explicit_to) or [original["from"]],
    }


def verify_draft(
    draft: Dict[str, Any],
    expected_from: str,
    expected_to: Sequence[str],
    expected_cc: Sequence[str],
    expected_bcc: Sequence[str],
    expected_subject: str,
    expected_attachments: Sequence[Path],
    expected_inline_images: Mapping[str, Path],
    expect_plain: bool,
    expect_html: bool,
    required_body_text: Sequence[str],
    reply: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    message = draft.get("message") or {}
    payload = message.get("payload") or {}
    headers = _header_map(payload)
    labels = set(message.get("labelIds") or [])
    parts = list(_walk_parts(payload))
    mime_types = [part.get("mimeType", "") for part in parts]
    attachment_filenames = sorted(
        part["filename"]
        for part in parts
        if part.get("filename") and _content_disposition(part) == "attachment"
    )
    inline_parts = [part for part in parts if _content_id(part)]
    inline_cids = sorted(_content_id(part) for part in inline_parts)
    inline_filenames = sorted(part.get("filename", "") for part in inline_parts)
    body = _body_text(payload)
    html = _mime_text(payload, "text/html")

    expected = {
        "to": sorted(_addresses(", ".join(expected_to))),
        "cc": sorted(_addresses(", ".join(expected_cc))),
        "bcc": sorted(_addresses(", ".join(expected_bcc))),
    }
    actual = {
        "to": sorted(_addresses(headers.get("to", ""))),
        "cc": sorted(_addresses(headers.get("cc", ""))),
        "bcc": sorted(_addresses(headers.get("bcc", ""))),
    }
    checks = {
        "from": headers.get("from") == expected_from,
        "recipient_headers": actual == expected,
        "subject": headers.get("subject") == expected_subject,
        "body_text": all(value in body for value in required_body_text),
        "plain_part": ("text/plain" in mime_types) == expect_plain,
        "html_part": ("text/html" in mime_types) == expect_html,
        "alternative": ("multipart/alternative" in mime_types)
        == (expect_plain and expect_html),
        "related": ("multipart/related" in mime_types) == bool(expected_inline_images),
        "attachment_filenames": attachment_filenames
        == sorted(path.name for path in expected_attachments),
        "inline_cids": inline_cids == sorted(expected_inline_images),
        "inline_filenames": inline_filenames
        == sorted(path.name for path in expected_inline_images.values()),
        "inline_disposition": all(
            _content_disposition(part) == "inline" for part in inline_parts
        ),
        "cid_linkage": all(html.count(f"cid:{cid}") == 1 for cid in expected_inline_images),
        "no_duplicate_inline_image": not (
            set(inline_filenames) & set(attachment_filenames)
        ),
        "draft_label": "DRAFT" in labels,
        "unsent": "SENT" not in labels,
    }
    if reply:
        checks.update(
            {
                "thread_id": message.get("threadId") == reply["thread_id"],
                "in_reply_to": headers.get("in-reply-to", "").strip() == reply["in_reply_to"],
                "references": _normalize_ws(headers.get("references", "")) == reply["references"],
                "reply_subject": (headers.get("subject") or "").lower().startswith("re:"),
            }
        )
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise DraftVerificationError("read-back verification failed: " + ", ".join(failed))

    return {
        "draft_id": draft.get("id"),
        "message_id": message.get("id"),
        "thread_id": message.get("threadId"),
        "original_thread_id": reply["thread_id"] if reply else None,
        "in_reply_to": headers.get("in-reply-to"),
        "references": headers.get("references"),
        "from": headers.get("from"),
        "to": actual["to"],
        "cc": actual["cc"],
        "bcc": actual["bcc"],
        "subject": headers.get("subject"),
        "mime_type": payload.get("mimeType"),
        "mime_types": mime_types,
        "attachment_filenames": attachment_filenames,
        "inline_cids": inline_cids,
        "inline_filenames": inline_filenames,
        "labels": sorted(labels),
        "required_body_text_present": list(required_body_text),
        "checks": checks,
    }


def api_session(credentials: service_account.Credentials) -> AuthorizedSession:
    credentials.refresh(Request())
    return AuthorizedSession(credentials)


def auth_check(credentials: service_account.Credentials) -> Dict[str, Any]:
    credentials.refresh(Request())
    return {
        "authorized": bool(credentials.valid and credentials.token),
        "subject": getattr(credentials, "_subject", None),
        "scope": GMAIL_SCOPES,
        "service_account_email": credentials.service_account_email,
    }


def write_and_verify(
    credentials: service_account.Credentials,
    message: EmailMessage,
    operation: str,
    draft_id: Optional[str],
    expected_from: str,
    to: Sequence[str],
    cc: Sequence[str],
    bcc: Sequence[str],
    subject: str,
    attachments: Sequence[Path],
    inline_images: Mapping[str, Path],
    expect_plain: bool,
    expect_html: bool,
    required_body_text: Sequence[str],
    reply: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    payload: Dict[str, Any] = {"message": {"raw": raw}}
    if reply:
        payload["message"]["threadId"] = reply["thread_id"]
    session = api_session(credentials)
    if operation == "create":
        write_response = session.post(
            f"{GMAIL_API}/users/me/drafts", json=payload, timeout=60
        )
        operation_name = "users.drafts.create"
    elif operation == "update" and draft_id:
        write_response = session.put(
            f"{GMAIL_API}/users/me/drafts/{draft_id}", json=payload, timeout=60
        )
        operation_name = "users.drafts.update"
    else:
        raise ValueError("operation must be create or update with a draft ID")
    write_response.raise_for_status()
    returned_draft_id = write_response.json()["id"]
    if draft_id and returned_draft_id != draft_id:
        raise DraftVerificationError("Gmail returned a different draft ID after update")
    draft_id = returned_draft_id

    get_response = session.get(
        f"{GMAIL_API}/users/me/drafts/{draft_id}",
        params={"format": "full"},
        timeout=60,
    )
    get_response.raise_for_status()
    result = verify_draft(
        get_response.json(),
        expected_from,
        to,
        cc,
        bcc,
        subject,
        attachments,
        inline_images,
        expect_plain,
        expect_html,
        required_body_text,
        reply,
    )
    result["impersonated_account"] = getattr(credentials, "_subject", None)
    result["scope"] = GMAIL_SCOPES
    result["operation"] = f"{operation_name} + users.drafts.get"
    return result


def _read_optional(path: Optional[str]) -> Optional[str]:
    return Path(path).read_text(encoding="utf-8") if path else None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--account", default=DEFAULT_SUBJECT_ACCOUNT, help="Workspace account to impersonate"
    )
    result.add_argument(
        "--credential-item", default=DEFAULT_CREDENTIAL_ITEM, help="1Password document item"
    )
    result.add_argument(
        "--credential-helper",
        default=os.environ.get("GMAIL_DRAFT_CREDENTIAL_HELPER", DEFAULT_CREDENTIAL_HELPER),
        help="approved helper that supports: doc ITEM OUT_PATH",
    )
    subparsers = result.add_subparsers(dest="command", required=True)
    subparsers.add_parser("auth-check", help="verify delegated token exchange without Gmail writes")

    def add_message_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--from-name")
        command.add_argument("--to", action="append", default=[])
        command.add_argument("--cc", action="append", default=[])
        command.add_argument("--bcc", action="append", default=[])
        command.add_argument("--subject", help="required unless --reply-to-query is given")
        command.add_argument(
            "--reply-to-query",
            help="Gmail search query; reply in the newest matching message's thread",
        )
        command.add_argument("--plain-body-file")
        command.add_argument("--html-body-file")
        command.add_argument("--inline-image", action="append", default=[])
        command.add_argument("--attach", action="append", default=[])
        command.add_argument("--verify-contains", action="append", default=[])

    create = subparsers.add_parser("create", help="create exactly one draft and verify read-back")
    add_message_arguments(create)
    update = subparsers.add_parser("update", help="update one existing draft in place and verify")
    update.add_argument("--draft-id", required=True)
    add_message_arguments(update)
    return result


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    result = parser()
    args = result.parse_args(argv)
    if args.command != "auth-check":
        if args.reply_to_query and args.subject:
            result.error("--subject cannot be combined with --reply-to-query")
        if not args.reply_to_query and not args.subject:
            result.error("--subject is required unless --reply-to-query is supplied")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        with delegated_credentials(
            args.account, args.credential_item, args.credential_helper
        ) as credentials:
            if args.command == "auth-check":
                output = auth_check(credentials)
            else:
                attachments = [Path(value) for value in args.attach]
                inline_images = _parse_inline_images(args.inline_image)
                plain_body = _read_optional(args.plain_body_file)
                html_body = _read_optional(args.html_body_file)
                sender = (
                    formataddr((args.from_name, args.account))
                    if args.from_name
                    else args.account
                )
                to, subject, reply = args.to, args.subject, None
                if args.reply_to_query:
                    original = lookup_reply_target(api_session(credentials), args.reply_to_query)
                    reply = reply_metadata(original, args.to)
                    to, subject = reply["to"], reply["subject"]
                message = build_message(
                    sender,
                    to,
                    args.cc,
                    args.bcc,
                    subject,
                    plain_body,
                    html_body,
                    attachments,
                    inline_images,
                    reply["in_reply_to"] if reply else None,
                    reply["references"] if reply else None,
                )
                output = write_and_verify(
                    credentials,
                    message,
                    args.command,
                    getattr(args, "draft_id", None),
                    sender,
                    to,
                    args.cc,
                    args.bcc,
                    subject,
                    attachments,
                    inline_images,
                    plain_body is not None,
                    html_body is not None,
                    args.verify_contains,
                    reply,
                )
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"gmail-draft: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
