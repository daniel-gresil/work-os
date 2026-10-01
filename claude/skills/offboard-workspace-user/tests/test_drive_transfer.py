"""Offline tests for the Google Drive ownership transfer operation (mocked API responses only)."""

import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import lifecycle_engine as engine

try:
    import provider_adapters as adapters_module
except ImportError:  # requests/google-auth absent: adapter tests are skipped, engine tests still run
    adapters_module = None

SOURCE = "departing.user@example.test"
DESTINATION = "sofia@example.test"
LIMITATION = "google_drive_transfer_inventory_bounded_to_admin_subject_visibility"


def request(**changes):
    value = {
        "schema_version": 1,
        "operation": engine.TRANSFER_OPERATION,
        "target": {"email": SOURCE},
        "platforms": {
            "google_workspace": {"disposition": "present", "immutable_id": "g-123", "customer_id": "C-example"},
            "microsoft_365": {"disposition": "skip"},
        },
        "transfer": {"destination": {"email": DESTINATION, "immutable_id": "g-456"}},
        "policy": {"approver": "ticket-42", "accepted_unknowns": [LIMITATION]},
    }
    value.update(changes)
    return value


def user(email, immutable_id, suspended):
    return {"email": email, "immutable_id": immutable_id, "customer_id": "C-example", "suspended": suspended}


def sample(count=3):
    return [
        {"id": "file-{:02d}".format(index), "mime_type": "application/pdf", "size": 100, "parents": ["root-src"]}
        for index in range(count)
    ]


def google_inventory(count=3, **changes):
    value = {
        "status": "ok",
        "complete": True,
        "customer_id": "C-example",
        "identity": {
            "source_exact_matches": [user(SOURCE, "g-123", True)],
            "destination_exact_matches": [user(DESTINATION, "g-456", False)],
            "non_user_matches": [],
        },
        "drive": {
            "query": "'{}' in owners and trashed = false".format(SOURCE),
            "owned_nontrashed_count": count,
            "total_reported_bytes": 100 * count,
            "objects_without_reported_size": 0,
            "by_type": {"application/pdf": count},
            "sample": sample(min(count, 3)),
            "sample_size": min(count, 3),
            "sample_selection": "first 25 objects by ascending file id",
        },
        "limitations": [LIMITATION],
        "errors": [],
        "write_count": 0,
    }
    value.update(changes)
    return value


def inventory_report(google=None):
    return {
        "schema_version": 1,
        "record_type": "workspace_user_lifecycle_inventory",
        "mode": "inventory",
        "providers": {"google_workspace": deepcopy(google or google_inventory())},
        "write_count": 0,
        "tenant_writes_performed": False,
    }


def approval(plan):
    return {
        "decision": "approve",
        "approved_by": "ticket-42",
        "plan_digest": plan["plan_digest"],
        "confirmation": plan["required_confirmation"],
    }


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTransferAdapter:
    """Engine-level double: pre-transfer inventory until submit, then post-transfer inventory."""

    name = "google_workspace"

    def __init__(self, inventory, statuses=("COMPLETED",), post_inventory=None, destination_owns=True):
        self.inventory_value = deepcopy(inventory)
        self.post_inventory = deepcopy(post_inventory) if post_inventory is not None else None
        self.statuses = list(statuses)
        self.destination_owns = destination_owns
        self.submitted = False
        self.submit_calls = []
        self.status_calls = []
        self.verify_calls = []

    def _current(self):
        return deepcopy(self.post_inventory if (self.submitted and self.post_inventory is not None) else self.inventory_value)

    def transfer_inventory(self, request):
        return self._current()

    def transfer_submit(self, action, request):
        self.submit_calls.append(deepcopy(action))
        self.submitted = True
        return {"accepted": True, "http_status": 200, "transfer_id": "T-1"}

    def transfer_status(self, transfer_id):
        self.status_calls.append(transfer_id)
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return {"transfer_id": transfer_id, "overall_status": status, "old_owner_user_id": "g-123", "new_owner_user_id": "g-456"}

    def transfer_verify(self, plan, request, transfer_id=None):
        self.verify_calls.append(transfer_id)
        inventory = deepcopy(self.post_inventory if self.post_inventory is not None else self.inventory_value)
        count = inventory["drive"]["owned_nontrashed_count"]
        return {
            "verified": count == 0 and self.destination_owns,
            "inventory": inventory,
            "sample_ownership": [
                {"id": item["id"], "destination_is_owner": self.destination_owns}
                for item in plan["pre_transfer_inventory"]["sample"]
            ],
            "transfer_folder": {"resolution": "resolved_from_drive_parent_metadata", "id": "F-1", "name": SOURCE},
            "write_count": 0,
        }


def run_apply(adapter, plan, checkpoint, request_value=None, max_wait=25, clock=None, approval_value=None):
    clock = clock or FakeClock()
    return engine.execute_transfer(
        request_value or request(),
        plan,
        approval_value or approval(plan),
        {"google_workspace": adapter},
        checkpoint,
        poll_interval_seconds=10,
        max_wait_seconds=max_wait,
        sleep=clock.sleep,
        clock=clock,
    )


class TransferEngineTests(unittest.TestCase):
    def test_plan_binds_ids_inventory_sample_and_fixed_drive_params(self):
        plan = engine.build_plan(request(), inventory_report())
        self.assertEqual("approval_required", plan["status"])
        self.assertEqual([], plan["guard_errors"])
        self.assertEqual(0, plan["write_count"])
        self.assertFalse(plan["tenant_writes_performed"])
        (action,) = plan["actions"]
        self.assertEqual("google:transfer_drive_ownership", action["action_id"])
        self.assertEqual("g-123", action["old_owner_user_id"])
        self.assertEqual("g-456", action["new_owner_user_id"])
        self.assertEqual("55656082996", action["application_id"])
        self.assertEqual([{"key": "PRIVACY_LEVEL", "value": ["SHARED", "PRIVATE"]}], action["application_transfer_params"])
        self.assertEqual(3, plan["pre_transfer_inventory"]["owned_nontrashed_count"])
        self.assertEqual(["file-00", "file-01", "file-02"], [item["id"] for item in plan["pre_transfer_inventory"]["sample"]])
        self.assertEqual(
            engine.inventory_signature(google_inventory()), plan["inventory_signatures"]["google_workspace"]
        )
        self.assertTrue(plan["required_confirmation"].startswith("APPLY-DRIVE-TRANSFER:{}->{}:".format(SOURCE, DESTINATION)))
        self.assertTrue(plan["required_confirmation"].endswith(plan["plan_digest"]))
        self.assertNotIn("APPLY-OFFBOARD", plan["required_confirmation"])
        # Any bound field change invalidates the digest and the literal.
        drifted = deepcopy(plan)
        drifted["pre_transfer_inventory"]["sample"][0]["id"] = "other"
        self.assertNotEqual(plan["plan_digest"], engine.plan_digest(drifted))

    def test_offboarding_confirmation_literal_is_unchanged(self):
        plan = {"operation": "remove", "target": {"email": SOURCE}, "actions": []}
        self.assertTrue(engine.confirmation_for(plan).startswith("APPLY-OFFBOARD:{}:".format(SOURCE)))

    def test_identity_tenant_and_suspension_drift_block_the_plan(self):
        cases = {
            "source not suspended": (
                {"identity": {**google_inventory()["identity"], "source_exact_matches": [user(SOURCE, "g-123", False)]}},
                "google_workspace source user is not suspended",
            ),
            "destination suspended": (
                {"identity": {**google_inventory()["identity"], "destination_exact_matches": [user(DESTINATION, "g-456", True)]}},
                "google_workspace destination user is suspended or its state is unknown",
            ),
            "source id drift": (
                {"identity": {**google_inventory()["identity"], "source_exact_matches": [user(SOURCE, "g-999", True)]}},
                "google_workspace source immutable identity drifted",
            ),
            "destination absent": (
                {"identity": {**google_inventory()["identity"], "destination_exact_matches": []}},
                "google_workspace destination user identity is absent or ambiguous",
            ),
            "destination ambiguous": (
                {"identity": {**google_inventory()["identity"], "destination_exact_matches": [user(DESTINATION, "g-456", False), user(DESTINATION, "g-457", False)]}},
                "google_workspace destination user identity is absent or ambiguous",
            ),
            "wrong tenant": (
                {"identity": {**google_inventory()["identity"], "destination_exact_matches": [{**user(DESTINATION, "g-456", False), "customer_id": "C-other"}]}},
                "google_workspace destination user is not in the approved customer",
            ),
            "alias recipient": (
                {"identity": {**google_inventory()["identity"], "non_user_matches": [{"type": "alias_on_user", "immutable_id": "g-777"}]}},
                "google_workspace source or destination address resolves to a non-user recipient",
            ),
            "incomplete inventory": ({"complete": False}, "google_workspace inventory is incomplete"),
            "unknown count": ({"drive": {"owned_nontrashed_count": None}}, "google_workspace Drive ownership count is unknown"),
        }
        for label, (changes, expected) in cases.items():
            with self.subTest(label):
                plan = engine.build_plan(request(), inventory_report(google_inventory(**changes)))
                self.assertEqual("blocked", plan["status"])
                self.assertIn(expected, plan["guard_errors"])
                self.assertEqual([], plan["actions"])

    def test_request_validation_fails_closed(self):
        value = request()
        value["platforms"]["microsoft_365"] = {"disposition": "present", "immutable_id": "m-1", "tenant_id": "t", "expected_license_sku_ids": []}
        self.assertTrue(any("Google-only" in error for error in engine.validate_request(value)))
        value = request(transfer={"destination": {"email": SOURCE, "immutable_id": "g-123"}})
        self.assertIn("transfer.destination must be a different user than the source", engine.validate_request(value))
        value = request(transfer={"destination": {"email": DESTINATION}})
        self.assertIn("transfer.destination.immutable_id is required", engine.validate_request(value))
        value = request(policy={"approver": "ticket-42"})
        self.assertIn("policy.accepted_unknowns must explicitly be a list", engine.validate_request(value))
        value = request(policy={"approver": "ticket-42", "accepted_unknowns": []})
        plan = engine.build_plan(value, inventory_report())
        self.assertIn("google_workspace has unaccepted inventory limitations: " + LIMITATION, plan["guard_errors"])

    def test_inventory_all_dispatches_to_transfer_inventory_and_is_get_only(self):
        adapter = FakeTransferAdapter(google_inventory())
        report = engine.inventory_all(request(), {"google_workspace": adapter})
        self.assertEqual("inventory_complete", report["status"])
        self.assertEqual(0, report["write_count"])
        self.assertEqual([], adapter.submit_calls)
        self.assertTrue(report["providers"]["google_workspace"]["identity"]["source_exact_matches"][0]["suspended"])

    def test_apply_submits_once_polls_to_completion_and_verifies(self):
        plan = engine.build_plan(request(), inventory_report())
        adapter = FakeTransferAdapter(google_inventory(), statuses=["INPROGRESS", "COMPLETED"], post_inventory=google_inventory(0))
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            report = run_apply(adapter, plan, checkpoint, clock=clock)
            saved = engine.load_json(checkpoint)
        self.assertEqual("completed_and_verified", report["status"])
        self.assertEqual("T-1", report["transfer_id"])
        self.assertEqual(1, report["write_count"])
        self.assertEqual(1, len(adapter.submit_calls))
        self.assertEqual(["T-1", "T-1"], adapter.status_calls)
        self.assertEqual([10], clock.sleeps)
        self.assertEqual("verified", saved["actions"]["google:transfer_drive_ownership"]["status"])
        self.assertEqual("T-1", saved["actions"]["google:transfer_drive_ownership"]["transfer_id"])
        self.assertEqual("COMPLETED", report["actions"][0]["poll"]["overall_status"])
        self.assertEqual(SOURCE, report["actions"][0]["verification"]["transfer_folder"]["name"])
        self.assertFalse(report["human_review_required"])
        self.assertEqual(0, report["actions"][0]["verification"]["inventory"]["drive"]["owned_nontrashed_count"])

    def test_timeout_returns_pending_with_recorded_transfer_id_not_failure(self):
        plan = engine.build_plan(request(), inventory_report())
        adapter = FakeTransferAdapter(google_inventory(), statuses=["INPROGRESS"], post_inventory=google_inventory(0))
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            report = run_apply(adapter, plan, checkpoint, max_wait=25, clock=clock)
            saved = engine.load_json(checkpoint)
        self.assertEqual("transfer_pending", report["status"])
        self.assertEqual("pending_max_wait_elapsed", report["actions"][0]["status"])
        self.assertEqual("PENDING", report["actions"][0]["poll"]["overall_status"])
        self.assertEqual(25, report["actions"][0]["poll"]["elapsed_seconds"])
        self.assertEqual([10, 10, 5], clock.sleeps)
        self.assertEqual("T-1", report["resume"]["transfer_id"])
        self.assertFalse(report["human_review_required"])
        self.assertEqual("submitted", saved["actions"]["google:transfer_drive_ownership"]["status"])
        self.assertEqual("T-1", saved["actions"]["google:transfer_drive_ownership"]["transfer_id"])
        self.assertEqual(1, saved["write_count"])
        self.assertEqual([], adapter.verify_calls)

    def test_resume_polls_recorded_transfer_id_and_never_resubmits(self):
        plan = engine.build_plan(request(), inventory_report())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            first = FakeTransferAdapter(google_inventory(), statuses=["INPROGRESS"], post_inventory=google_inventory(0))
            self.assertEqual("transfer_pending", run_apply(first, plan, checkpoint, max_wait=5)["status"])
            second = FakeTransferAdapter(google_inventory(0), statuses=["COMPLETED"], post_inventory=google_inventory(0))
            report = run_apply(second, plan, checkpoint)
            saved = engine.load_json(checkpoint)
            third = FakeTransferAdapter(google_inventory(0), post_inventory=google_inventory(0))
            rerun = run_apply(third, plan, checkpoint)
        self.assertEqual("completed_and_verified", report["status"])
        self.assertEqual([], second.submit_calls)
        self.assertEqual(["T-1"], second.status_calls)
        self.assertEqual(0, report["write_count"])
        self.assertTrue(report["actions"][0]["resumed_recorded_transfer_id_without_resubmit"])
        self.assertEqual("verified", saved["actions"]["google:transfer_drive_ownership"]["status"])
        self.assertEqual("verified_complete_no_write", rerun["status"])
        self.assertEqual([], third.submit_calls)
        self.assertEqual("already_verified_no_write", rerun["actions"][0]["status"])

    def test_about_to_submit_checkpoint_without_id_is_never_resubmitted(self):
        plan = engine.build_plan(request(), inventory_report())
        value = engine.initial_checkpoint(plan)
        value["actions"] = {"google:transfer_drive_ownership": {"status": "about_to_submit"}}
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            engine.atomic_write_json(checkpoint, value)
            adapter = FakeTransferAdapter(google_inventory())
            report = run_apply(adapter, plan, checkpoint)
            self.assertEqual("partial_failure", report["status"])
            self.assertEqual("indeterminate_prior_submit_not_retried", report["actions"][0]["status"])
            self.assertTrue(report["human_review_required"])
            self.assertEqual([], adapter.submit_calls)
            self.assertEqual(0, report["write_count"])
            recovered = FakeTransferAdapter(google_inventory(), post_inventory=google_inventory(0))
            report = run_apply(recovered, plan, checkpoint)
            saved = engine.load_json(checkpoint)
        self.assertEqual("verified_complete_no_write", report["status"])
        self.assertEqual("recovered_by_readback_no_write", report["actions"][0]["status"])
        self.assertEqual([], recovered.submit_calls)
        self.assertEqual("verified", saved["actions"]["google:transfer_drive_ownership"]["status"])

    def test_provider_failed_is_reported_and_not_resubmitted(self):
        plan = engine.build_plan(request(), inventory_report())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            adapter = FakeTransferAdapter(google_inventory(), statuses=["FAILED"])
            first = run_apply(adapter, plan, checkpoint)
            again = FakeTransferAdapter(google_inventory())
            second = run_apply(again, plan, checkpoint)
        self.assertEqual("transfer_failed", first["status"])
        self.assertTrue(first["human_review_required"])
        self.assertEqual("transfer_failed", second["status"])
        self.assertEqual("provider_reported_failed_not_resubmitted", second["actions"][0]["status"])
        self.assertEqual([], again.submit_calls)

    def test_fresh_preflight_drift_and_bad_approval_refuse_before_submit(self):
        plan = engine.build_plan(request(), inventory_report())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            unsuspended = google_inventory(identity={**google_inventory()["identity"], "source_exact_matches": [user(SOURCE, "g-123", False)]})
            adapter = FakeTransferAdapter(unsuspended)
            drift = run_apply(adapter, plan, checkpoint)
            self.assertEqual("refused", drift["status"])
            self.assertIn("google_workspace source user is not suspended", drift["fresh_preflight_errors"])
            self.assertEqual([], adapter.submit_calls)
            more_files = FakeTransferAdapter(google_inventory(4))
            drift = run_apply(more_files, plan, checkpoint)
            self.assertIn("google_workspace material inventory drifted after approval", drift["fresh_preflight_errors"])
            self.assertEqual([], more_files.submit_calls)
            wrong_literal = approval(plan)
            wrong_literal["confirmation"] = "APPLY-OFFBOARD:{}:{}".format(SOURCE, plan["plan_digest"])
            adapter = FakeTransferAdapter(google_inventory())
            refused = run_apply(adapter, plan, checkpoint, approval_value=wrong_literal)
            self.assertEqual("refused", refused["status"])
            self.assertIn("literal confirmation is missing or incorrect", refused["approval_errors"])
            retargeted = request(transfer={"destination": {"email": "other@example.test", "immutable_id": "g-789"}})
            refused = run_apply(adapter, plan, checkpoint, request_value=retargeted)
            self.assertIn("request.transfer does not match the approved plan", refused["approval_errors"])
            self.assertEqual([], adapter.submit_calls)
            self.assertFalse(os.path.exists(checkpoint))

    def test_completed_transfer_bound_to_other_ids_is_not_verified(self):
        plan = engine.build_plan(request(), inventory_report())
        adapter = FakeTransferAdapter(google_inventory(), post_inventory=google_inventory(0))
        adapter.transfer_status = lambda transfer_id: {"overall_status": "COMPLETED", "old_owner_user_id": "g-123", "new_owner_user_id": "g-999"}
        with tempfile.TemporaryDirectory() as tmp:
            report = run_apply(adapter, plan, os.path.join(tmp, "checkpoint.json"))
        self.assertEqual("partial_failure", report["status"])
        self.assertIn("different owner IDs", report["actions"][0]["verification"]["error"])
        self.assertEqual([], adapter.verify_calls)

    def test_verify_requires_zero_source_ownership_and_destination_sample(self):
        plan = engine.build_plan(request(), inventory_report())
        checkpoint = engine.initial_checkpoint(plan)
        checkpoint["actions"] = {"google:transfer_drive_ownership": {"status": "submitted", "transfer_id": "T-1"}}
        good = FakeTransferAdapter(google_inventory(), post_inventory=google_inventory(0))
        report = engine.verify_transfer(request(), plan, {"google_workspace": good}, checkpoint)
        self.assertEqual("verified_complete_no_write", report["status"])
        self.assertEqual("T-1", report["transfer_id"])
        self.assertEqual(["T-1"], good.verify_calls)
        self.assertEqual(0, report["write_count"])
        remaining = FakeTransferAdapter(google_inventory(), post_inventory=google_inventory(1))
        self.assertEqual("verification_failed", engine.verify_transfer(request(), plan, {"google_workspace": remaining})["status"])
        not_owner = FakeTransferAdapter(google_inventory(), post_inventory=google_inventory(0), destination_owns=False)
        self.assertEqual("verification_failed", engine.verify_transfer(request(), plan, {"google_workspace": not_owner})["status"])
        unsuspended = google_inventory(0, identity={**google_inventory()["identity"], "source_exact_matches": [user(SOURCE, "g-123", False)]})
        drifted = FakeTransferAdapter(google_inventory(), post_inventory=unsuspended)
        report = engine.verify_transfer(request(), plan, {"google_workspace": drifted})
        self.assertEqual("verification_failed", report["status"])
        self.assertIn("google_workspace source user is not suspended", report["providers"]["google_workspace"]["guard_errors"])
        tampered = deepcopy(plan)
        tampered["transfer"]["destination"]["immutable_id"] = "g-999"
        report = engine.verify_transfer(request(), tampered, {"google_workspace": good})
        self.assertEqual("verification_failed", report["status"])
        self.assertIn("plan digest is invalid or plan drifted", report["adapter_errors"])

    def test_remove_operation_still_refuses_inline_transfer_policy(self):
        with open(os.path.join(HERE, "..", "templates", "remove-request.example.json"), encoding="utf-8") as handle:
            remove = json.load(handle)
        with open(os.path.join(HERE, "fixtures", "pilot-like-inventory.json"), encoding="utf-8") as handle:
            inventory = json.load(handle)
        remove["policy"]["files"] = "transfer"
        remove["policy"]["transfer_destination"] = DESTINATION
        plan = engine.build_plan(remove, inventory)
        self.assertEqual("blocked", plan["status"])
        self.assertTrue(any(engine.TRANSFER_OPERATION in error for error in plan["guard_errors"]))

    def test_example_template_plans_without_writes(self):
        with open(os.path.join(HERE, "..", "templates", "transfer-request.example.json"), encoding="utf-8") as handle:
            example = json.load(handle)
        self.assertEqual([], engine.validate_request(example))
        plan = engine.build_plan(example, inventory_report())
        self.assertEqual("approval_required", plan["status"])
        self.assertNotIn("private_key", json.dumps(plan))


class TransferEngineGuardTests(unittest.TestCase):
    def test_engine_allowlist_refuses_tampered_action_before_submit(self):
        # A plan whose action names other IDs, re-signed so approval/digest binding passes,
        # is still refused by the engine before the adapter is ever asked to submit.
        plan = engine.build_plan(request(), inventory_report())
        plan["actions"][0]["new_owner_user_id"] = "g-999"
        plan["plan_digest"] = engine.plan_digest(plan)
        plan["required_confirmation"] = engine.confirmation_for(plan)
        adapter = FakeTransferAdapter(google_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            report = run_apply(adapter, plan, checkpoint)
            self.assertFalse(os.path.exists(checkpoint))
        self.assertEqual("refused", report["status"])
        self.assertIn("action.new_owner_user_id is outside the approved exact-ID allowlist", report["fresh_preflight_errors"])
        self.assertEqual([], adapter.submit_calls)
        self.assertEqual(0, report["write_count"])

    def test_execute_plan_refuses_transfer_plans(self):
        plan = engine.build_plan(request(), inventory_report())
        adapter = FakeTransferAdapter(google_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            report = engine.execute_plan(request(), plan, approval(plan), {"google_workspace": adapter}, checkpoint)
            self.assertFalse(os.path.exists(checkpoint))
        self.assertEqual("refused", report["status"])
        self.assertIn("{} plans execute only through execute_transfer".format(engine.TRANSFER_OPERATION), report["approval_errors"])
        self.assertEqual([], adapter.submit_calls)


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = {}

    def json(self):
        return self._body


def directory_body(email, immutable_id, suspended):
    return {"id": immutable_id, "primaryEmail": email, "customerId": "C-example", "suspended": suspended}


@unittest.skipIf(adapters_module is None, "requests/google-auth not installed")
class TransferAdapterTests(unittest.TestCase):
    def adapter(self, users=None, drive_pages=None, files=None):
        adapter = object.__new__(adapters_module.GoogleWorkspaceAdapter)
        adapter.credential_path = "external-only"
        adapter.admin_subject = "admin@example.test"
        users = users if users is not None else {
            SOURCE: directory_body(SOURCE, "g-123", True),
            "g-123": directory_body(SOURCE, "g-123", True),
            DESTINATION: directory_body(DESTINATION, "g-456", False),
            "g-456": directory_body(DESTINATION, "g-456", False),
        }
        adapter._user_get = mock.Mock(side_effect=lambda key: FakeResponse(200, users[key]) if key in users else FakeResponse(404, {"error": {"message": "not found"}}))
        drive_pages = drive_pages if drive_pages is not None else {None: {"files": []}}
        files = files or {}
        adapter.drive_calls = []

        def drive_get(url, params=None, timeout=None):
            if url.endswith("/files"):
                adapter.drive_calls.append(dict(params or {}))
                return FakeResponse(200, drive_pages[(params or {}).get("pageToken")])
            file_id = url.rsplit("/", 1)[1]
            return FakeResponse(200, files[file_id]) if file_id in files else FakeResponse(404, {"error": {"message": "not found"}})

        drive_session = mock.Mock()
        drive_session.get = mock.Mock(side_effect=drive_get)
        adapter.datatransfer = mock.Mock()
        adapter.datatransfer.post = mock.Mock(return_value=FakeResponse(200, {"id": "T-1", "overallTransferStatusCode": "inProgress"}))
        adapter.datatransfer.get = mock.Mock(return_value=FakeResponse(200, {
            "id": "T-1", "overallTransferStatusCode": "completed", "oldOwnerUserId": "g-123", "newOwnerUserId": "g-456",
            "requestTime": "2026-09-03T10:00:00.000Z",
            "applicationDataTransfers": [{"applicationId": "55656082996", "applicationTransferStatus": "completed"}],
        }))
        adapter._sessions = {"drive:admin@example.test": drive_session, "datatransfer:admin@example.test": adapter.datatransfer}
        # transfer_verify mints fresh sessions; keep the mocks reachable afterwards.
        adapter.session = lambda key, subject=None, _mocks={"drive": drive_session, "datatransfer": adapter.datatransfer}: _mocks[key]
        return adapter

    def test_inventory_uses_literal_admin_query_paginates_and_reports_bytes(self):
        pages = {
            None: {"nextPageToken": "p2", "files": [
                {"id": "z-file", "mimeType": "application/pdf", "size": "100", "parents": ["root-src"]},
                {"id": "m-folder", "mimeType": "application/vnd.google-apps.folder", "parents": ["root-src"]},
            ]},
            "p2": {"files": [
                {"id": "a-doc", "mimeType": "application/vnd.google-apps.document", "parents": ["m-folder"]},
                {"id": "b-file", "mimeType": "application/pdf", "size": "50", "parents": ["root-src"]},
            ]},
        }
        adapter = self.adapter(drive_pages=pages)
        result = adapter.transfer_inventory(request())
        self.assertTrue(result["complete"])
        self.assertEqual(0, result["write_count"])
        self.assertEqual(2, len(adapter.drive_calls))
        self.assertEqual("'{}' in owners and trashed = false".format(SOURCE), adapter.drive_calls[0]["q"])
        self.assertNotIn("pageToken", adapter.drive_calls[0])
        self.assertEqual("p2", adapter.drive_calls[1]["pageToken"])
        self.assertEqual(4, result["drive"]["owned_nontrashed_count"])
        self.assertEqual(150, result["drive"]["total_reported_bytes"])
        self.assertEqual(2, result["drive"]["objects_without_reported_size"])
        self.assertEqual({"application/pdf": 2, "application/vnd.google-apps.folder": 1, "application/vnd.google-apps.document": 1}, result["drive"]["by_type"])
        self.assertEqual(["a-doc", "b-file", "m-folder", "z-file"], [item["id"] for item in result["drive"]["sample"]])
        self.assertNotIn("name", json.dumps(result))
        self.assertTrue(result["identity"]["source_exact_matches"][0]["suspended"])
        self.assertFalse(result["identity"]["destination_exact_matches"][0]["suspended"])
        self.assertEqual(["google_drive_transfer_inventory_bounded_to_admin_subject_visibility"], result["limitations"])
        adapter.datatransfer.post.assert_not_called()

    def test_sample_is_bounded_and_deterministic(self):
        files = [{"id": "f-{:03d}".format(index), "mimeType": "application/pdf", "size": "1"} for index in reversed(range(40))]
        adapter = self.adapter(drive_pages={None: {"files": files}})
        result = adapter.transfer_inventory(request())["drive"]
        self.assertEqual(40, result["owned_nontrashed_count"])
        self.assertEqual(engine.TRANSFER_SAMPLE_SIZE, result["sample_size"])
        self.assertEqual(["f-{:03d}".format(index) for index in range(engine.TRANSFER_SAMPLE_SIZE)], [item["id"] for item in result["sample"]])

    def test_submit_posts_exact_payload_with_immutable_ids(self):
        plan = engine.build_plan(request(), inventory_report())
        adapter = self.adapter()
        result = adapter.transfer_submit(plan["actions"][0], request())
        adapter.datatransfer.post.assert_called_once_with(
            "https://admin.googleapis.com/admin/datatransfer/v1/transfers",
            json={
                "oldOwnerUserId": "g-123",
                "newOwnerUserId": "g-456",
                "applicationDataTransfers": [{
                    "applicationId": "55656082996",
                    "applicationTransferParams": [{"key": "PRIVACY_LEVEL", "value": ["SHARED", "PRIVATE"]}],
                }],
            },
            timeout=60,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual("T-1", result["transfer_id"])
        self.assertEqual("INPROGRESS", result["overall_status"])

    def test_submit_refuses_allowlist_and_state_drift(self):
        plan = engine.build_plan(request(), inventory_report())
        action = deepcopy(plan["actions"][0])
        action["application_id"] = "123"
        adapter = self.adapter()
        with self.assertRaisesRegex(adapters_module.LifecycleError, "allowlist"):
            adapter.transfer_submit(action, request())
        action = deepcopy(plan["actions"][0])
        action["application_transfer_params"] = [{"key": "PRIVACY_LEVEL", "value": ["PRIVATE"]}]
        with self.assertRaisesRegex(adapters_module.LifecycleError, "allowlist"):
            adapter.transfer_submit(action, request())
        adapter = self.adapter(users={
            SOURCE: directory_body(SOURCE, "g-123", False), "g-123": directory_body(SOURCE, "g-123", False),
            DESTINATION: directory_body(DESTINATION, "g-456", False), "g-456": directory_body(DESTINATION, "g-456", False),
        })
        with self.assertRaisesRegex(adapters_module.LifecycleError, "not suspended"):
            adapter.transfer_submit(plan["actions"][0], request())
        adapter = self.adapter(users={
            SOURCE: directory_body(SOURCE, "g-123", True), "g-123": directory_body(SOURCE, "g-123", True),
            DESTINATION: directory_body(DESTINATION, "g-456", True), "g-456": directory_body(DESTINATION, "g-456", True),
        })
        with self.assertRaisesRegex(adapters_module.LifecycleError, "destination user is suspended"):
            adapter.transfer_submit(plan["actions"][0], request())
        adapter.datatransfer.post.assert_not_called()

    def test_verify_reads_back_zero_source_ownership_sample_owner_and_folder(self):
        plan = engine.build_plan(request(), inventory_report())
        owned = lambda parents: {"id": "x", "trashed": False, "owners": [{"emailAddress": "Sofia@Example.test"}], "parents": parents}
        files = {
            "file-00": owned(["F-1"]),
            "file-01": owned(["F-1"]),
            "file-02": owned(["root-src"]),
            "F-1": {"id": "F-1", "name": SOURCE, "mimeType": "application/vnd.google-apps.folder", "owners": [{"emailAddress": DESTINATION}]},
        }
        adapter = self.adapter(files=files)
        result = adapter.transfer_verify(plan, request(), "T-1")
        self.assertTrue(result["verified"])
        self.assertEqual(0, result["remaining_source_owned_nontrashed_count"])
        self.assertEqual(3, result["sample_checked"])
        self.assertTrue(all(item["destination_is_owner"] for item in result["sample_ownership"]))
        self.assertEqual("COMPLETED", result["transfer_status"]["overall_status"])
        self.assertEqual({"resolution": "resolved_from_drive_parent_metadata", "id": "F-1", "name": SOURCE}, result["transfer_folder"])
        self.assertEqual(0, result["write_count"])
        files["file-01"]["owners"] = [{"emailAddress": SOURCE}]
        self.assertFalse(self.adapter(files=files).transfer_verify(plan, request(), "T-1")["verified"])
        del files["file-01"]
        self.assertFalse(self.adapter(files=files).transfer_verify(plan, request())["verified"])
        remaining = self.adapter(files=files, drive_pages={None: {"files": [{"id": "left", "mimeType": "application/pdf", "size": "1"}]}})
        self.assertFalse(remaining.transfer_verify(plan, request())["verified"])

    def test_verify_reports_unresolved_folder_instead_of_inventing_one(self):
        plan = engine.build_plan(request(), inventory_report())
        files = {item["id"]: {"id": item["id"], "trashed": False, "owners": [{"emailAddress": DESTINATION}], "parents": ["root-src"]} for item in sample()}
        result = self.adapter(files=files).transfer_verify(plan, request())
        self.assertTrue(result["verified"])
        self.assertEqual("unresolved", result["transfer_folder"]["resolution"])
        self.assertIsNone(result["transfer_folder"].get("name"))


@unittest.skipIf(adapters_module is None, "requests/google-auth not installed")
class TransferCliTests(unittest.TestCase):
    def test_dry_run_and_flag_bounds(self):
        import user_lifecycle
        with tempfile.TemporaryDirectory() as tmp:
            request_path = os.path.join(tmp, "request.json")
            inventory_path = os.path.join(tmp, "inventory.json")
            output = os.path.join(tmp, "plan.json")
            with open(request_path, "w", encoding="utf-8") as handle:
                json.dump(request(), handle)
            with open(inventory_path, "w", encoding="utf-8") as handle:
                json.dump(inventory_report(), handle)
            with mock.patch("sys.stdout"):
                code = user_lifecycle.main(["dry-run", "--request", request_path, "--inventory", inventory_path, "--output", output])
            plan = engine.load_json(output)
        self.assertEqual(0, code)
        self.assertEqual("dry_run", plan["mode"])
        self.assertEqual("approval_required", plan["status"])
        self.assertEqual(0, plan["write_count"])
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            user_lifecycle.parser().parse_args(["apply", "--request", "r", "--output", "o", "--max-wait-seconds", "7201"])
        args = user_lifecycle.parser().parse_args(["apply", "--request", "r", "--output", "o"])
        self.assertLessEqual(args.max_wait_seconds, 7200)


if __name__ == "__main__":
    unittest.main()
