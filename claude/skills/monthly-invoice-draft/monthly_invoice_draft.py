#!/usr/bin/env python3
"""Create one idempotent, verified prior-month Gmail invoice draft.

Ported from the Hermes `monthly-invoice-draft` v0.1.1. Run through the
gmail-draft venv: ~/.claude/skills/gmail-draft/run.sh --script <this file> <command>
"""
from __future__ import annotations

import argparse
import calendar
import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ACCOUNT = "daniel.souza@laveapparel.com"
FROM_NAME = "Daniel de Souza"
TO_ADDRESS = "tatiana.braun@laveapparel.com"
CC_ADDRESS = "ody@laveapparel.com"
TO = [f"Tatiana Braun <{TO_ADDRESS}>"]
CC = [f"Ody Demetriadi <{CC_ADDRESS}>"]
HOURS_PER_DAY = 3
RATE_USD = 35
TZ = ZoneInfo("America/Los_Angeles")
GMAIL_DRAFT_DIR = Path.home() / ".claude" / "skills" / "gmail-draft"
# Cached from 1Password by op-secrets-load.sh (work-os manifest); never in the repo.
REMITTANCE_FILE = Path.home() / ".cache/claude-secrets/work-os/files/INVOICE_REMITTANCE"


@dataclass(frozen=True)
class InvoicePeriod:
    year: int
    month: int
    month_name: str
    weekdays: int
    hours: int
    amount_usd: int
    subject: str


def previous_month(today: date) -> InvoicePeriod:
    prior = today.replace(day=1) - timedelta(days=1)
    weekdays = sum(
        1
        for day in range(1, calendar.monthrange(prior.year, prior.month)[1] + 1)
        if date(prior.year, prior.month, day).weekday() < 5
    )
    hours = weekdays * HOURS_PER_DAY
    month_name = calendar.month_name[prior.month]
    return InvoicePeriod(
        year=prior.year,
        month=prior.month,
        month_name=month_name,
        weekdays=weekdays,
        hours=hours,
        amount_usd=hours * RATE_USD,
        subject=f"Invoice for {month_name} / {prior.year}",
    )


def read_remittance() -> str:
    try:
        value = REMITTANCE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        value = ""
    if not value:
        raise RuntimeError(
            "remittance block not cached; run: cd ~/Developer/GitHub/work-os && ~/.claude/op-secrets-load.sh"
        )
    return value


def gmail_module():
    path = GMAIL_DRAFT_DIR / "scripts" / "gmail_draft.py"
    spec = importlib.util.spec_from_file_location("gmail_draft", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("gmail-draft skill is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_body(period: InvoicePeriod, remittance: str) -> str:
    return (
        "Hi Tati,\n\n"
        f"The invoice amount for {period.month_name} was ${period.amount_usd:,}.\n\n"
        f"{remittance}\n\n"
        "Thank you,\n\n"
        "Daniel\n"
    )


def required_text(period: InvoicePeriod) -> list[str]:
    return [f"invoice amount for {period.month_name}", f"${period.amount_usd:,}", "Thank you"]


def _normalize_multiline(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "\n".join(line.rstrip() for line in normalized.splitlines())


def has_remittance(module, draft: dict[str, Any], remittance: str) -> bool:
    payload = (draft.get("message") or {}).get("payload") or {}
    return _normalize_multiline(remittance) in _normalize_multiline(module._body_text(payload))


def get_json(session, url: str, **params) -> dict[str, Any]:
    response = session.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def subject_drafts(module, session, subject: str) -> list[dict[str, Any]]:
    base = f"{module.GMAIL_API}/users/me/drafts"
    found = []
    for item in get_json(session, base, q=f'subject:"{subject}"', maxResults=100).get("drafts", []):
        draft = get_json(session, f"{base}/{item['id']}", format="full")
        headers = module._header_map((draft.get("message") or {}).get("payload") or {})
        if headers.get("subject") == subject:
            found.append(draft)
    return found


def already_sent(module, session, period: InvoicePeriod) -> bool:
    base = f"{module.GMAIL_API}/users/me/messages"
    query = (
        f'in:sent subject:"{period.subject}" to:{TO_ADDRESS} '
        f"after:{date(period.year, period.month, 1):%Y/%m/%d}"
    )
    for item in get_json(session, base, q=query, maxResults=25).get("messages", []):
        message = get_json(session, f"{base}/{item['id']}", format="full")
        payload = message.get("payload") or {}
        headers = module._header_map(payload)
        labels = set(message.get("labelIds") or [])
        if (
            headers.get("subject") == period.subject
            and TO_ADDRESS in module._addresses(headers.get("to", ""))
            and f"${period.amount_usd:,}" in module._body_text(payload)
            and "SENT" in labels
            and "DRAFT" not in labels
        ):
            return True
    return False


def result(period: InvoicePeriod, operation: str, verification: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "operation": operation,
        "period": asdict(period),
        "draft_id": verification.get("draft_id"),
        "labels": verification.get("labels"),
        "checks": verification.get("checks"),
        "remittance_block_present": True,
        "sent": False,
    }


def check_or_create(command: str, period: InvoicePeriod) -> dict[str, Any]:
    module = gmail_module()
    sender = f"{FROM_NAME} <{ACCOUNT}>"
    helper = os.environ.get(
        "GMAIL_DRAFT_CREDENTIAL_HELPER",
        str(GMAIL_DRAFT_DIR / "scripts" / "cache_credential_helper.sh"),
    )
    with module.delegated_credentials(ACCOUNT, module.DEFAULT_CREDENTIAL_ITEM, helper) as credentials:
        if command == "check":
            auth = module.auth_check(credentials)
            return {
                "status": "ready",
                "period": asdict(period),
                "gmail_authorized": bool(auth.get("authorized")),
                "remittance_available": bool(read_remittance()),
                "write_performed": False,
            }
        session = module.api_session(credentials)
        if already_sent(module, session, period):
            return {
                "status": "already_sent",
                "operation": "sent message found; no draft write",
                "period": asdict(period),
                "sent": True,
                "write_performed": False,
            }
        remittance = read_remittance()
        drafts = subject_drafts(module, session, period.subject)
        if len(drafts) > 1:
            raise RuntimeError(f"multiple drafts already use subject {period.subject!r}; no write performed")
        verify_args = (sender, TO, CC, [], period.subject, [], {}, True, False, required_text(period))
        if drafts:
            verification = module.verify_draft(drafts[0], *verify_args)
            if not has_remittance(module, drafts[0], remittance):
                raise RuntimeError("existing draft has different remittance text; no write performed")
            return result(period, "existing verified draft (no write)", verification)
        message = module.build_message(
            sender, TO, CC, [], period.subject, build_body(period, remittance), None, [], {}
        )
        verification = module.write_and_verify(credentials, message, "create", None, *verify_args)
        draft = get_json(
            session, f"{module.GMAIL_API}/users/me/drafts/{verification['draft_id']}", format="full"
        )
        if not has_remittance(module, draft, remittance):
            raise RuntimeError("created draft failed remittance read-back verification")
        return result(period, "created and verified", verification)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preview", "check", "create"])
    parser.add_argument("--today", help="override the local date as YYYY-MM-DD")
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else datetime.now(TZ).date()
    period = previous_month(today)
    try:
        if args.command == "preview":
            output = {"status": "preview", "period": asdict(period), "write_performed": False}
        else:
            output = check_or_create(args.command, period)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "period": asdict(period),
                    "error": str(exc),
                    "write_performed": False if args.command != "create" else "unknown",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
