"""Deterministic policy tests for HERMES-SOCIAL (B2).

Run via:
  uv run --with pyyaml python -m unittest discover -s tests -v
"""
import os
import unittest

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
POLICIES = os.path.join(os.path.dirname(HERE), "policies")


def load(name):
    with open(os.path.join(POLICIES, name), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class PermissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = load("permissions.yaml")

    def test_permission_chain(self):
        self.assertIn("observe", self.p["permission_levels"]["analyze"]["requires"])
        self.assertIn("analyze", self.p["permission_levels"]["draft"]["requires"])
        reqs = self.p["permission_levels"]["execute"]["requires"]
        for r in ("observe", "analyze", "draft", "approval_gate"):
            self.assertIn(r, reqs)

    def test_external_side_effects_only_execute(self):
        for level in ("observe", "analyze", "draft"):
            self.assertFalse(self.p["permission_levels"][level]["external_side_effects"])
        self.assertTrue(self.p["permission_levels"]["execute"]["external_side_effects"])

    def test_defaults_deny(self):
        self.assertEqual(self.p["defaults"]["new_connector"], "observe_only")
        self.assertEqual(self.p["defaults"]["raw_credentials_in_model_context"], "deny")


class ApprovalGateTests(unittest.TestCase):
    def setUp(self):
        self.p = load("approval-gates.yaml")

    def test_default_deny_execute(self):
        self.assertEqual(self.p["default"], "deny_execute")

    def test_draft_requires_approver(self):
        self.assertEqual(self.p["gates"]["draft"]["approvers"], ["assigned_operator"])

    def test_high_risk_dual_control(self):
        self.assertEqual(
            self.p["gates"]["execute_high_risk"]["approvers"],
            ["human_operator", "second_controller"],
        )

    def test_every_gate_requires_receipt(self):
        for gate in self.p["gates"].values():
            self.assertEqual(gate["receipt"], "required")


class RiskLevelTests(unittest.TestCase):
    def setUp(self):
        self.p = load("risk-levels.yaml")

    def test_bands_contiguous(self):
        order = [("low", 0, 24), ("moderate", 25, 49), ("high", 50, 74), ("critical", 75, 100)]
        for name, lo, hi in order:
            self.assertEqual(self.p["levels"][name]["range"], [lo, hi])

    def test_critical_signals(self):
        self.assertEqual(self.p["signals"]["credential_exposure"], "critical")
        self.assertEqual(self.p["signals"]["private_data_leak"], "critical")


class CouncilPolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = load("council.yaml")

    def test_outcomes_match_mandate(self):
        self.assertEqual(
            set(self.p["outcomes"].keys()),
            {"ignore", "analyze", "draft", "escalate", "approve", "execute", "reject", "quarantine"},
        )

    def test_pilot_execute_disabled(self):
        self.assertFalse(self.p["pilot"]["execute_enabled"])
        self.assertFalse(self.p["pilot"]["publishing_enabled"])
        self.assertTrue(self.p["pilot"]["draft_requires_human_approval"])

    def test_never_auto_execute(self):
        cats = set(self.p["never_auto_execute"])
        for c in ("moderation", "deletion", "financial_promotion", "political_persuasion",
                  "legal_claims", "account_changes", "private_messaging", "credential_changes"):
            self.assertIn(c, cats)


if __name__ == "__main__":
    unittest.main()
