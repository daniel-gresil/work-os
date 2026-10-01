#!/usr/bin/env python3
"""Live Google Workspace and Microsoft 365 adapters for lifecycle_engine.

Secrets stay outside request/audit JSON. Google accepts a service-account JSON path
and delegated admin subject at construction. Microsoft uses the current Azure CLI
Graph session. Responses are minimized before returning to the engine.
"""

from __future__ import annotations

import concurrent.futures
import json
import subprocess
import time
import urllib.parse
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import requests

from lifecycle_engine import (
    DRIVE_TRANSFER_APPLICATION_ID,
    DRIVE_TRANSFER_PARAMS,
    GOOGLE_LICENSE_PRODUCT_CATALOG,
    TRANSFER_SAMPLE_SIZE,
    LifecycleError,
    sanitize_error,
)

GOOGLE_DIRECTORY = "https://admin.googleapis.com/admin/directory/v1"
GOOGLE_DATATRANSFER = "https://admin.googleapis.com/admin/datatransfer/v1"
GOOGLE_LICENSING = "https://licensing.googleapis.com/apps/licensing/v1"
GOOGLE_DRIVE = "https://www.googleapis.com/drive/v3"
GOOGLE_GMAIL = "https://gmail.googleapis.com/gmail/v1"
GRAPH = "https://graph.microsoft.com/v1.0"

GOOGLE_SCOPES = {
    "directory": "https://www.googleapis.com/auth/admin.directory.user",
    "groups": "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "roles": "https://www.googleapis.com/auth/admin.directory.rolemanagement.readonly",
    "security": "https://www.googleapis.com/auth/admin.directory.user.security",
    "licensing": "https://www.googleapis.com/auth/apps.licensing",
    "drive": "https://www.googleapis.com/auth/drive",
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
    "datatransfer": "https://www.googleapis.com/auth/admin.datatransfer",
}
DRIVE_OWNER_QUERY = "'{}' in owners and trashed = false"
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
# The transfer listing impersonates the delegated admin, so it can only see
# source-owned objects that are visible to that admin. Data Transfer moves
# everything regardless; the approver accepts this bound explicitly.
GOOGLE_TRANSFER_LIMITATIONS = ["google_drive_transfer_inventory_bounded_to_admin_subject_visibility"]
GOOGLE_FAST_PATH_LIMITATIONS = [
    "google_external_ownership_dependencies_not_in_fast_path",
    "google_gmail_settings_delegates_oauth_not_in_fast_path",
    "google_vault_tenant_retention_not_api_verifiable",
]
MICROSOFT_FAST_PATH_LIMITATIONS = [
    "microsoft_exchange_dependencies_not_in_graph_fast_path",
    "microsoft_external_ownership_dependencies_not_in_fast_path",
    "microsoft_onedrive_dependencies_not_in_graph_fast_path",
    "microsoft_purview_holds_not_in_graph_fast_path",
]


def _page(session: requests.Session, url: str, key: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    values: List[Dict[str, Any]] = []
    query = dict(params or {})
    while True:
        response = session.get(url, params=query, timeout=60)
        if response.status_code != 200:
            raise LifecycleError("GET {} returned HTTP {}: {}".format(url, response.status_code, _error_message(response)))
        body = response.json()
        values.extend(body.get(key) or [])
        token = body.get("nextPageToken")
        if not token:
            return values
        query["pageToken"] = token


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            return str(error.get("message", ""))[:400]
        return str(error)[:400]
    except Exception:
        return "non-JSON provider error"


def _evidence(response: requests.Response) -> Dict[str, Any]:
    result: Dict[str, Any] = {"http_status": int(response.status_code)}
    ids = {
        key: response.headers.get(key)
        for key in ("request-id", "x-request-id", "x-goog-request-id", "x-guploader-uploadid")
        if response.headers.get(key)
    }
    if ids:
        result["request_ids"] = ids
    if response.status_code >= 400:
        result["error"] = _error_message(response)
    return result


def _google_session(credential_path: str, subject: str, scope: str) -> requests.Session:
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as exc:
        raise LifecycleError("google-auth is required for Google Workspace live mode") from exc
    credentials = service_account.Credentials.from_service_account_file(credential_path, scopes=[scope], subject=subject)
    return AuthorizedSession(credentials)


def _google_user(body: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "immutable_id": body.get("id"),
        "email": str(body.get("primaryEmail", "")).lower(),
        "customer_id": body.get("customerId"),
        "suspended": body.get("suspended"),
        "is_admin": body.get("isAdmin"),
        "is_delegated_admin": body.get("isDelegatedAdmin"),
        "aliases": body.get("aliases") or [],
        "non_editable_aliases": body.get("nonEditableAliases") or [],
        "org_unit_path": body.get("orgUnitPath"),
    }


class GoogleWorkspaceAdapter:
    name = "google_workspace"

    def __init__(self, credential_path: str, admin_subject: str) -> None:
        self.credential_path = credential_path
        self.admin_subject = admin_subject
        self._sessions: Dict[str, requests.Session] = {}

    def session(self, key: str, subject: Optional[str] = None) -> requests.Session:
        cache_key = "{}:{}".format(key, subject or self.admin_subject)
        if cache_key not in self._sessions:
            self._sessions[cache_key] = _google_session(
                self.credential_path, subject or self.admin_subject, GOOGLE_SCOPES[key]
            )
        return self._sessions[cache_key]

    def _user_get(self, key: str) -> requests.Response:
        return self.session("directory").get(
            GOOGLE_DIRECTORY + "/users/" + urllib.parse.quote(key, safe=""),
            params={"projection": "full"},
            timeout=60,
        )

    def _resolve_user(self, email: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """GET-only exact primary-email resolution: (exact, non_user, errors)."""
        response = self._user_get(email)
        if response.status_code == 200:
            user = _google_user(response.json())
            if user["email"] == email:
                return [user], [], []
            return [], [{"type": "alias_on_user", "immutable_id": user["immutable_id"], "owner_email": user["email"]}], []
        if response.status_code == 404:
            return [], [], []
        return [], [], ["directory user lookup: HTTP {} {}".format(response.status_code, _error_message(response))]

    def _assert_current_identity(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        target = str((request.get("target") or {}).get("email", "")).lower()
        expected_id = str(config.get("immutable_id", ""))
        response = self._user_get(expected_id)
        if response.status_code != 200:
            raise LifecycleError("exact Google identity is not active immediately before write")
        user = _google_user(response.json())
        if (
            str(user.get("immutable_id")) != expected_id
            or str(user.get("email", "")).lower() != target
            or str(user.get("customer_id")) != str(config.get("customer_id"))
        ):
            raise LifecycleError("exact Google identity drifted immediately before write")
        return user

    def _license_assignments(self, request: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        customer = str(config.get("customer_id", ""))
        products = config.get("license_product_ids") or []
        if config.get("license_product_catalog_complete") is not True or not products:
            raise LifecycleError("Google license product catalog completeness was not explicitly asserted")

        # One delegated session per bounded worker avoids sharing a requests
        # Session across threads. Sort merged results so inventory hashes are
        # deterministic despite completion order.
        worker_count = min(4, len(products))
        chunks = [products[index::worker_count] for index in range(worker_count)]

        def collect(chunk: List[Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
            session = _google_session(
                self.credential_path,
                self.admin_subject,
                GOOGLE_SCOPES["licensing"],
            )
            found: List[Dict[str, Any]] = []
            failed: List[str] = []
            for product in chunk:
                try:
                    items = _page(
                        session,
                        GOOGLE_LICENSING + "/product/{}/users".format(urllib.parse.quote(str(product), safe="")),
                        "items",
                        {"customerId": customer, "maxResults": 1000},
                    )
                    found.extend(
                        {
                            "product_id": item.get("productId"),
                            "sku_id": item.get("skuId"),
                            "user_id": str(item.get("userId", "")).lower(),
                        }
                        for item in items
                    )
                except Exception as exc:
                    failed.append("{}: {}".format(product, sanitize_error(exc)))
            return found, failed

        assignments: List[Dict[str, Any]] = []
        errors: List[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            for found, failed in executor.map(collect, chunks):
                assignments.extend(found)
                errors.extend(failed)
        assignments.sort(key=lambda item: (str(item.get("product_id")), str(item.get("sku_id")), str(item.get("user_id"))))
        errors.sort()
        return assignments, errors

    def inventory(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        target = str((request.get("target") or {}).get("email", "")).lower()
        expected_id = str(config.get("immutable_id", ""))
        exact, non_user, errors = self._resolve_user(target)
        try:
            directory_groups = _page(
                self.session("groups"),
                GOOGLE_DIRECTORY + "/groups",
                "groups",
                {"customer": config.get("customer_id"), "maxResults": 200},
            )
            for group in directory_groups:
                addresses = {
                    str(value).lower()
                    for value in [group.get("email"), *(group.get("aliases") or []), *(group.get("nonEditableAliases") or [])]
                    if value
                }
                if target in addresses:
                    non_user.append({"type": "group", "immutable_id": group.get("id"), "email": str(group.get("email", "")).lower()})
        except Exception as exc:
            errors.append("group recipient lookup: " + sanitize_error(exc))
        groups: List[Dict[str, Any]] = []
        roles: List[Dict[str, Any]] = []
        drive: Dict[str, Any] = {"owned_nontrashed_count": None}
        mailbox: Dict[str, Any] = {"exists": None}
        licenses: List[Dict[str, Any]] = []
        if exact:
            try:
                groups = _page(
                    self.session("groups"), GOOGLE_DIRECTORY + "/groups", "groups", {"userKey": target, "maxResults": 200}
                )
            except Exception as exc:
                errors.append("group memberships: " + sanitize_error(exc))
            try:
                roles = _page(
                    self.session("roles"), GOOGLE_DIRECTORY + "/customer/{}/roleassignments".format(urllib.parse.quote(str(config.get("customer_id")), safe="")), "items", {"userKey": expected_id, "maxResults": 200}
                )
            except Exception as exc:
                errors.append("role assignments: " + sanitize_error(exc))
            try:
                all_assignments, license_errors = self._license_assignments(request)
                errors.extend("license inventory: " + item for item in license_errors)
                licenses = [item for item in all_assignments if item["user_id"] in {target, expected_id.lower()}]
            except Exception as exc:
                errors.append("license inventory: " + sanitize_error(exc))
            try:
                target_session = self.session("drive", target)
                files = _page(
                    target_session,
                    GOOGLE_DRIVE + "/files",
                    "files",
                    {"q": "'me' in owners and trashed = false", "fields": "nextPageToken,files(id,mimeType,size)", "pageSize": 1000, "supportsAllDrives": "true"},
                )
                drive = {"owned_nontrashed_count": len(files), "by_type": {}}
                for item in files:
                    mime = str(item.get("mimeType", "unknown"))
                    drive["by_type"][mime] = drive["by_type"].get(mime, 0) + 1
            except Exception as exc:
                errors.append("Drive inventory: " + sanitize_error(exc))
            try:
                profile = self.session("gmail", target).get(GOOGLE_GMAIL + "/users/me/profile", timeout=60)
                mailbox = {"exists": profile.status_code == 200, "http_status": profile.status_code}
                if profile.status_code not in {200, 404}:
                    errors.append("Gmail profile: HTTP {}".format(profile.status_code))
            except Exception as exc:
                errors.append("Gmail inventory: " + sanitize_error(exc))
        return {
            "status": "ok" if not errors else "incomplete",
            "complete": not errors,
            "customer_id": config.get("customer_id"),
            "identity": {"exact_matches": exact, "non_user_matches": non_user},
            "groups": [{"id": item.get("id"), "email": item.get("email")} for item in groups],
            "roles": [{"role_assignment_id": item.get("roleAssignmentId"), "role_id": item.get("roleId")} for item in roles],
            "licenses": licenses,
            "drive": drive,
            "mailbox": mailbox,
            "limitations": GOOGLE_FAST_PATH_LIMITATIONS if exact else [],
            "errors": errors,
            "write_count": 0,
        }

    # ---- Drive ownership transfer (Admin SDK Data Transfer API) ----

    def _drive_owned_by(self, email: str) -> Dict[str, Any]:
        """Admin-subject Drive v3 files.list of non-trashed objects owned by `email`, fully paginated."""
        if "'" in email or "\\" in email:
            raise LifecycleError("owner email contains characters that are not allowed in a Drive query")
        query = DRIVE_OWNER_QUERY.format(email)
        files = _page(
            self.session("drive"),
            GOOGLE_DRIVE + "/files",
            "files",
            {"q": query, "fields": "nextPageToken,files(id,mimeType,size,parents)", "pageSize": 1000, "supportsAllDrives": "true"},
        )
        files.sort(key=lambda item: str(item.get("id")))
        by_type: Dict[str, int] = {}
        total_bytes = 0
        without_size = 0
        for item in files:
            mime = str(item.get("mimeType", "unknown"))
            by_type[mime] = by_type.get(mime, 0) + 1
            if item.get("size") is None:
                without_size += 1
            else:
                total_bytes += int(item["size"])
        sample = [
            {
                "id": item.get("id"),
                "mime_type": item.get("mimeType"),
                "size": None if item.get("size") is None else int(item["size"]),
                "parents": sorted(str(parent) for parent in item.get("parents") or []),
            }
            for item in files[:TRANSFER_SAMPLE_SIZE]
        ]
        return {
            "query": query,
            "listing_subject": "delegated_admin",
            "owned_nontrashed_count": len(files),
            "total_reported_bytes": total_bytes,
            "objects_without_reported_size": without_size,
            "by_type": by_type,
            "sample": sample,
            "sample_size": len(sample),
            "sample_selection": "first {} objects by ascending file id".format(TRANSFER_SAMPLE_SIZE),
        }

    def transfer_inventory(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        """GET-only: resolve source and destination Directory users and list source-owned Drive objects."""
        config = (request.get("platforms") or {}).get(self.name) or {}
        source_email = str((request.get("target") or {}).get("email", "")).lower()
        destination_email = str(((request.get("transfer") or {}).get("destination") or {}).get("email", "")).lower()
        source, non_user, errors = self._resolve_user(source_email)
        destination, destination_non_user, destination_errors = self._resolve_user(destination_email)
        errors = errors + ["destination " + error for error in destination_errors]
        drive: Dict[str, Any] = {"owned_nontrashed_count": None}
        try:
            drive = self._drive_owned_by(source_email)
        except Exception as exc:
            errors.append("Drive inventory: " + sanitize_error(exc))
        return {
            "status": "ok" if not errors else "incomplete",
            "complete": not errors,
            "customer_id": config.get("customer_id"),
            "identity": {
                "source_exact_matches": source,
                "destination_exact_matches": destination,
                "non_user_matches": non_user + destination_non_user,
            },
            "drive": drive,
            "limitations": GOOGLE_TRANSFER_LIMITATIONS,
            "errors": errors,
            "write_count": 0,
        }

    def transfer_submit(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
        """The only transfer write: transfers.insert with the approved immutable IDs and fixed Drive params."""
        config = (request.get("platforms") or {}).get(self.name) or {}
        destination = (request.get("transfer") or {}).get("destination") or {}
        body = {
            "oldOwnerUserId": str(action.get("old_owner_user_id")),
            "newOwnerUserId": str(action.get("new_owner_user_id")),
            "applicationDataTransfers": [{
                "applicationId": str(action.get("application_id")),
                "applicationTransferParams": json.loads(json.dumps(action.get("application_transfer_params"))),
            }],
        }
        if (
            body["oldOwnerUserId"] != str(config.get("immutable_id"))
            or body["newOwnerUserId"] != str(destination.get("immutable_id"))
            or body["applicationDataTransfers"][0]["applicationId"] != DRIVE_TRANSFER_APPLICATION_ID
            or body["applicationDataTransfers"][0]["applicationTransferParams"] != DRIVE_TRANSFER_PARAMS
        ):
            raise LifecycleError("transfer action is outside the exact-ID allowlist")
        source = self._assert_current_identity(request)
        if source.get("suspended") is not True:
            raise LifecycleError("source user is not suspended immediately before transfer")
        response = self._user_get(str(destination.get("immutable_id")))
        if response.status_code != 200:
            raise LifecycleError("destination user is not active immediately before transfer")
        current = _google_user(response.json())
        if (
            str(current.get("immutable_id")) != body["newOwnerUserId"]
            or current.get("email") != str(destination.get("email", "")).lower()
            or str(current.get("customer_id")) != str(config.get("customer_id"))
        ):
            raise LifecycleError("destination identity drifted immediately before transfer")
        if current.get("suspended") is not False:
            raise LifecycleError("destination user is suspended immediately before transfer")
        response = self.session("datatransfer").post(GOOGLE_DATATRANSFER + "/transfers", json=body, timeout=60)
        result: Dict[str, Any] = {"accepted": response.status_code == 200, "request_body": body, **_evidence(response)}
        if result["accepted"]:
            payload = response.json()
            if not payload.get("id"):
                result["accepted"] = False
                result["error"] = "provider accepted the transfer without returning an id"
            else:
                result["transfer_id"] = str(payload["id"])
                result["overall_status"] = str(payload.get("overallTransferStatusCode", "")).upper()
                result["request_time"] = payload.get("requestTime")
        return result

    def transfer_status(self, transfer_id: str) -> Dict[str, Any]:
        response = self.session("datatransfer").get(
            GOOGLE_DATATRANSFER + "/transfers/" + urllib.parse.quote(str(transfer_id), safe=""), timeout=60
        )
        if response.status_code != 200:
            raise LifecycleError("transfers.get returned HTTP {}: {}".format(response.status_code, _error_message(response)))
        body = response.json()
        return {
            "transfer_id": str(body.get("id")),
            "overall_status": str(body.get("overallTransferStatusCode", "")).upper(),
            "old_owner_user_id": body.get("oldOwnerUserId"),
            "new_owner_user_id": body.get("newOwnerUserId"),
            "request_time": body.get("requestTime"),
            "applications": [
                {"application_id": str(app.get("applicationId")), "status": str(app.get("applicationTransferStatus", "")).upper()}
                for app in body.get("applicationDataTransfers") or []
            ],
            **_evidence(response),
        }

    def _file_get(self, file_id: str, fields: str) -> requests.Response:
        return self.session("drive").get(
            GOOGLE_DRIVE + "/files/" + urllib.parse.quote(str(file_id), safe=""),
            params={"fields": fields, "supportsAllDrives": "true"},
            timeout=60,
        )

    def transfer_verify(self, plan: Mapping[str, Any], request: Mapping[str, Any], transfer_id: Optional[str] = None) -> Dict[str, Any]:
        """GET-only read-back: zero source-owned objects, destination owns the sampled files, folder name if discoverable."""
        self._sessions = {}
        destination_email = str(((request.get("transfer") or {}).get("destination") or {}).get("email", "")).lower()
        inventory = self.transfer_inventory(request)
        errors: List[str] = list(inventory.get("errors") or [])
        sample = (plan.get("pre_transfer_inventory") or {}).get("sample") or []
        prior_parents = {parent for item in sample for parent in item.get("parents") or []}
        new_parents: set[str] = set()
        ownership: List[Dict[str, Any]] = []
        for item in sample:
            response = self._file_get(str(item.get("id")), "id,trashed,owners(emailAddress),parents")
            entry: Dict[str, Any] = {"id": item.get("id"), **_evidence(response)}
            if response.status_code == 200:
                body = response.json()
                owners = {str(owner.get("emailAddress", "")).lower() for owner in body.get("owners") or []}
                entry["destination_is_owner"] = owners == {destination_email}
                entry["trashed"] = body.get("trashed")
                new_parents.update(str(parent) for parent in body.get("parents") or [] if str(parent) not in prior_parents)
            else:
                entry["destination_is_owner"] = False
                if response.status_code != 404:
                    errors.append("sample file read: HTTP {}".format(response.status_code))
            ownership.append(entry)
        status = None
        if transfer_id:
            try:
                status = self.transfer_status(transfer_id)
            except Exception as exc:
                errors.append("transfers.get: " + sanitize_error(exc))
        count = (inventory.get("drive") or {}).get("owned_nontrashed_count")
        verified = (
            inventory.get("complete") is True
            and not errors
            and count == 0
            and all(entry.get("destination_is_owner") is True for entry in ownership)
            and (status is None or status.get("overall_status") == "COMPLETED")
        )
        return {
            "verified": verified,
            "method": "fresh admin-subject Drive listing plus per-file owner read-back of the approved sample",
            "inventory": inventory,
            "remaining_source_owned_nontrashed_count": count,
            "sample_ownership": ownership,
            "sample_checked": len(ownership),
            "transfer_status": status,
            "transfer_folder": self._transfer_folder(new_parents, destination_email),
            "errors": errors,
            "write_count": 0,
        }

    def _transfer_folder(self, candidate_ids: Iterable[str], destination_email: str) -> Dict[str, Any]:
        """Google creates the transfer folder; report its name only when Drive metadata resolves it uniquely."""
        # ponytail: direct parents of sampled files only; walk ancestors if nested-only samples leave this unresolved often.
        candidates: List[Dict[str, Any]] = []
        for folder_id in sorted(candidate_ids):
            response = self._file_get(folder_id, "id,name,mimeType,owners(emailAddress)")
            if response.status_code != 200:
                continue
            body = response.json()
            owners = {str(owner.get("emailAddress", "")).lower() for owner in body.get("owners") or []}
            if body.get("mimeType") == DRIVE_FOLDER_MIME and owners == {destination_email}:
                candidates.append({"id": body.get("id"), "name": body.get("name")})
        if len(candidates) == 1:
            return {"resolution": "resolved_from_drive_parent_metadata", **candidates[0]}
        return {
            "resolution": "unresolved",
            "reason": "Data Transfer API does not expose the folder; no sampled file gained exactly one new destination-owned parent folder",
            "candidates": candidates,
        }

    def apply_action(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        target = str((request.get("target") or {}).get("email", "")).lower()
        immutable_id = str(config.get("immutable_id"))
        base = GOOGLE_DIRECTORY + "/users/" + urllib.parse.quote(immutable_id, safe="")
        verb = action.get("verb")
        current_user = self._assert_current_identity(request)
        if verb != "suspend" and current_user.get("suspended") is not True:
            raise LifecycleError("Google user is not suspended immediately before dependent write")
        if verb == "suspend":
            response = self.session("directory").patch(base, json={"suspended": True}, timeout=60)
        elif verb == "revoke_sessions":
            response = self.session("security").post(base + "/signOut", timeout=60)
        elif verb == "remove_license":
            licenses = action.get("expected_licenses") or []
            if len(licenses) != 1:
                raise LifecycleError("remove_license requires exactly one expected_licenses entry")
            license_item = licenses[0]
            assignments, errors = self._license_assignments(request)
            if errors:
                raise LifecycleError("cannot prove complete Google license state immediately before removal")
            current = {
                (str(item.get("product_id")), str(item.get("sku_id")))
                for item in assignments
                if item.get("user_id") in {target, immutable_id.lower()}
            }
            approved = {(str(license_item["product_id"]), str(license_item["sku_id"]))}
            if current != approved:
                raise LifecycleError("Google license set drifted immediately before removal")
            url = GOOGLE_LICENSING + "/product/{}/sku/{}/user/{}".format(
                urllib.parse.quote(str(license_item["product_id"]), safe=""),
                urllib.parse.quote(str(license_item["sku_id"]), safe=""),
                urllib.parse.quote(target, safe=""),
            )
            response = self.session("licensing").delete(url, timeout=60)
        elif verb == "delete_user":
            response = self.session("directory").delete(base, timeout=60)
        else:
            raise LifecycleError("unsupported Google action {}".format(verb))
        return {"accepted": response.status_code in {200, 204}, **_evidence(response)}

    def _tombstone(self, request: Mapping[str, Any]) -> bool:
        config = (request.get("platforms") or {}).get(self.name) or {}
        expected_id = str(config.get("immutable_id"))
        target = str((request.get("target") or {}).get("email", "")).lower()
        users = _page(
            self.session("directory"), GOOGLE_DIRECTORY + "/users", "users", {"customer": config.get("customer_id"), "showDeleted": "true", "maxResults": 500}
        )
        return len([item for item in users if str(item.get("id")) == expected_id and str(item.get("primaryEmail", "")).lower() == target]) == 1

    def _licenses_absent(self, request: Mapping[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        assignments, errors = self._license_assignments(request)
        config = (request.get("platforms") or {}).get(self.name) or {}
        target = str((request.get("target") or {}).get("email", "")).lower()
        expected_id = str(config.get("immutable_id", "")).lower()
        matches = [item for item in assignments if item["user_id"] in {target, expected_id}]
        return not errors and not matches, {"listing_complete": not errors, "matches": matches, "errors": errors}

    def verify_action(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
        verb = action.get("verb")
        config = (request.get("platforms") or {}).get(self.name) or {}
        immutable_id = str(config.get("immutable_id"))
        if verb in {"suspend", "revoke_sessions"}:
            response = self._user_get(immutable_id)
            suspended = response.status_code == 200 and response.json().get("suspended") is True
            return {"verified": suspended, "method": "directory suspended read-back", **_evidence(response)}
        if verb == "remove_license":
            absent, evidence = self._licenses_absent(request)
            return {"verified": absent, "method": "complete product assignment listing", **evidence}
        if verb == "delete_user":
            return self.verify_terminal(request)
        return {"verified": False, "error": "unsupported action"}

    def verify_terminal(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        # Use newly minted delegated sessions for terminal evidence instead of
        # reusing handles that sent writes.
        self._sessions = {}
        config = (request.get("platforms") or {}).get(self.name) or {}
        disposition = config.get("disposition")
        target = str((request.get("target") or {}).get("email", "")).lower()
        expected_id = str(config.get("immutable_id", ""))
        by_email = self._user_get(target)
        if disposition == "absent":
            inventory = self.inventory(request)
            identity = inventory.get("identity") or {}
            verified = (
                inventory.get("complete") is True
                and str(inventory.get("customer_id")) == str(config.get("customer_id"))
                and not (identity.get("exact_matches") or [])
                and not (identity.get("non_user_matches") or [])
            )
            return {"verified": verified, "inventory": inventory, "active_by_email": _evidence(by_email), "write_count": 0}
        by_id = self._user_get(expected_id) if expected_id else None
        license_absent, license_evidence = self._licenses_absent(request)
        tombstone = self._tombstone(request)
        verified = by_email.status_code == 404 and by_id is not None and by_id.status_code == 404 and tombstone and license_absent
        return {
            "verified": verified,
            "active_by_email": _evidence(by_email),
            "active_by_id": _evidence(by_id) if by_id is not None else None,
            "tombstone_verified": tombstone,
            "license_absence": license_evidence,
            "write_count": 0,
        }


def _run_json(command: List[str]) -> Dict[str, Any]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise LifecycleError(result.stderr.strip().replace("\n", " ")[:800])
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise LifecycleError("command returned non-object JSON")
    return value


class Microsoft365Adapter:
    name = "microsoft_365"

    def __init__(self) -> None:
        token = _run_json(["az", "account", "get-access-token", "--resource-type", "ms-graph", "--output", "json"])
        self.token = str(token["accessToken"])
        account = _run_json(["az", "account", "show", "--output", "json"])
        self.tenant_id = str(account.get("tenantId", ""))
        self.session = requests.Session()
        self.session.headers.update({"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return self.session.get(GRAPH + path, params=params, timeout=60)

    def _collection(self, path: str, select: str) -> List[Dict[str, Any]]:
        url: Optional[str] = GRAPH + path
        params: Optional[Dict[str, Any]] = {"$select": select, "$top": "999"}
        result: List[Dict[str, Any]] = []
        while url:
            response = self.session.get(url, params=params, timeout=60)
            if response.status_code != 200:
                raise LifecycleError("Graph GET returned HTTP {}: {}".format(response.status_code, _error_message(response)))
            body = response.json()
            result.extend(body.get("value") or [])
            url = body.get("@odata.nextLink")
            params = None
        return result

    @staticmethod
    def _addresses(item: Mapping[str, Any]) -> set[str]:
        values: List[str] = []
        for key in ("userPrincipalName", "mail"):
            if item.get(key):
                values.append(str(item[key]))
        values.extend(str(value) for value in item.get("otherMails") or [])
        values.extend(str(value).split(":", 1)[-1] for value in item.get("proxyAddresses") or [])
        for identity in item.get("identities") or []:
            if identity.get("issuerAssignedId"):
                values.append(str(identity["issuerAssignedId"]))
        return {value.lower() for value in values}

    @staticmethod
    def _canonical_user_addresses(item: Mapping[str, Any]) -> set[str]:
        """Addresses that can identify a user, excluding mailbox proxies."""
        values = [
            str(item[key]).lower()
            for key in ("userPrincipalName", "mail")
            if item.get(key)
        ]
        values.extend(
            str(identity["issuerAssignedId"]).lower()
            for identity in item.get("identities") or []
            if identity.get("signInType") in {"emailAddress", "userPrincipalName"}
            and identity.get("issuerAssignedId")
        )
        return set(values)

    @classmethod
    def _proxy_only_addresses(cls, item: Mapping[str, Any]) -> set[str]:
        proxies = {
            str(value).split(":", 1)[-1].lower()
            for value in item.get("proxyAddresses") or []
            if value
        }
        proxies.update(str(value).lower() for value in item.get("otherMails") or [] if value)
        return proxies - cls._canonical_user_addresses(item)

    def inventory(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        target = str((request.get("target") or {}).get("email", "")).lower()
        errors: List[str] = []
        try:
            users = self._collection("/users", "id,userPrincipalName,mail,proxyAddresses,otherMails,identities,accountEnabled,assignedLicenses")
            deleted = self._collection("/directory/deletedItems/microsoft.graph.user", "id,userPrincipalName,mail,proxyAddresses,otherMails,identities")
            groups = self._collection("/groups", "id,mail,proxyAddresses")
            contacts = self._collection("/contacts", "id,mail,proxyAddresses")
        except Exception as exc:
            users, deleted, groups, contacts = [], [], [], []
            errors.append(sanitize_error(exc))
        exact_users = [item for item in users if target in self._canonical_user_addresses(item)]
        proxy_owners = [item for item in users if target in self._proxy_only_addresses(item)]
        non_user = [
            {"type": kind, "immutable_id": item.get("id"), "email": item.get("mail")}
            for kind, collection in (("group", groups), ("contact", contacts))
            for item in collection
            if target in self._addresses(item)
        ]
        non_user.extend(
            {
                "type": "proxy_on_user",
                "immutable_id": item.get("id"),
                "owner_upn": item.get("userPrincipalName"),
            }
            for item in proxy_owners
        )
        exact = [
            {
                "immutable_id": item.get("id"),
                "email": target,
                "canonical_upn": item.get("userPrincipalName"),
                "account_enabled": item.get("accountEnabled"),
                "assigned_licenses": item.get("assignedLicenses") or [],
            }
            for item in exact_users
        ]
        return {
            "status": "ok" if not errors else "incomplete",
            "complete": not errors,
            "tenant_id": self.tenant_id,
            "identity": {"exact_matches": exact, "non_user_matches": non_user},
            "deleted_exact_matches": [item.get("id") for item in deleted if target in self._canonical_user_addresses(item)],
            "deleted_user_ids": [item.get("id") for item in deleted],
            "protected_same_localpart": [
                {"immutable_id": item.get("id"), "canonical_upn": item.get("userPrincipalName")}
                for item in users
                if str(item.get("userPrincipalName", "")).lower().split("@", 1)[0] == target.split("@", 1)[0]
                and target not in self._addresses(item)
            ],
            "limitations": MICROSOFT_FAST_PATH_LIMITATIONS if exact else [],
            "errors": errors,
            "write_count": 0,
        }

    def apply_action(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        immutable_id = urllib.parse.quote(str(config.get("immutable_id")), safe="")
        url = GRAPH + "/users/" + immutable_id
        verb = action.get("verb")
        before = self._get(
            "/users/" + immutable_id,
            {"$select": "id,userPrincipalName,mail,proxyAddresses,otherMails,identities,accountEnabled,assignedLicenses"},
        )
        if before.status_code != 200:
            raise LifecycleError("exact Microsoft identity is not active immediately before write")
        body = before.json()
        target = str((request.get("target") or {}).get("email", "")).lower()
        if str(body.get("id")) != str(config.get("immutable_id")) or target not in self._canonical_user_addresses(body):
            raise LifecycleError("exact Microsoft identity drifted immediately before write")
        if verb != "block_sign_in" and body.get("accountEnabled") is not False:
            raise LifecycleError("Microsoft user is not blocked immediately before dependent write")
        if verb == "block_sign_in":
            response = self.session.patch(url, json={"accountEnabled": False}, timeout=60)
        elif verb == "revoke_sessions":
            response = self.session.post(url + "/revokeSignInSessions", json={}, timeout=60)
        elif verb == "remove_licenses":
            current = {str(item.get("skuId")) for item in body.get("assignedLicenses") or []}
            approved = {str(item) for item in action.get("expected_license_sku_ids") or []}
            if current != approved:
                raise LifecycleError("Microsoft license set drifted immediately before removal")
            remove = sorted(approved)
            response = self.session.post(url + "/assignLicense", json={"addLicenses": [], "removeLicenses": remove}, timeout=60)
        elif verb == "delete_user":
            response = self.session.delete(url, timeout=60)
        else:
            raise LifecycleError("unsupported Microsoft action {}".format(verb))
        return {"accepted": response.status_code in {200, 204}, **_evidence(response)}

    def verify_action(self, action: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        immutable_id = urllib.parse.quote(str(config.get("immutable_id")), safe="")
        verb = action.get("verb")
        if verb in {"block_sign_in", "revoke_sessions", "remove_licenses"}:
            response = self._get("/users/" + immutable_id, {"$select": "id,accountEnabled,assignedLicenses"})
            body = response.json() if response.status_code == 200 else {}
            if verb in {"block_sign_in", "revoke_sessions"}:
                verified = response.status_code == 200 and body.get("accountEnabled") is False
            else:
                verified = response.status_code == 200 and not (body.get("assignedLicenses") or [])
            return {"verified": verified, **_evidence(response)}
        if verb == "delete_user":
            return self.verify_terminal(request)
        return {"verified": False, "error": "unsupported action"}

    def verify_terminal(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        config = (request.get("platforms") or {}).get(self.name) or {}
        target = str((request.get("target") or {}).get("email", "")).lower()
        inventory = self.inventory(request)
        exact = (inventory.get("identity") or {}).get("exact_matches") or []
        non_user = (inventory.get("identity") or {}).get("non_user_matches") or []
        if config.get("disposition") == "absent":
            return {
                "verified": (
                    inventory.get("complete") is True
                    and str(inventory.get("tenant_id")) == str(config.get("tenant_id"))
                    and not exact
                    and not non_user
                ),
                "inventory": inventory,
                "write_count": 0,
            }
        # Deletion verification is pinned to the immutable ID. Address fields
        # on deleted Graph objects can be normalized or removed by the provider.
        deleted_ids = inventory.get("deleted_user_ids") or []
        expected_id = str(config.get("immutable_id"))
        return {
            "verified": (
                inventory.get("complete") is True
                and str(inventory.get("tenant_id")) == str(config.get("tenant_id"))
                and not exact
                and not non_user
                and expected_id in deleted_ids
            ),
            "inventory": inventory,
            "write_count": 0,
        }
