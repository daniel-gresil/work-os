#!/usr/bin/env python3
"""Fail-closed, provider-neutral user offboarding orchestration.

Provider adapters own API calls. This module owns policy validation, exact-identity
checks, approval binding, ordered writes, checkpoints, read-back, and audit shape.
"""

from __future__ import annotations

import concurrent.futures
import copy
import datetime as dt
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Protocol

SCHEMA_VERSION = 1
PLATFORMS = ("google_workspace", "microsoft_365")
GOOGLE_LICENSE_PRODUCT_CATALOG = (
    "Google-Apps", "101068", "101047", "101034", "101031", "101037",
    "101038", "101054", "Google-Vault", "101001", "101005", "101052",
    "101050", "101049", "101036", "101043", "101033", "101039", "101040",
    "101035",
)
TERMINAL_SUCCESS = {"completed_and_verified", "verified_complete_no_write"}
WRITE_ACTIONS = {
    "google_workspace": ("suspend", "revoke_sessions", "remove_license", "delete_user"),
    "microsoft_365": ("block_sign_in", "revoke_sessions", "remove_licenses", "delete_user"),
}
# Google-only Drive ownership transfer through the Admin SDK Data Transfer API.
# The application ID and privacy levels are fixed by policy, bound into the
# approved plan, and re-asserted by the adapter before the single write.
TRANSFER_OPERATION = "transfer_drive_ownership"
TRANSFER_ACTION_ID = "google:transfer_drive_ownership"
DRIVE_TRANSFER_APPLICATION_ID = "55656082996"
DRIVE_TRANSFER_PARAMS = [{"key": "PRIVACY_LEVEL", "value": ["SHARED", "PRIVATE"]}]
TRANSFER_SAMPLE_SIZE = 25
TRANSFER_DEFAULT_POLL_INTERVAL_SECONDS = 30
TRANSFER_DEFAULT_MAX_WAIT_SECONDS = 1800
TRANSFER_MAX_WAIT_CEILING_SECONDS = 7200
TRANSFER_TERMINAL_STATUSES = {"COMPLETED", "FAILED"}


class LifecycleError(RuntimeError):
    pass


class ProviderAdapter(Protocol):
    name: str

    def inventory(self, request: Mapping[str, Any]) -> Dict[str, Any]: ...

    def apply_action(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]: ...

    def verify_action(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]: ...

    def verify_terminal(self, request: Mapping[str, Any]) -> Dict[str, Any]: ...


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def plan_digest(plan: Mapping[str, Any]) -> str:
    value = copy.deepcopy(dict(plan))
    value.pop("plan_digest", None)
    value.pop("mode", None)
    # This display-only field is derived from the digest and therefore cannot
    # itself participate in the digest without creating a circular value.
    value.pop("required_confirmation", None)
    return hashlib.sha256(canonical_json(value)).hexdigest()


def confirmation_for(plan: Mapping[str, Any]) -> str:
    target = str((plan.get("target") or {}).get("email", "")).lower()
    if plan.get("operation") == TRANSFER_OPERATION:
        destination = str(((plan.get("transfer") or {}).get("destination") or {}).get("email", "")).lower()
        return "APPLY-DRIVE-TRANSFER:{}->{}:{}".format(target, destination, plan_digest(plan))
    return "APPLY-OFFBOARD:{}:{}".format(target, plan_digest(plan))


def atomic_write_json(path: str, value: Mapping[str, Any]) -> None:
    destination = os.path.abspath(path)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".lifecycle-", suffix=".json", dir=os.path.dirname(destination))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise LifecycleError("{} must contain a JSON object".format(path))
    return value


def sanitize_error(exc: BaseException) -> str:
    text = str(exc)
    lowered = text.lower()
    if any(marker in lowered for marker in ("access_token", "refresh_token", "client_secret", "private_key")):
        return "credential-bearing error redacted"
    return text[:800]


def validate_request(request: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if request.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be {}".format(SCHEMA_VERSION))
    transfer = request.get("operation") == TRANSFER_OPERATION
    if request.get("operation") not in {"remove", "add", TRANSFER_OPERATION}:
        errors.append("operation must be remove, add, or {}".format(TRANSFER_OPERATION))
    target = request.get("target") or {}
    email = str(target.get("email", "")).strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        errors.append("target.email must be an exact email address")
    platforms = request.get("platforms") or {}
    selected = 0
    for name in PLATFORMS:
        config = platforms.get(name) or {}
        disposition = config.get("disposition", "skip")
        if disposition not in {"present", "absent", "skip"}:
            errors.append("platforms.{}.disposition must be present, absent, or skip".format(name))
            continue
        if disposition != "skip":
            selected += 1
        tenant_key = "customer_id" if name == "google_workspace" else "tenant_id"
        if disposition in {"present", "absent"} and not config.get(tenant_key):
            errors.append("platforms.{}.{} is required when {}".format(name, tenant_key, disposition))
        if disposition == "present":
            if not config.get("immutable_id"):
                errors.append("platforms.{}.immutable_id is required when present".format(name))
            if name == "google_workspace" and not transfer:
                products = config.get("license_product_ids")
                if not isinstance(products, list) or not products or any(not str(item).strip() for item in products):
                    errors.append("platforms.google_workspace.license_product_ids must be a non-empty explicit list")
                elif len({str(item) for item in products}) != len(products):
                    errors.append("platforms.google_workspace.license_product_ids must not contain duplicates")
                if config.get("license_product_catalog_complete") is not True:
                    errors.append("platforms.google_workspace.license_product_catalog_complete must explicitly be true")
            if name == "google_workspace" and not transfer and not isinstance(config.get("expected_licenses"), list):
                errors.append("platforms.google_workspace.expected_licenses must explicitly be a list")
            if name == "microsoft_365" and not isinstance(config.get("expected_license_sku_ids"), list):
                errors.append("platforms.microsoft_365.expected_license_sku_ids must explicitly be a list")
        if disposition == "absent" and config.get("immutable_id"):
            errors.append("platforms.{} cannot be absent and carry immutable_id".format(name))
    if selected == 0:
        errors.append("at least one platform must be present or explicitly absent")
    if transfer:
        errors.extend(validate_transfer_request(request))
    if request.get("operation") == "add":
        add = request.get("provisioning") or {}
        if not add.get("display_name"):
            errors.append("provisioning.display_name is required for add")
        if not add.get("initial_secret_env"):
            errors.append("provisioning.initial_secret_env is required; passwords never belong in the request")
    return errors


def validate_transfer_request(request: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    platforms = request.get("platforms") or {}
    google = platforms.get("google_workspace") or {}
    if google.get("disposition") != "present":
        errors.append("platforms.google_workspace.disposition must be present for {}".format(TRANSFER_OPERATION))
    if (platforms.get("microsoft_365") or {}).get("disposition", "skip") != "skip":
        errors.append("{} is Google-only; platforms.microsoft_365.disposition must be skip".format(TRANSFER_OPERATION))
    source_email = str((request.get("target") or {}).get("email", "")).strip().lower()
    destination = (request.get("transfer") or {}).get("destination") or {}
    destination_email = str(destination.get("email", "")).strip().lower()
    destination_id = str(destination.get("immutable_id", "")).strip()
    if "@" not in destination_email or destination_email.startswith("@") or destination_email.endswith("@"):
        errors.append("transfer.destination.email must be an exact email address")
    if not destination_id:
        errors.append("transfer.destination.immutable_id is required")
    if destination_email == source_email or (destination_id and destination_id == str(google.get("immutable_id", ""))):
        errors.append("transfer.destination must be a different user than the source")
    policy = request.get("policy") or {}
    if not str(policy.get("approver", "")).strip():
        errors.append("policy.approver is required")
    if not isinstance(policy.get("accepted_unknowns"), list):
        errors.append("policy.accepted_unknowns must explicitly be a list")
    return errors


def transfer_guard_errors(request: Mapping[str, Any], inventory: Mapping[str, Any]) -> List[str]:
    """Fail closed on tenant, identity, suspension, or completeness drift for a transfer."""
    errors: List[str] = []
    config = (request.get("platforms") or {}).get("google_workspace") or {}
    destination = (request.get("transfer") or {}).get("destination") or {}
    accepted_unknowns = (request.get("policy") or {}).get("accepted_unknowns")
    if not isinstance(accepted_unknowns, list):
        accepted_unknowns = []
    item = (inventory.get("providers") or {}).get("google_workspace") or {}
    if item.get("write_count", 0) != 0:
        errors.append("google_workspace inventory reported writes")
    if item.get("complete") is not True:
        errors.append("google_workspace inventory is incomplete")
        return errors
    unaccepted = sorted(set(item.get("limitations") or []) - set(accepted_unknowns))
    if unaccepted:
        errors.append("google_workspace has unaccepted inventory limitations: {}".format(", ".join(unaccepted)))
    identity = item.get("identity") or {}
    expected = (
        ("source", str((request.get("target") or {}).get("email", "")).lower(), str(config.get("immutable_id", "")), True),
        ("destination", str(destination.get("email", "")).lower(), str(destination.get("immutable_id", "")), False),
    )
    for role, email, immutable_id, suspended in expected:
        matches = identity.get(role + "_exact_matches") or []
        if len(matches) != 1:
            errors.append("google_workspace {} user identity is absent or ambiguous".format(role))
            continue
        match = matches[0]
        if str(match.get("email", "")).lower() != email:
            errors.append("google_workspace {} exact match email drifted".format(role))
        if str(match.get("immutable_id", "")) != immutable_id:
            errors.append("google_workspace {} immutable identity drifted".format(role))
        if str(match.get("customer_id", "")) != str(config.get("customer_id", "")):
            errors.append("google_workspace {} user is not in the approved customer".format(role))
        if match.get("suspended") is not suspended:
            errors.append(
                "google_workspace source user is not suspended" if role == "source"
                else "google_workspace destination user is suspended or its state is unknown"
            )
    if identity.get("non_user_matches"):
        errors.append("google_workspace source or destination address resolves to a non-user recipient")
    if not isinstance((item.get("drive") or {}).get("owned_nontrashed_count"), int):
        errors.append("google_workspace Drive ownership count is unknown")
    return errors


def validate_remove_policy(request: Mapping[str, Any]) -> List[str]:
    if request.get("operation") != "remove":
        return []
    errors: List[str] = []
    policy = request.get("policy") or {}
    for field in ("mail", "files"):
        if policy.get(field) not in {"delete", "transfer", "retain"}:
            errors.append("policy.{} must be delete, transfer, or retain".format(field))
    if policy.get("legal_hold") not in {"none_known", "present"}:
        errors.append("policy.legal_hold must explicitly be none_known or present")
    if policy.get("legal_hold") == "present" and policy.get("deletion") == "immediate":
        errors.append("immediate deletion is forbidden while policy.legal_hold=present")
    if policy.get("deletion") not in {"immediate", "delayed"}:
        errors.append("policy.deletion must be immediate or delayed")
    if policy.get("license") not in {"release_on_delete", "remove_then_delete", "retain"}:
        errors.append("policy.license must be release_on_delete, remove_then_delete, or retain")
    if not str(policy.get("approver", "")).strip():
        errors.append("policy.approver is required")
    if policy.get("mail") == "transfer" or policy.get("files") == "transfer":
        destination = str(policy.get("transfer_destination", "")).strip().lower()
        if "@" not in destination:
            errors.append("policy.transfer_destination is required for transfer")
    if policy.get("deletion") == "immediate" and (policy.get("mail") == "retain" or policy.get("files") == "retain"):
        errors.append("immediate deletion conflicts with retain policy")
    if policy.get("deletion") == "immediate" and policy.get("license") == "retain":
        errors.append("immediate deletion conflicts with retained license policy")
    return errors


def inventory_material(item: Mapping[str, Any], resume: bool = False) -> Dict[str, Any]:
    """Select material provider state, optionally ignoring expected mutations."""
    material = {
        key: copy.deepcopy(item.get(key))
        for key in (
            "complete",
            "customer_id",
            "tenant_id",
            "identity",
            "groups",
            "roles",
            "licenses",
            "drive",
            "mailbox",
            "deleted_exact_matches",
            "deleted_user_ids",
            "protected_same_localpart",
            "limitations",
            "errors",
        )
        if key in item
    }
    if resume:
        # Suspension, sign-in blocking, and license removal are expected
        # mid-plan mutations. Preserve identities and dependencies, but ignore
        # only those mutable fields.
        material.pop("licenses", None)
        identity = material.get("identity") or {}
        for match in identity.get("exact_matches") or []:
            for key in ("suspended", "account_enabled", "assigned_licenses"):
                match.pop(key, None)
    return material


def inventory_signature(item: Mapping[str, Any], resume: bool = False) -> str:
    """Hash material provider state while excluding timestamps and narration."""
    material = inventory_material(item, resume=resume)
    return hashlib.sha256(canonical_json(material)).hexdigest()


def _inventory_one(name: str, adapter: ProviderAdapter, request: Mapping[str, Any], method: str = "inventory") -> Dict[str, Any]:
    started = utc_now()
    try:
        result = getattr(adapter, method)(request)
        if not isinstance(result, dict):
            raise LifecycleError("adapter returned non-object inventory")
        return {"platform": name, "started_at_utc": started, "completed_at_utc": utc_now(), **result}
    except Exception as exc:
        return {
            "platform": name,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "status": "error",
            "complete": False,
            "error": sanitize_error(exc),
            "write_count": 0,
        }


def inventory_all(
    request: Mapping[str, Any], adapters: Mapping[str, ProviderAdapter], max_workers: int = 2
) -> Dict[str, Any]:
    request_errors = validate_request(request)
    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_inventory",
        "generated_at_utc": utc_now(),
        "mode": "inventory",
        "target": copy.deepcopy(request.get("target") or {}),
        "request_errors": request_errors,
        "providers": {},
        "write_count": 0,
        "tenant_writes_performed": False,
    }
    if request_errors:
        report["status"] = "refused"
        return report
    wanted = {
        name: adapters[name]
        for name in PLATFORMS
        if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip" and name in adapters
    }
    missing = [
        name
        for name in PLATFORMS
        if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip" and name not in adapters
    ]
    if missing:
        report["status"] = "refused"
        report["request_errors"] = ["missing adapter for {}".format(name) for name in missing]
        return report
    bounded = max(1, min(int(max_workers), 4, len(wanted) or 1))
    method = "transfer_inventory" if request.get("operation") == TRANSFER_OPERATION else "inventory"
    with concurrent.futures.ThreadPoolExecutor(max_workers=bounded) as executor:
        futures = {executor.submit(_inventory_one, name, adapter, request, method): name for name, adapter in wanted.items()}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            report["providers"][result["platform"]] = result
    failures = inventory_guard_errors(request, report)
    report["guard_errors"] = failures
    report["status"] = "inventory_complete" if not failures else "inventory_incomplete"
    return report


def inventory_guard_errors(request: Mapping[str, Any], inventory: Mapping[str, Any]) -> List[str]:
    if request.get("operation") == TRANSFER_OPERATION:
        return transfer_guard_errors(request, inventory)
    errors: List[str] = []
    target = str((request.get("target") or {}).get("email", "")).lower()
    accepted_unknowns = (request.get("policy") or {}).get("accepted_unknowns")
    if not isinstance(accepted_unknowns, list):
        errors.append("policy.accepted_unknowns must explicitly be a list")
        accepted_unknowns = []
    for name in PLATFORMS:
        expected = (request.get("platforms") or {}).get(name, {}).get("disposition", "skip")
        if expected == "skip":
            continue
        item = (inventory.get("providers") or {}).get(name) or {}
        if item.get("write_count", 0) != 0:
            errors.append("{} inventory reported writes".format(name))
        if item.get("complete") is not True:
            errors.append("{} inventory is incomplete".format(name))
            continue
        unaccepted = sorted(set(item.get("limitations") or []) - set(accepted_unknowns))
        if unaccepted:
            errors.append("{} has unaccepted inventory limitations: {}".format(name, ", ".join(unaccepted)))
        resolution = item.get("identity") or {}
        exact = resolution.get("exact_matches") or []
        non_user = resolution.get("non_user_matches") or []
        if expected == "present":
            if len(exact) != 1 or non_user:
                errors.append("{} exact user identity is ambiguous or is a non-user recipient".format(name))
                continue
            match = exact[0]
            config = (request.get("platforms") or {}).get(name) or {}
            if str(match.get("email", "")).lower() != target:
                errors.append("{} exact match email drifted".format(name))
            if str(match.get("immutable_id", "")) != str(config.get("immutable_id", "")):
                errors.append("{} immutable identity drifted".format(name))
            tenant_key = "customer_id" if name == "google_workspace" else "tenant_id"
            if str(item.get(tenant_key, "")) != str(config.get(tenant_key, "")):
                errors.append("{} {} drifted".format(name, tenant_key))
            if name == "google_workspace":
                actual_licenses = {
                    (str(value.get("product_id")), str(value.get("sku_id")))
                    for value in item.get("licenses") or []
                }
                expected_licenses = {
                    (str(value.get("product_id")), str(value.get("sku_id")))
                    for value in config.get("expected_licenses") or []
                }
                if actual_licenses != expected_licenses:
                    errors.append("google_workspace license set does not match the approved request")
            if name == "microsoft_365":
                actual_skus = {
                    str(value.get("skuId"))
                    for value in match.get("assigned_licenses") or []
                }
                expected_skus = {str(value) for value in config.get("expected_license_sku_ids") or []}
                if actual_skus != expected_skus:
                    errors.append("microsoft_365 license set does not match the approved request")
        elif expected == "absent":
            config = (request.get("platforms") or {}).get(name) or {}
            tenant_key = "customer_id" if name == "google_workspace" else "tenant_id"
            if str(item.get(tenant_key, "")) != str(config.get(tenant_key, "")):
                errors.append("{} {} drifted".format(name, tenant_key))
            if exact or non_user:
                errors.append("{} was declared absent but an exact recipient exists".format(name))
    return errors


def _action(
    action_id: str,
    provider: str,
    verb: str,
    risk: str,
    verification: str,
    **approved_parameters: Any,
) -> Dict[str, Any]:
    return {
        "action_id": action_id,
        "provider": provider,
        "verb": verb,
        "risk": risk,
        "verification": verification,
        "authorization": "pending_explicit_plan_approval",
        **approved_parameters,
    }


def build_plan(request: Mapping[str, Any], inventory: Mapping[str, Any]) -> Dict[str, Any]:
    if request.get("operation") == TRANSFER_OPERATION:
        return build_transfer_plan(request, inventory)
    errors = validate_request(request) + validate_remove_policy(request) + inventory_guard_errors(request, inventory)
    plan: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_plan",
        "generated_at_utc": utc_now(),
        "operation": request.get("operation"),
        "target": copy.deepcopy(request.get("target") or {}),
        "platforms": copy.deepcopy(request.get("platforms") or {}),
        "policy": copy.deepcopy(request.get("policy") or {}),
        "inventory_signatures": {
            name: inventory_signature(item)
            for name, item in (inventory.get("providers") or {}).items()
        },
        "resume_inventory_signatures": {
            name: inventory_signature(item, resume=True)
            for name, item in (inventory.get("providers") or {}).items()
        },
        "actions": [],
        "guard_errors": errors,
        "write_count": 0,
        "tenant_writes_performed": False,
    }
    if request.get("operation") == "add":
        errors.append("add is plan-only in this skill release; provider provisioning writes require a separately reviewed extension")
    if request.get("operation") == "remove" and not errors:
        policy = request.get("policy") or {}
        if policy.get("mail") == "transfer" or policy.get("files") == "transfer":
            errors.append("transfer execution is not built into the fast-path runner; run operation={} first, verify it, then plan deletion".format(TRANSFER_OPERATION))
        if policy.get("deletion") == "delayed":
            errors.append("delayed deletion scheduling is not built into the runner; inventory and plan remain read-only")
    if not errors:
        for name in PLATFORMS:
            config = (request.get("platforms") or {}).get(name) or {}
            if config.get("disposition", "skip") != "present":
                continue
            if name == "google_workspace":
                plan["actions"].extend([
                    _action("google:suspend", name, "suspend", "reversible", "exact user read shows suspended=true"),
                    _action("google:revoke_sessions", name, "revoke_sessions", "reversible", "HTTP 2xx plus suspended read-back; provider exposes no session-state field"),
                ])
                if (request.get("policy") or {}).get("license") == "remove_then_delete":
                    plan["actions"].append(_action(
                        "google:remove_license",
                        name,
                        "remove_license",
                        "destructive",
                        "exact assignment absent",
                        expected_licenses=copy.deepcopy(config.get("expected_licenses") or []),
                    ))
                plan["actions"].append(_action("google:delete", name, "delete_user", "critical", "active ID/email absent, exact tombstone present, license listing complete and absent"))
            else:
                microsoft_actions = [
                    _action("microsoft:block_sign_in", name, "block_sign_in", "reversible", "exact object read shows accountEnabled=false"),
                    _action("microsoft:revoke_sessions", name, "revoke_sessions", "reversible", "provider accepted revoke and account remains blocked"),
                ]
                if config.get("expected_license_sku_ids") and (request.get("policy") or {}).get("license") == "remove_then_delete":
                    microsoft_actions.append(_action(
                        "microsoft:remove_licenses",
                        name,
                        "remove_licenses",
                        "destructive",
                        "exact object has zero assigned licenses",
                        expected_license_sku_ids=copy.deepcopy(config["expected_license_sku_ids"]),
                    ))
                microsoft_actions.append(_action("microsoft:delete", name, "delete_user", "critical", "active object absent and deleted object present"))
                plan["actions"].extend(microsoft_actions)
    plan["status"] = "blocked" if errors else "approval_required"
    plan["plan_digest"] = plan_digest(plan)
    plan["required_confirmation"] = confirmation_for(plan)
    return plan


def validate_approval(plan: Mapping[str, Any], approval: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    actual_digest = plan_digest(plan)
    if plan.get("plan_digest") != actual_digest:
        errors.append("plan digest is invalid or plan drifted")
    if plan.get("status") != "approval_required" or plan.get("guard_errors"):
        errors.append("plan is not eligible for approval")
    approver = str((plan.get("policy") or {}).get("approver", ""))
    if approval.get("plan_digest") != actual_digest:
        errors.append("approval is not bound to this plan digest")
    if str(approval.get("approved_by", "")) != approver:
        errors.append("approval identity does not match policy.approver")
    if approval.get("decision") != "approve":
        errors.append("approval.decision must be approve")
    if approval.get("confirmation") != confirmation_for(plan):
        errors.append("literal confirmation is missing or incorrect")
    return errors


def safe_verify_action(adapter: ProviderAdapter, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        result = getattr(adapter, "verify_action")(action, request)
        return result if isinstance(result, dict) else {"verified": False, "error": "adapter returned non-object verification"}
    except Exception as exc:
        return {"verified": False, "error": sanitize_error(exc)}


def safe_verify_terminal(adapter: ProviderAdapter, request: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        result = getattr(adapter, "verify_terminal")(request)
        return result if isinstance(result, dict) else {"verified": False, "error": "adapter returned non-object terminal verification"}
    except Exception as exc:
        return {"verified": False, "error": sanitize_error(exc)}


def validate_request_matches_plan(request: Mapping[str, Any], plan: Mapping[str, Any]) -> List[str]:
    """Prevent an approved plan from being executed with retargeted inputs."""
    errors: List[str] = []
    for key in ("operation", "target", "platforms", "policy", "transfer"):
        if canonical_json(request.get(key)) != canonical_json(plan.get(key)):
            errors.append("request.{} does not match the approved plan".format(key))
    return errors


def selected_adapter_errors(
    request: Mapping[str, Any], adapters: Mapping[str, ProviderAdapter]
) -> List[str]:
    """Require an adapter for every selected provider, including absent no-ops."""
    return [
        "missing adapter for {}".format(name)
        for name in PLATFORMS
        if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip"
        and name not in adapters
    ]


def initial_checkpoint(plan: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_checkpoint",
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "plan_digest": plan_digest(plan),
        "actions": {},
        "write_count": 0,
    }


def load_checkpoint(plan: Mapping[str, Any], checkpoint_path: str) -> "tuple[Dict[str, Any], List[str]]":
    checkpoint = load_json(checkpoint_path) if os.path.exists(checkpoint_path) else initial_checkpoint(plan)
    if checkpoint.get("plan_digest") != plan_digest(plan):
        return checkpoint, ["checkpoint belongs to a different plan"]
    if not isinstance(checkpoint.setdefault("actions", {}), dict):
        return checkpoint, ["checkpoint.actions must be an object"]
    return checkpoint, []


def execute_plan(
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    adapters: Mapping[str, ProviderAdapter],
    checkpoint_path: str,
) -> Dict[str, Any]:
    approval_errors = (
        validate_approval(plan, approval)
        + validate_request_matches_plan(request, plan)
        + selected_adapter_errors(request, adapters)
    )
    if plan.get("operation") == TRANSFER_OPERATION:
        approval_errors.append("{} plans execute only through execute_transfer".format(TRANSFER_OPERATION))
    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_audit",
        "generated_at_utc": utc_now(),
        "mode": "apply",
        "operation": plan.get("operation"),
        "target": copy.deepcopy(plan.get("target") or {}),
        "plan_digest": plan_digest(plan),
        "approval_errors": approval_errors,
        "actions": [],
        "write_count": 0,
        "tenant_writes_performed": False,
        "human_review_required": False,
    }
    if approval_errors:
        report["status"] = "refused"
        return report
    checkpoint, checkpoint_errors = load_checkpoint(plan, checkpoint_path)
    if checkpoint_errors:
        report["status"] = "refused"
        report["approval_errors"] = checkpoint_errors
        return report
    checkpoint_actions = checkpoint["actions"]
    planned_actions = plan.get("actions") or []
    if planned_actions and all(
        (checkpoint_actions.get(str(item["action_id"])) or {}).get("status") == "verified"
        for item in planned_actions
    ):
        terminal = {
            name: safe_verify_terminal(adapter, request)
            for name, adapter in adapters.items()
            if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip"
        }
        report["terminal_verification"] = terminal
        verified = bool(terminal) and all(item.get("verified") is True for item in terminal.values())
        report["status"] = "verified_complete_no_write" if verified else "partial_failure"
        report["human_review_required"] = not verified
        return report
    # If deletion may already have been sent, terminal read-back is the only
    # safe recovery path. Do not require an active-user preflight or resend.
    for action in planned_actions:
        if action.get("verb") != "delete_user":
            continue
        previous = checkpoint_actions.get(str(action["action_id"])) or {}
        if previous.get("status") in {"about_to_write", "write_sent", "verification_failed", "write_error"}:
            adapter = adapters.get(str(action["provider"]))
            verification = safe_verify_terminal(adapter, request) if adapter is not None else {"verified": False}
            report["actions"].append({
                **action,
                "status": "recovered_by_terminal_readback_no_write" if verification.get("verified") else "indeterminate_prior_write_not_retried",
                "resume_verification": verification,
            })
            if verification.get("verified") is not True:
                report["status"] = "partial_failure"
                report["human_review_required"] = True
                return report
            checkpoint["actions"][str(action["action_id"])] = {"status": "verified", "verified_at_utc": utc_now()}
            checkpoint["updated_at_utc"] = utc_now()
            atomic_write_json(checkpoint_path, checkpoint)
    if planned_actions and all(
        (checkpoint["actions"].get(str(item["action_id"])) or {}).get("status") == "verified"
        for item in planned_actions
    ):
        terminal = {
            name: safe_verify_terminal(adapter, request)
            for name, adapter in adapters.items()
            if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip"
        }
        report["terminal_verification"] = terminal
        verified = bool(terminal) and all(item.get("verified") is True for item in terminal.values())
        report["status"] = "verified_complete_no_write" if verified else "partial_failure"
        report["human_review_required"] = not verified
        return report
    # Approval is bound to an inventory snapshot. Re-read every selected
    # provider before a new write. During resume, ignore only expected mutable
    # account/license fields while retaining dependency and identity guards.
    fresh_inventory = inventory_all(request, adapters)
    report["fresh_preflight"] = fresh_inventory
    completed_deleted_providers = {
        str(action["provider"])
        for action in planned_actions
        if action.get("verb") == "delete_user"
        and (checkpoint_actions.get(str(action["action_id"])) or {}).get("status") == "verified"
    }
    fresh_errors = [
        error
        for error in (fresh_inventory.get("guard_errors") or [])
        if not any(str(error).startswith(provider + " ") for provider in completed_deleted_providers)
    ]
    expected_license_changes = {
        "google:remove_license": "google_workspace license set does not match the approved request",
        "microsoft:remove_licenses": "microsoft_365 license set does not match the approved request",
    }
    for action_id, expected_error in expected_license_changes.items():
        if (checkpoint_actions.get(action_id) or {}).get("status") == "verified":
            fresh_errors = [error for error in fresh_errors if error != expected_error]
    partial_resume = bool(checkpoint_actions)
    approved_signatures = (
        plan.get("resume_inventory_signatures") if partial_resume else plan.get("inventory_signatures")
    ) or {}
    for name, item in (fresh_inventory.get("providers") or {}).items():
        if name in completed_deleted_providers:
            continue
        if approved_signatures.get(name) != inventory_signature(item, resume=partial_resume):
            fresh_errors.append("{} material inventory drifted after approval".format(name))
    if fresh_errors:
        report["status"] = "refused"
        report["fresh_preflight_errors"] = fresh_errors
        return report
    for action in plan.get("actions") or []:
        action_id = str(action["action_id"])
        provider = str(action["provider"])
        adapter = adapters.get(provider)
        if adapter is None:
            report["status"] = "partial_failure"
            report["human_review_required"] = True
            report["actions"].append({**action, "status": "missing_adapter"})
            return report
        previous = (checkpoint.get("actions") or {}).get(action_id) or {}
        audit_action = {**action, "started_at_utc": utc_now()}
        report["actions"].append(audit_action)
        if previous.get("status") == "verified":
            if provider in completed_deleted_providers:
                audit_action["status"] = "already_verified_by_provider_terminal_delete_no_write"
                audit_action["completed_at_utc"] = utc_now()
                continue
            verification = safe_verify_action(adapter, action, request)
            audit_action["resume_verification"] = verification
            if verification.get("verified") is True:
                audit_action["status"] = "already_verified_no_write"
                audit_action["completed_at_utc"] = utc_now()
                continue
            audit_action["status"] = "checkpoint_verification_failed"
            report["status"] = "partial_failure"
            report["human_review_required"] = True
            return report
        if previous.get("status") in {"about_to_write", "write_sent", "verification_failed", "write_error"}:
            # A crash can occur after the provider received the request but
            # before `write_sent` was persisted. Never fall through and resend.
            # Session revocation has no unique state read-back, so it may be
            # recovered only when the checkpoint captured an accepted response.
            if action.get("verb") == "revoke_sessions" and not (previous.get("write") or {}).get("accepted"):
                audit_action["status"] = "indeterminate_prior_write_not_retried"
                report["status"] = "partial_failure"
                report["human_review_required"] = True
                return report
            verification = safe_verify_action(adapter, action, request)
            audit_action["resume_verification"] = verification
            if verification.get("verified") is True:
                checkpoint["actions"][action_id] = {"status": "verified", "verified_at_utc": utc_now()}
                checkpoint["updated_at_utc"] = utc_now()
                atomic_write_json(checkpoint_path, checkpoint)
                audit_action["status"] = "recovered_by_readback_no_write"
                audit_action["completed_at_utc"] = utc_now()
                continue
            audit_action["status"] = "indeterminate_prior_write_not_retried"
            report["status"] = "partial_failure"
            report["human_review_required"] = True
            return report
        if action.get("verb") == "delete_user":
            delete_preflight = inventory_all(request, adapters)
            audit_action["immediate_predelete_inventory"] = delete_preflight
            delete_errors = [
                error
                for error in (delete_preflight.get("guard_errors") or [])
                if not any(str(error).startswith(provider + " ") for provider in completed_deleted_providers)
            ]
            for completed_action, expected_error in expected_license_changes.items():
                if (checkpoint_actions.get(completed_action) or {}).get("status") == "verified":
                    delete_errors = [error for error in delete_errors if error != expected_error]
            approved_resume = plan.get("resume_inventory_signatures") or {}
            for name, item in (delete_preflight.get("providers") or {}).items():
                if name in completed_deleted_providers:
                    continue
                if approved_resume.get(name) != inventory_signature(item, resume=True):
                    delete_errors.append("{} material inventory drifted immediately before deletion".format(name))
            if delete_errors:
                audit_action["status"] = "predelete_drift_blocked"
                audit_action["guard_errors"] = delete_errors
                report["status"] = "partial_failure" if checkpoint_actions else "refused"
                report["human_review_required"] = bool(checkpoint_actions)
                return report
        checkpoint["actions"][action_id] = {"status": "about_to_write", "updated_at_utc": utc_now()}
        checkpoint["updated_at_utc"] = utc_now()
        atomic_write_json(checkpoint_path, checkpoint)
        try:
            write = adapter.apply_action(action, request)
        except Exception as exc:
            write = {"accepted": False, "error": sanitize_error(exc)}
        # Record the attempted provider call in the in-memory audit before any
        # subsequent checkpoint write can fail.
        report["write_count"] += 1
        report["tenant_writes_performed"] = True
        audit_action["write"] = write
        checkpoint["write_count"] = int(checkpoint.get("write_count", 0)) + 1
        checkpoint["actions"][action_id] = {"status": "write_sent", "write": write, "updated_at_utc": utc_now()}
        checkpoint["updated_at_utc"] = utc_now()
        try:
            atomic_write_json(checkpoint_path, checkpoint)
        except Exception as exc:
            audit_action["status"] = "write_sent_checkpoint_failed"
            audit_action["checkpoint_error"] = sanitize_error(exc)
            report["status"] = "partial_failure"
            report["human_review_required"] = True
            return report
        verification = safe_verify_action(adapter, action, request)
        audit_action["verification"] = verification
        if write.get("accepted") is True and verification.get("verified") is True:
            checkpoint["actions"][action_id] = {"status": "verified", "write": write, "verification": verification, "verified_at_utc": utc_now()}
            checkpoint["updated_at_utc"] = utc_now()
            try:
                atomic_write_json(checkpoint_path, checkpoint)
            except Exception as exc:
                audit_action["status"] = "verified_but_checkpoint_failed"
                audit_action["checkpoint_error"] = sanitize_error(exc)
                report["status"] = "partial_failure"
                report["human_review_required"] = True
                return report
            audit_action["status"] = "verified"
            audit_action["completed_at_utc"] = utc_now()
            continue
        checkpoint["actions"][action_id]["status"] = "verification_failed" if write.get("accepted") else "write_error"
        checkpoint["actions"][action_id]["verification"] = verification
        checkpoint["updated_at_utc"] = utc_now()
        try:
            atomic_write_json(checkpoint_path, checkpoint)
        except Exception as exc:
            audit_action["checkpoint_error"] = sanitize_error(exc)
        audit_action["status"] = checkpoint["actions"][action_id]["status"]
        audit_action["completed_at_utc"] = utc_now()
        report["status"] = "partial_failure"
        report["human_review_required"] = True
        return report
    terminal: Dict[str, Any] = {}
    for name, adapter in adapters.items():
        if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip":
            terminal[name] = safe_verify_terminal(adapter, request)
    report["terminal_verification"] = terminal
    report["status"] = "completed_and_verified" if terminal and all(item.get("verified") is True for item in terminal.values()) else "partial_failure"
    report["human_review_required"] = report["status"] != "completed_and_verified"
    return report


def verify_only(request: Mapping[str, Any], adapters: Mapping[str, ProviderAdapter]) -> Dict[str, Any]:
    adapter_errors = selected_adapter_errors(request, adapters)
    results = {
        name: safe_verify_terminal(adapter, request)
        for name, adapter in adapters.items()
        if (request.get("platforms") or {}).get(name, {}).get("disposition", "skip") != "skip"
    }
    verified = not adapter_errors and bool(results) and all(item.get("verified") is True for item in results.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_verification",
        "generated_at_utc": utc_now(),
        "mode": "verify",
        "target": copy.deepcopy(request.get("target") or {}),
        "providers": results,
        "adapter_errors": adapter_errors,
        "write_count": 0,
        "tenant_writes_performed": False,
        "status": "verified_complete_no_write" if verified else "verification_failed",
    }


def build_transfer_plan(request: Mapping[str, Any], inventory: Mapping[str, Any]) -> Dict[str, Any]:
    """Zero-write plan binding both immutable IDs, the inventory signature/sample, and fixed Drive params."""
    errors = validate_request(request) + transfer_guard_errors(request, inventory)
    config = (request.get("platforms") or {}).get("google_workspace") or {}
    destination = (request.get("transfer") or {}).get("destination") or {}
    drive = ((inventory.get("providers") or {}).get("google_workspace") or {}).get("drive") or {}
    plan: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_plan",
        "generated_at_utc": utc_now(),
        "operation": TRANSFER_OPERATION,
        "target": copy.deepcopy(request.get("target") or {}),
        "platforms": copy.deepcopy(request.get("platforms") or {}),
        "transfer": copy.deepcopy(request.get("transfer") or {}),
        "policy": copy.deepcopy(request.get("policy") or {}),
        "inventory_signatures": {
            name: inventory_signature(item)
            for name, item in (inventory.get("providers") or {}).items()
        },
        "pre_transfer_inventory": {
            key: copy.deepcopy(drive.get(key))
            for key in (
                "query", "owned_nontrashed_count", "total_reported_bytes", "objects_without_reported_size",
                "by_type", "sample", "sample_size", "sample_selection",
            )
        },
        "actions": [],
        "guard_errors": errors,
        "write_count": 0,
        "tenant_writes_performed": False,
    }
    if not errors:
        plan["actions"].append(_action(
            TRANSFER_ACTION_ID,
            "google_workspace",
            "transfer_drive_ownership",
            "critical",
            "Data Transfer overallTransferStatusCode completed; fresh Drive listing shows zero source-owned non-trashed objects; destination owns every sampled pre-transfer file",
            old_owner_user_id=str(config.get("immutable_id")),
            new_owner_user_id=str(destination.get("immutable_id")),
            source_email=str((request.get("target") or {}).get("email", "")).lower(),
            destination_email=str(destination.get("email", "")).lower(),
            customer_id=str(config.get("customer_id")),
            application_id=DRIVE_TRANSFER_APPLICATION_ID,
            application_transfer_params=copy.deepcopy(DRIVE_TRANSFER_PARAMS),
        ))
    plan["status"] = "blocked" if errors else "approval_required"
    plan["plan_digest"] = plan_digest(plan)
    plan["required_confirmation"] = confirmation_for(plan)
    return plan


def _transfer_plan_errors(plan: Mapping[str, Any]) -> List[str]:
    actions = plan.get("actions") or []
    if plan.get("operation") != TRANSFER_OPERATION:
        return ["plan is not a {} plan".format(TRANSFER_OPERATION)]
    if len(actions) != 1 or actions[0].get("action_id") != TRANSFER_ACTION_ID:
        return ["plan does not contain exactly the approved transfer action"]
    return []


def transfer_allowlist_errors(action: Mapping[str, Any], request: Mapping[str, Any]) -> List[str]:
    """Only the approved source/destination immutable IDs and the fixed Drive application/params may be submitted."""
    config = (request.get("platforms") or {}).get("google_workspace") or {}
    destination = (request.get("transfer") or {}).get("destination") or {}
    expected = {
        "provider": "google_workspace",
        "verb": TRANSFER_OPERATION,
        "old_owner_user_id": str(config.get("immutable_id")),
        "new_owner_user_id": str(destination.get("immutable_id")),
        "customer_id": str(config.get("customer_id")),
        "application_id": DRIVE_TRANSFER_APPLICATION_ID,
        "application_transfer_params": DRIVE_TRANSFER_PARAMS,
    }
    return [
        "action.{} is outside the approved exact-ID allowlist".format(key)
        for key, value in expected.items()
        if canonical_json(action.get(key)) != canonical_json(value)
    ]


def _safe_transfer_verify(adapter: Any, plan: Mapping[str, Any], request: Mapping[str, Any], transfer_id: Optional[str]) -> Dict[str, Any]:
    try:
        result = adapter.transfer_verify(plan, request, transfer_id)
        if not isinstance(result, dict):
            return {"verified": False, "error": "adapter returned non-object transfer verification"}
    except Exception as exc:
        return {"verified": False, "error": sanitize_error(exc)}
    # Adapter proves Drive facts; the engine re-applies identity/suspension guards.
    guard_errors = transfer_guard_errors(request, {"providers": {"google_workspace": result.get("inventory") or {}}})
    result["guard_errors"] = guard_errors
    result["verified"] = result.get("verified") is True and not guard_errors
    return result


def poll_transfer(
    adapter: Any,
    transfer_id: str,
    poll_interval_seconds: int,
    max_wait_seconds: int,
    sleep: Any = time.sleep,
    clock: Any = time.monotonic,
) -> Dict[str, Any]:
    """GET transfers.get until COMPLETED/FAILED or the bounded wait elapses (then PENDING)."""
    started = clock()
    polls = 0
    while True:
        polls += 1
        try:
            last = adapter.transfer_status(transfer_id)
        except Exception as exc:
            last = {"overall_status": "UNKNOWN", "error": sanitize_error(exc)}
        provider_status = str(last.get("overall_status", "UNKNOWN")).upper()
        elapsed = clock() - started
        if provider_status in TRANSFER_TERMINAL_STATUSES or elapsed >= max_wait_seconds:
            return {
                "overall_status": provider_status if provider_status in TRANSFER_TERMINAL_STATUSES else "PENDING",
                "provider_status": provider_status,
                "polls": polls,
                "elapsed_seconds": int(elapsed),
                "max_wait_seconds": int(max_wait_seconds),
                "last": last,
            }
        sleep(max(0, min(poll_interval_seconds, max_wait_seconds - elapsed)))


def execute_transfer(
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    adapters: Mapping[str, Any],
    checkpoint_path: str,
    poll_interval_seconds: int = TRANSFER_DEFAULT_POLL_INTERVAL_SECONDS,
    max_wait_seconds: int = TRANSFER_DEFAULT_MAX_WAIT_SECONDS,
    sleep: Any = time.sleep,
    clock: Any = time.monotonic,
) -> Dict[str, Any]:
    """Submit one approved Data Transfer, checkpoint around it, poll, then independently verify."""
    approval_errors = (
        validate_approval(plan, approval)
        + validate_request_matches_plan(request, plan)
        + selected_adapter_errors(request, adapters)
        + _transfer_plan_errors(plan)
    )
    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_audit",
        "generated_at_utc": utc_now(),
        "mode": "apply",
        "operation": TRANSFER_OPERATION,
        "target": copy.deepcopy(plan.get("target") or {}),
        "transfer": copy.deepcopy(plan.get("transfer") or {}),
        "plan_digest": plan_digest(plan),
        "approval_errors": approval_errors,
        "transfer_id": None,
        "actions": [],
        "write_count": 0,
        "tenant_writes_performed": False,
        "human_review_required": False,
    }
    if approval_errors:
        report["status"] = "refused"
        return report
    checkpoint, checkpoint_errors = load_checkpoint(plan, checkpoint_path)
    if checkpoint_errors:
        report["status"] = "refused"
        report["approval_errors"] = checkpoint_errors
        return report
    action = plan["actions"][0]
    adapter = adapters["google_workspace"]
    previous = checkpoint["actions"].get(TRANSFER_ACTION_ID) or {}
    audit: Dict[str, Any] = {**action, "started_at_utc": utc_now()}
    report["actions"].append(audit)
    transfer_id = previous.get("transfer_id")
    report["transfer_id"] = transfer_id

    def save(status: str, **fields: Any) -> None:
        entry = {**previous, "status": status, "updated_at_utc": utc_now(), **fields}
        checkpoint["actions"][TRANSFER_ACTION_ID] = entry
        checkpoint["updated_at_utc"] = utc_now()
        atomic_write_json(checkpoint_path, checkpoint)

    def finish(status: str, audit_status: str, review: bool) -> Dict[str, Any]:
        audit["status"] = audit_status
        audit["completed_at_utc"] = utc_now()
        report["status"] = status
        report["human_review_required"] = review
        return report

    if previous.get("status") == "verified":
        verification = _safe_transfer_verify(adapter, plan, request, transfer_id)
        audit["resume_verification"] = verification
        if verification.get("verified"):
            return finish("verified_complete_no_write", "already_verified_no_write", False)
        return finish("partial_failure", "checkpoint_verification_failed", True)
    if previous.get("status") == "failed":
        audit["poll"] = previous.get("poll")
        return finish("transfer_failed", "provider_reported_failed_not_resubmitted", True)
    if previous and not transfer_id:
        # A crash between about_to_submit and the recorded response is
        # indeterminate: the provider may hold the transfer. Read back; never resend.
        # ponytail: recovery is Drive read-back only; add transfers.list lookup if indeterminate submits recur.
        verification = _safe_transfer_verify(adapter, plan, request, None)
        audit["resume_verification"] = verification
        if verification.get("verified"):
            save("verified", verification={"verified": True, "recovered_by_readback": True}, verified_at_utc=utc_now())
            return finish("verified_complete_no_write", "recovered_by_readback_no_write", False)
        return finish("partial_failure", "indeterminate_prior_submit_not_retried", True)
    if not transfer_id:
        fresh = inventory_all(request, adapters)
        report["fresh_preflight"] = fresh
        fresh_errors = list(fresh.get("request_errors") or []) + list(fresh.get("guard_errors") or [])
        approved = plan.get("inventory_signatures") or {}
        if "google_workspace" not in (fresh.get("providers") or {}):
            fresh_errors.append("google_workspace fresh preflight inventory is missing")
        for name, item in (fresh.get("providers") or {}).items():
            if approved.get(name) != inventory_signature(item):
                fresh_errors.append("{} material inventory drifted after approval".format(name))
        fresh_errors.extend(transfer_allowlist_errors(action, request))
        if fresh_errors:
            report["fresh_preflight_errors"] = fresh_errors
            report["status"] = "refused"
            return report
        save("about_to_submit")
        try:
            write = adapter.transfer_submit(action, request)
        except Exception as exc:
            write = {"accepted": False, "error": sanitize_error(exc)}
        report["write_count"] += 1
        report["tenant_writes_performed"] = True
        audit["write"] = write
        checkpoint["write_count"] = int(checkpoint.get("write_count", 0)) + 1
        transfer_id = str(write.get("transfer_id")) if write.get("accepted") is True and write.get("transfer_id") else None
        report["transfer_id"] = transfer_id
        try:
            if transfer_id:
                save("submitted", transfer_id=transfer_id, write=write, submitted_at_utc=utc_now())
            else:
                save("submit_error", write=write)
        except Exception as exc:
            audit["checkpoint_error"] = sanitize_error(exc)
            return finish("partial_failure", "submitted_checkpoint_failed", True)
        if not transfer_id:
            return finish("partial_failure", "submit_error", True)
        previous = checkpoint["actions"][TRANSFER_ACTION_ID]
    else:
        audit["resumed_recorded_transfer_id_without_resubmit"] = True
    audit["transfer_id"] = transfer_id
    poll = poll_transfer(adapter, transfer_id, poll_interval_seconds, max_wait_seconds, sleep, clock)
    audit["poll"] = poll
    last = poll.get("last") or {}
    if poll["overall_status"] == "COMPLETED":
        mismatch = [
            key for key, approved_id in (("old_owner_user_id", action["old_owner_user_id"]), ("new_owner_user_id", action["new_owner_user_id"]))
            if last.get(key) is not None and str(last.get(key)) != str(approved_id)
        ]
        verification = _safe_transfer_verify(adapter, plan, request, transfer_id) if not mismatch else {
            "verified": False, "error": "recorded transfer is bound to different owner IDs: " + ", ".join(mismatch),
        }
        audit["verification"] = verification
        if verification.get("verified"):
            save("verified", poll=poll, verification={"verified": True, "transfer_folder": verification.get("transfer_folder")}, verified_at_utc=utc_now())
            return finish("completed_and_verified", "verified", False)
        save("verification_failed", poll=poll)
        return finish("partial_failure", "verification_failed", True)
    if poll["overall_status"] == "FAILED":
        save("failed", poll=poll)
        return finish("transfer_failed", "provider_reported_failed", True)
    save("submitted", last_poll=poll)
    report["resume"] = {
        "transfer_id": transfer_id,
        "apply": "re-run apply with the same --plan/--approval/--checkpoint; the recorded transfer id is polled again and never resubmitted",
        "verify": "run verify with --plan and --checkpoint to read back Drive ownership without waiting",
    }
    return finish("transfer_pending", "pending_max_wait_elapsed", False)


def verify_transfer(
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    adapters: Mapping[str, Any],
    checkpoint: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """GET-only: fresh listing must show zero source ownership and the sampled files owned by the destination."""
    errors = validate_request_matches_plan(request, plan) + selected_adapter_errors(request, adapters) + _transfer_plan_errors(plan)
    if plan.get("plan_digest") != plan_digest(plan):
        errors.append("plan digest is invalid or plan drifted")
    transfer_id = None
    if checkpoint is not None:
        if checkpoint.get("plan_digest") != plan_digest(plan):
            errors.append("checkpoint belongs to a different plan")
        else:
            transfer_id = ((checkpoint.get("actions") or {}).get(TRANSFER_ACTION_ID) or {}).get("transfer_id")
    result = _safe_transfer_verify(adapters["google_workspace"], plan, request, transfer_id) if not errors else {"verified": False}
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "workspace_user_lifecycle_verification",
        "generated_at_utc": utc_now(),
        "mode": "verify",
        "operation": TRANSFER_OPERATION,
        "target": copy.deepcopy(request.get("target") or {}),
        "transfer": copy.deepcopy(request.get("transfer") or {}),
        "plan_digest": plan.get("plan_digest"),
        "transfer_id": transfer_id,
        "providers": {"google_workspace": result},
        "adapter_errors": errors,
        "write_count": 0,
        "tenant_writes_performed": False,
        "status": "verified_complete_no_write" if result.get("verified") is True else "verification_failed",
    }
