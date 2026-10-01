#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "monthly_invoice_draft", Path(__file__).with_name("monthly_invoice_draft.py")
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class MonthlyInvoiceDraftTests(unittest.TestCase):
    def test_september_run_bills_august_weekdays(self):
        period = module.previous_month(date(2026, 9, 1))
        self.assertEqual((period.month_name, period.year), ("August", 2026))
        self.assertEqual((period.weekdays, period.hours, period.amount_usd), (21, 63, 2205))
        self.assertEqual(period.subject, "Invoice for August / 2026")

    def test_january_run_bills_previous_december(self):
        period = module.previous_month(date(2027, 1, 1))
        self.assertEqual((period.year, period.month), (2026, 12))
        self.assertEqual(period.amount_usd, period.weekdays * 3 * 35)

    def test_normalizes_gmail_line_endings_for_remittance_check(self):
        self.assertEqual(
            module._normalize_multiline("Line one\nLine two  \n"),
            module._normalize_multiline("Line one\r\nLine two\r\n"),
        )

    def test_body_names_same_period_and_amount(self):
        period = module.previous_month(date(2026, 9, 1))
        body = module.build_body(period, "REMITTANCE-BLOCK")
        self.assertIn("invoice amount for August", body)
        self.assertIn("$2,205", body)
        self.assertIn("REMITTANCE-BLOCK", body)
        self.assertNotIn("July", body)


if __name__ == "__main__":
    unittest.main()
