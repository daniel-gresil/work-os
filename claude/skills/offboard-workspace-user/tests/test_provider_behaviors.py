import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import provider_adapters as subject


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = {}

    def json(self):
        return self._body


class ProviderBehaviorTests(unittest.TestCase):
    def adapter(self, assignments, errors=None):
        adapter = object.__new__(subject.GoogleWorkspaceAdapter)
        adapter.credential_path = "external-only"
        adapter.admin_subject = "admin@example.test"
        adapter._sessions = {}
        adapter._license_assignments = mock.Mock(return_value=(assignments, errors or []))
        return adapter

    def request(self):
        return {
            "target": {"email": "departing.user@example.test"},
            "platforms": {
                "google_workspace": {
                    "disposition": "present",
                    "immutable_id": "g-123",
                    "customer_id": "C-example",
                    "license_product_ids": list(subject.GOOGLE_LICENSE_PRODUCT_CATALOG),
                    "license_product_catalog_complete": True,
                }
            },
        }

    def test_complete_product_listing_proves_auto_assigned_license_absence(self):
        adapter = self.adapter([])
        absent, evidence = adapter._licenses_absent(self.request())
        self.assertTrue(absent)
        self.assertTrue(evidence["listing_complete"])
        self.assertEqual([], evidence["matches"])

    def test_invalid_user_direct_get_would_not_override_listing_match(self):
        assignment = {
            "product_id": "Google-Apps",
            "sku_id": "sku-example",
            "user_id": "departing.user@example.test",
        }
        adapter = self.adapter([assignment])
        absent, evidence = adapter._licenses_absent(self.request())
        self.assertFalse(absent)
        self.assertEqual([assignment], evidence["matches"])

    def test_incomplete_product_listing_never_proves_absence(self):
        adapter = self.adapter([], ["Google-Apps: HTTP 403"])
        absent, evidence = adapter._licenses_absent(self.request())
        self.assertFalse(absent)
        self.assertFalse(evidence["listing_complete"])

    def test_microsoft_address_resolution_is_exact_and_case_insensitive(self):
        user = {
            "userPrincipalName": "other@example.test",
            "mail": None,
            "proxyAddresses": ["SMTP:Other@Example.Test", "smtp:departing.user@example.test"],
            "otherMails": [],
            "identities": [],
        }
        addresses = subject.Microsoft365Adapter._addresses(user)
        self.assertIn("departing.user@example.test", addresses)
        self.assertNotIn("departing.user", addresses)
        self.assertNotIn("departing.user@example.test", subject.Microsoft365Adapter._canonical_user_addresses(user))
        self.assertIn("departing.user@example.test", subject.Microsoft365Adapter._proxy_only_addresses(user))

    def test_microsoft_license_removal_refuses_unapproved_new_sku(self):
        adapter = object.__new__(subject.Microsoft365Adapter)
        adapter._get = mock.Mock(return_value=FakeResponse(200, {
            "id": "m-123",
            "userPrincipalName": "departing.user@example.test",
            "mail": "departing.user@example.test",
            "proxyAddresses": [],
            "otherMails": [],
            "identities": [],
            "accountEnabled": False,
            "assignedLicenses": [{"skuId": "approved-sku"}, {"skuId": "new-unapproved-sku"}],
        }))
        adapter.session = mock.Mock()
        action = {
            "verb": "remove_licenses",
            "expected_license_sku_ids": ["approved-sku"],
        }
        request = {
            "target": {"email": "departing.user@example.test"},
            "platforms": {
                "microsoft_365": {
                    "immutable_id": "m-123",
                    "tenant_id": "tenant-example",
                }
            }
        }
        with self.assertRaisesRegex(subject.LifecycleError, "license set drifted"):
            adapter.apply_action(action, request)
        adapter.session.post.assert_not_called()

    def test_microsoft_absent_verification_is_bound_to_tenant(self):
        adapter = object.__new__(subject.Microsoft365Adapter)
        adapter.inventory = mock.Mock(return_value={
            "complete": True,
            "tenant_id": "wrong-tenant",
            "identity": {"exact_matches": [], "non_user_matches": []},
        })
        request = {
            "target": {"email": "departing.user@example.test"},
            "platforms": {
                "microsoft_365": {
                    "disposition": "absent",
                    "tenant_id": "approved-tenant",
                }
            },
        }
        result = adapter.verify_terminal(request)
        self.assertFalse(result["verified"])

    def test_google_dependent_write_requires_suspension(self):
        adapter = object.__new__(subject.GoogleWorkspaceAdapter)
        adapter._assert_current_identity = mock.Mock(return_value={"suspended": False})
        action = {"verb": "delete_user"}
        with self.assertRaisesRegex(subject.LifecycleError, "not suspended"):
            adapter.apply_action(action, self.request())

    def test_microsoft_dependent_write_requires_blocked_sign_in(self):
        adapter = object.__new__(subject.Microsoft365Adapter)
        adapter._get = mock.Mock(return_value=FakeResponse(200, {
            "id": "m-123",
            "userPrincipalName": "departing.user@example.test",
            "mail": "departing.user@example.test",
            "proxyAddresses": [],
            "otherMails": [],
            "identities": [],
            "accountEnabled": True,
            "assignedLicenses": [],
        }))
        adapter.session = mock.Mock()
        request = {
            "target": {"email": "departing.user@example.test"},
            "platforms": {"microsoft_365": {"immutable_id": "m-123"}},
        }
        with self.assertRaisesRegex(subject.LifecycleError, "not blocked"):
            adapter.apply_action({"verb": "delete_user"}, request)
        adapter.session.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
