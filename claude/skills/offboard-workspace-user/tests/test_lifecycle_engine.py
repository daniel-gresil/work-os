import json
import os
import tempfile
import unittest
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
import sys
sys.path.insert(0, SCRIPTS)

import lifecycle_engine as subject


class FakeAdapter:
    def __init__(self, name, inventory, fail_verification_for=None):
        self.name = name
        self.inventory_value = deepcopy(inventory)
        self.fail_verification_for = set(fail_verification_for or [])
        self.satisfied = set()
        self.write_calls = []
        self.inventory_calls = 0

    def inventory(self, request):
        self.inventory_calls += 1
        return deepcopy(self.inventory_value)

    def apply_action(self, action, request):
        action_id = action["action_id"]
        self.write_calls.append(action_id)
        if action_id not in self.fail_verification_for:
            self.satisfied.add(action_id)
        return {"accepted": True, "http_status": 204}

    def verify_action(self, action, request):
        action_id = action["action_id"]
        return {"verified": action_id in self.satisfied}

    def verify_terminal(self, request):
        disposition = request["platforms"][self.name]["disposition"]
        if disposition == "absent":
            return {"verified": True, "write_count": 0}
        planned = {
            action_id
            for action_id in self.write_calls
            if action_id.startswith("google:") if self.name == "google_workspace"
        }
        if self.name == "microsoft_365":
            planned = {action_id for action_id in self.write_calls if action_id.startswith("microsoft:")}
        return {"verified": bool(planned) and planned.issubset(self.satisfied), "write_count": 0}


def request(**changes):
    value = {
        "schema_version": 1,
        "operation": "remove",
        "target": {"email": "departing.user@example.test"},
        "platforms": {
            "google_workspace": {
                "disposition": "present",
                "immutable_id": "g-123",
                "customer_id": "C-example",
                "license_product_ids": list(subject.GOOGLE_LICENSE_PRODUCT_CATALOG),
                "license_product_catalog_complete": True,
                "expected_licenses": [{"product_id": "Google-Apps", "sku_id": "sku-example"}],
            },
            "microsoft_365": {"disposition": "absent", "tenant_id": "tenant-example"},
        },
        "policy": {
            "mail": "delete",
            "files": "delete",
            "transfer_destination": None,
            "legal_hold": "none_known",
            "license": "release_on_delete",
            "deletion": "immediate",
            "approver": "ticket-42",
            "accepted_unknowns": [],
        },
    }
    for key, item in changes.items():
        value[key] = item
    return value


def google_inventory(**changes):
    value = {
        "status": "ok",
        "complete": True,
        "customer_id": "C-example",
        "identity": {
            "exact_matches": [{"email": "departing.user@example.test", "immutable_id": "g-123"}],
            "non_user_matches": [],
        },
        "groups": [],
        "roles": [],
        "licenses": [{"product_id": "Google-Apps", "sku_id": "sku-example", "user_id": "departing.user@example.test"}],
        "drive": {"owned_nontrashed_count": 0},
        "mailbox": {"exists": True},
        "errors": [],
        "write_count": 0,
    }
    value.update(changes)
    return value


def microsoft_absent_inventory(**changes):
    value = {
        "status": "ok",
        "complete": True,
        "tenant_id": "tenant-example",
        "identity": {"exact_matches": [], "non_user_matches": []},
        "protected_same_localpart": [{"immutable_id": "protected-1", "canonical_upn": "departing.user@other.test"}],
        "errors": [],
        "write_count": 0,
    }
    value.update(changes)
    return value


def inventory_report(google=None, microsoft=None):
    return {
        "schema_version": 1,
        "record_type": "workspace_user_lifecycle_inventory",
        "mode": "inventory",
        "providers": {
            "google_workspace": deepcopy(google or google_inventory()),
            "microsoft_365": deepcopy(microsoft or microsoft_absent_inventory()),
        },
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


class LifecycleEngineTests(unittest.TestCase):
    def test_skill_frontmatter_is_valid_and_trigger_focused(self):
        skill = os.path.abspath(os.path.join(HERE, "..", "SKILL.md"))
        with open(skill, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual("---", lines[0])
        closing = lines.index("---", 1)
        frontmatter = lines[1:closing]
        name = next(line.split(":", 1)[1].strip() for line in frontmatter if line.startswith("name:"))
        description = next(line.split(":", 1)[1].strip().strip('"') for line in frontmatter if line.startswith("description:"))
        self.assertEqual("offboard-workspace-user", name)
        self.assertTrue(description.startswith("Use when"))
        self.assertLess(len(description), 1024)

    def test_pilot_like_fixture_reproduces_delete_only_plan(self):
        with open(os.path.join(HERE, "..", "templates", "remove-request.example.json"), encoding="utf-8") as handle:
            example_request = json.load(handle)
        with open(os.path.join(HERE, "fixtures", "pilot-like-inventory.json"), encoding="utf-8") as handle:
            example_inventory = json.load(handle)
        plan = subject.build_plan(example_request, example_inventory)
        self.assertEqual("approval_required", plan["status"])
        self.assertEqual([], plan["guard_errors"])
        self.assertEqual(
            ["google:suspend", "google:revoke_sessions", "google:delete"],
            [item["action_id"] for item in plan["actions"]],
        )
        self.assertEqual(0, plan["write_count"])

    def test_google_catalog_completeness_requires_explicit_attestation(self):
        value = request()
        del value["platforms"]["google_workspace"]["license_product_catalog_complete"]
        errors = subject.validate_request(value)
        self.assertIn(
            "platforms.google_workspace.license_product_catalog_complete must explicitly be true",
            errors,
        )

    def test_resume_signature_ignores_expected_state_but_not_dependency_drift(self):
        original = google_inventory()
        changed_state = deepcopy(original)
        changed_state["identity"]["exact_matches"][0]["suspended"] = True
        changed_state["licenses"] = []
        self.assertEqual(
            subject.inventory_signature(original, resume=True),
            subject.inventory_signature(changed_state, resume=True),
        )
        changed_state["groups"] = [{"id": "unexpected-group"}]
        self.assertNotEqual(
            subject.inventory_signature(original, resume=True),
            subject.inventory_signature(changed_state, resume=True),
        )

    def test_parallel_inventory_is_get_only_and_complete(self):
        adapters = {
            "google_workspace": FakeAdapter("google_workspace", google_inventory()),
            "microsoft_365": FakeAdapter("microsoft_365", microsoft_absent_inventory()),
        }
        report = subject.inventory_all(request(), adapters, max_workers=2)
        self.assertEqual("inventory_complete", report["status"])
        self.assertEqual(0, report["write_count"])
        self.assertFalse(report["tenant_writes_performed"])
        self.assertEqual([], adapters["google_workspace"].write_calls)
        self.assertEqual([], adapters["microsoft_365"].write_calls)

    def test_identity_ambiguity_and_non_user_recipient_fail_closed(self):
        ambiguous = google_inventory(identity={
            "exact_matches": [
                {"email": "departing.user@example.test", "immutable_id": "g-123"},
                {"email": "departing.user@example.test", "immutable_id": "g-999"},
            ],
            "non_user_matches": [{"type": "group", "immutable_id": "group-1"}],
        })
        inv = inventory_report(google=ambiguous)
        plan = subject.build_plan(request(), inv)
        self.assertEqual("blocked", plan["status"])
        self.assertIn("google_workspace exact user identity is ambiguous or is a non-user recipient", plan["guard_errors"])
        self.assertEqual([], plan["actions"])

    def test_missing_policy_refuses_unsafe_action(self):
        value = request(policy={"mail": "delete"})
        plan = subject.build_plan(value, inventory_report())
        self.assertEqual("blocked", plan["status"])
        self.assertTrue(any("legal_hold" in error for error in plan["guard_errors"]))
        self.assertTrue(any("approver" in error for error in plan["guard_errors"]))

    def test_absent_platform_is_verified_no_op(self):
        report = subject.inventory_all(
            request(),
            {
                "google_workspace": FakeAdapter("google_workspace", google_inventory()),
                "microsoft_365": FakeAdapter("microsoft_365", microsoft_absent_inventory()),
            },
        )
        self.assertEqual("inventory_complete", report["status"])
        plan = subject.build_plan(request(), report)
        self.assertFalse(any(item["provider"] == "microsoft_365" for item in plan["actions"]))

    def test_platform_specific_google_only_is_supported(self):
        value = request()
        value["platforms"]["microsoft_365"] = {"disposition": "skip"}
        adapters = {"google_workspace": FakeAdapter("google_workspace", google_inventory())}
        inv = subject.inventory_all(value, adapters)
        self.assertEqual("inventory_complete", inv["status"])
        plan = subject.build_plan(value, inv)
        self.assertEqual("approval_required", plan["status"])

    def test_dry_run_has_zero_writes_and_auto_license_skips_direct_removal(self):
        plan = subject.build_plan(request(), inventory_report())
        self.assertEqual("approval_required", plan["status"])
        self.assertEqual(0, plan["write_count"])
        self.assertFalse(plan["tenant_writes_performed"])
        self.assertEqual(
            ["google:suspend", "google:revoke_sessions", "google:delete"],
            [item["action_id"] for item in plan["actions"]],
        )
        self.assertNotIn("google:remove_license", [item["action_id"] for item in plan["actions"]])

    def test_transfer_is_parameterized_but_not_silently_executed(self):
        value = request()
        value["policy"]["files"] = "transfer"
        value["policy"]["transfer_destination"] = "owner@example.test"
        plan = subject.build_plan(value, inventory_report())
        self.assertEqual("blocked", plan["status"])
        self.assertTrue(any("transfer execution" in error for error in plan["guard_errors"]))

    def test_plan_and_approval_hash_drift_refuse_before_write(self):
        plan = subject.build_plan(request(), inventory_report())
        value = approval(plan)
        plan["policy"]["mail"] = "retain"
        adapter = FakeAdapter("google_workspace", google_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            report = subject.execute_plan(request(), plan, value, {"google_workspace": adapter}, os.path.join(tmp, "checkpoint.json"))
        self.assertEqual("refused", report["status"])
        self.assertEqual([], adapter.write_calls)
        self.assertIn("plan digest is invalid or plan drifted", report["approval_errors"])

    def test_approved_plan_cannot_be_retargeted_by_apply_request(self):
        approved_request = request()
        plan = subject.build_plan(approved_request, inventory_report())
        retargeted = deepcopy(approved_request)
        retargeted["target"]["email"] = "other.user@example.test"
        adapter = FakeAdapter("google_workspace", google_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            report = subject.execute_plan(
                retargeted,
                plan,
                approval(plan),
                {"google_workspace": adapter},
                os.path.join(tmp, "checkpoint.json"),
            )
        self.assertEqual("refused", report["status"])
        self.assertEqual([], adapter.write_calls)
        self.assertIn("request.target does not match the approved plan", report["approval_errors"])

    def test_about_to_write_checkpoint_never_blindly_retries_session_revoke(self):
        plan = subject.build_plan(request(), inventory_report())
        google = FakeAdapter("google_workspace", google_inventory())
        google.satisfied.add("google:suspend")
        microsoft = FakeAdapter("microsoft_365", microsoft_absent_inventory())
        checkpoint_value = subject.initial_checkpoint(plan)
        checkpoint_value["actions"] = {
            "google:suspend": {"status": "verified"},
            "google:revoke_sessions": {"status": "about_to_write"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            subject.atomic_write_json(checkpoint, checkpoint_value)
            report = subject.execute_plan(
                request(),
                plan,
                approval(plan),
                {"google_workspace": google, "microsoft_365": microsoft},
                checkpoint,
            )
        self.assertEqual("partial_failure", report["status"])
        self.assertEqual([], google.write_calls)
        self.assertEqual("indeterminate_prior_write_not_retried", report["actions"][1]["status"])

    def test_failed_verification_checkpoints_and_never_blindly_retries(self):
        plan = subject.build_plan(request(), inventory_report())
        adapter = FakeAdapter("google_workspace", google_inventory(), {"google:suspend"})
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            first = subject.execute_plan(request(), plan, approval(plan), {"google_workspace": adapter, "microsoft_365": FakeAdapter("microsoft_365", microsoft_absent_inventory())}, checkpoint)
            self.assertEqual("partial_failure", first["status"])
            self.assertEqual(["google:suspend"], adapter.write_calls)
            second = subject.execute_plan(request(), plan, approval(plan), {"google_workspace": adapter, "microsoft_365": FakeAdapter("microsoft_365", microsoft_absent_inventory())}, checkpoint)
            self.assertEqual("partial_failure", second["status"])
            self.assertEqual(["google:suspend"], adapter.write_calls)
            self.assertEqual("indeterminate_prior_write_not_retried", second["actions"][0]["status"])

    def test_partial_completion_resumes_from_verified_readback(self):
        plan = subject.build_plan(request(), inventory_report())
        google = FakeAdapter("google_workspace", google_inventory(), {"google:revoke_sessions"})
        microsoft = FakeAdapter("microsoft_365", microsoft_absent_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            first = subject.execute_plan(request(), plan, approval(plan), {"google_workspace": google, "microsoft_365": microsoft}, checkpoint)
            self.assertEqual("partial_failure", first["status"])
            self.assertEqual(["google:suspend", "google:revoke_sessions"], google.write_calls)
            google.fail_verification_for.clear()
            google.satisfied.add("google:revoke_sessions")
            resumed = subject.execute_plan(request(), plan, approval(plan), {"google_workspace": google, "microsoft_365": microsoft}, checkpoint)
            self.assertEqual("completed_and_verified", resumed["status"])
            self.assertEqual(["google:suspend", "google:revoke_sessions", "google:delete"], google.write_calls)
            self.assertEqual("already_verified_no_write", resumed["actions"][0]["status"])
            self.assertEqual("recovered_by_readback_no_write", resumed["actions"][1]["status"])

    def test_repeated_execution_is_idempotent_zero_write(self):
        plan = subject.build_plan(request(), inventory_report())
        google = FakeAdapter("google_workspace", google_inventory())
        microsoft = FakeAdapter("microsoft_365", microsoft_absent_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            first = subject.execute_plan(request(), plan, approval(plan), {"google_workspace": google, "microsoft_365": microsoft}, checkpoint)
            self.assertEqual("completed_and_verified", first["status"])
            count = len(google.write_calls)
            second = subject.execute_plan(request(), plan, approval(plan), {"google_workspace": google, "microsoft_365": microsoft}, checkpoint)
            self.assertEqual("verified_complete_no_write", second["status"])
            self.assertEqual(0, second["write_count"])
            self.assertEqual(count, len(google.write_calls))
            self.assertEqual([], second["actions"])

    def test_terminal_verification_requires_every_selected_adapter(self):
        plan = subject.build_plan(request(), inventory_report())
        checkpoint_value = subject.initial_checkpoint(plan)
        checkpoint_value["actions"] = {
            item["action_id"]: {"status": "verified"}
            for item in plan["actions"]
        }
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = os.path.join(tmp, "checkpoint.json")
            subject.atomic_write_json(checkpoint, checkpoint_value)
            report = subject.execute_plan(
                request(),
                plan,
                approval(plan),
                {"google_workspace": FakeAdapter("google_workspace", google_inventory())},
                checkpoint,
            )
        self.assertEqual("refused", report["status"])
        self.assertIn("missing adapter for microsoft_365", report["approval_errors"])

    def test_verify_only_requires_every_selected_adapter(self):
        report = subject.verify_only(
            request(),
            {"google_workspace": FakeAdapter("google_workspace", google_inventory())},
        )
        self.assertEqual("verification_failed", report["status"])
        self.assertIn("missing adapter for microsoft_365", report["adapter_errors"])

    def test_checkpoint_action_map_tracks_license_removal_before_delete(self):
        value = request()
        value["policy"]["license"] = "remove_then_delete"
        plan = subject.build_plan(value, inventory_report())
        google = FakeAdapter("google_workspace", google_inventory())
        microsoft = FakeAdapter("microsoft_365", microsoft_absent_inventory())
        with tempfile.TemporaryDirectory() as tmp:
            report = subject.execute_plan(
                value,
                plan,
                approval(plan),
                {"google_workspace": google, "microsoft_365": microsoft},
                os.path.join(tmp, "checkpoint.json"),
            )
        self.assertEqual("completed_and_verified", report["status"])
        self.assertIn("google:remove_license", google.write_calls)
        self.assertEqual("google:delete", google.write_calls[-1])

    def test_absent_declared_platform_with_exact_match_is_not_a_no_op(self):
        microsoft = microsoft_absent_inventory(identity={
            "exact_matches": [{"email": "departing.user@example.test", "immutable_id": "m-1"}],
            "non_user_matches": [],
        })
        plan = subject.build_plan(request(), inventory_report(microsoft=microsoft))
        self.assertEqual("blocked", plan["status"])
        self.assertIn("microsoft_365 was declared absent but an exact recipient exists", plan["guard_errors"])

    def test_add_is_safe_plan_only_and_secret_is_external(self):
        value = request(operation="add")
        value["provisioning"] = {"display_name": "Synthetic User", "initial_secret_env": "NEW_USER_PASSWORD"}
        plan = subject.build_plan(value, inventory_report())
        self.assertEqual("blocked", plan["status"])
        self.assertTrue(any("add is plan-only" in error for error in plan["guard_errors"]))
        self.assertNotIn("password", json.dumps(plan).lower())


if __name__ == "__main__":
    unittest.main()
