#!/usr/bin/env python3
"""CLI for reusable Google Workspace / Microsoft 365 user lifecycle operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional

from lifecycle_engine import (
    TRANSFER_DEFAULT_MAX_WAIT_SECONDS,
    TRANSFER_DEFAULT_POLL_INTERVAL_SECONDS,
    TRANSFER_MAX_WAIT_CEILING_SECONDS,
    TRANSFER_OPERATION,
    build_plan,
    execute_plan,
    execute_transfer,
    inventory_all,
    load_json,
    sanitize_error,
    utc_now,
    verify_only,
    verify_transfer,
)
from provider_adapters import GoogleWorkspaceAdapter, Microsoft365Adapter


def build_adapters(request: Mapping[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    adapters: Dict[str, Any] = {}
    platforms = request.get("platforms") or {}
    google = platforms.get("google_workspace") or {}
    microsoft = platforms.get("microsoft_365") or {}
    if google.get("disposition", "skip") != "skip":
        credential = args.google_credential or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        subject = args.google_admin_subject or os.environ.get("GOOGLE_WORKSPACE_ADMIN_SUBJECT")
        if not credential or not subject:
            raise ValueError("Google live mode requires --google-credential/GOOGLE_APPLICATION_CREDENTIALS and --google-admin-subject/GOOGLE_WORKSPACE_ADMIN_SUBJECT")
        adapters["google_workspace"] = GoogleWorkspaceAdapter(credential, subject)
    if microsoft.get("disposition", "skip") != "skip":
        adapters["microsoft_365"] = Microsoft365Adapter()
    return adapters


def write_report(path: str, report: Mapping[str, Any]) -> None:
    destination = os.path.abspath(path)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(destination)


def bounded_seconds(maximum: int):
    def convert(text: str) -> int:
        value = int(text)
        if value < 1 or value > maximum:
            raise argparse.ArgumentTypeError("must be between 1 and {} seconds".format(maximum))
        return value
    return convert


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("mode", choices=("inventory", "plan", "dry-run", "apply", "verify"))
    value.add_argument("--request", required=True, help="Policy/request JSON; contains no credentials")
    value.add_argument("--output", required=True, help="Sanitized JSON output")
    value.add_argument("--inventory", help="Inventory JSON for plan/dry-run")
    value.add_argument("--plan", help="Approved plan JSON for apply")
    value.add_argument("--approval", help="Approval JSON bound to plan digest for apply")
    value.add_argument("--checkpoint", help="Durable checkpoint JSON for apply/resume")
    value.add_argument("--google-credential", help="External service-account JSON path; never copied to output")
    value.add_argument("--google-admin-subject", help="Explicit delegated admin subject")
    value.add_argument("--max-parallel-reads", type=int, default=2)
    value.add_argument("--poll-interval-seconds", type=bounded_seconds(600), default=TRANSFER_DEFAULT_POLL_INTERVAL_SECONDS, help="Data Transfer status poll interval for {} apply".format(TRANSFER_OPERATION))
    value.add_argument("--max-wait-seconds", type=bounded_seconds(TRANSFER_MAX_WAIT_CEILING_SECONDS), default=TRANSFER_DEFAULT_MAX_WAIT_SECONDS, help="Bounded wait for Data Transfer completion; on expiry apply reports transfer_pending and is resumable")
    return value


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    request = load_json(args.request)
    transfer = request.get("operation") == TRANSFER_OPERATION
    try:
        if args.mode == "inventory":
            report = inventory_all(request, build_adapters(request, args), args.max_parallel_reads)
        elif args.mode in {"plan", "dry-run"}:
            if not args.inventory:
                raise ValueError("--inventory is required for plan/dry-run")
            report = build_plan(request, load_json(args.inventory))
            report["mode"] = "dry_run" if args.mode == "dry-run" else "plan"
        elif args.mode == "apply":
            missing = [flag for flag, value in (("--plan", args.plan), ("--approval", args.approval), ("--checkpoint", args.checkpoint)) if not value]
            if missing:
                raise ValueError("apply requires " + ", ".join(missing))
            if transfer:
                report = execute_transfer(
                    request,
                    load_json(args.plan),
                    load_json(args.approval),
                    build_adapters(request, args),
                    args.checkpoint,
                    poll_interval_seconds=args.poll_interval_seconds,
                    max_wait_seconds=args.max_wait_seconds,
                )
            else:
                report = execute_plan(
                    request,
                    load_json(args.plan),
                    load_json(args.approval),
                    build_adapters(request, args),
                    args.checkpoint,
                )
        elif transfer:
            if not args.plan:
                raise ValueError("--plan is required for {} verify (it carries the pre-transfer sample)".format(TRANSFER_OPERATION))
            checkpoint = load_json(args.checkpoint) if args.checkpoint and os.path.exists(args.checkpoint) else None
            report = verify_transfer(request, load_json(args.plan), build_adapters(request, args), checkpoint)
        else:
            report = verify_only(request, build_adapters(request, args))
    except Exception as exc:
        report = {
            "schema_version": 1,
            "record_type": "workspace_user_lifecycle_cli_error",
            "generated_at_utc": utc_now(),
            "mode": args.mode,
            "status": "refused",
            "error": sanitize_error(exc),
            "write_count": 0,
            "tenant_writes_performed": False,
        }
    if report.get("transfer_id"):
        print("transfer_id={}".format(report["transfer_id"]), file=sys.stderr)
    write_report(args.output, report)
    return 0 if report.get("status") in {
        "inventory_complete",
        "approval_required",
        "completed_and_verified",
        "verified_complete_no_write",
    } else 2


if __name__ == "__main__":
    sys.exit(main())
