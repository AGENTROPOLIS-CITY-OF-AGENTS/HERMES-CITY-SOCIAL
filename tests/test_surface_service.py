"""B4 Social Surface — service layer tests.

Covers the governed ingest gate, quarantine exclusion, credential exclusion,
draft-not-publish invariant, approval states, receipt integrity, analytics,
and the LIVE=BLOCKED health posture.
"""

import json
import unittest

from membrane.dedup import content_hash

from surface.repositories.sqlite import SQLiteSurfaceRepository
from surface.services.surface import SurfaceService

NOW = "2026-08-08T00:00:00Z"


def released_event(**overrides):
    """A fully governed released Social Event (as emitted by B3)."""
    event = {
        "schema_version": "1.0.0",
        "event_id": "x:tweet-2001",
        "platform": "x",
        "connector_id": "conn_x_observe_001",
        "connector_mode": "native_api",
        "account_id": "acct_hermes_public",
        "event_type": "tweet",
        "author": {"id": "user_123", "display_name": "alice"},
        "content": {"text": "governed content"},
        "media": [],
        "conversation_id": None,
        "engagement": {},
        "permissions": {"observe": True, "analyze": False, "draft": False, "execute": False},
        "provenance": {"connector_type": "native_api", "source_reference": "mock://x/tweet-2001", "retrieved_at": NOW},
        "risk_score": 5.0,
        "risk_level": "low",
        "received_at": NOW,
        "source_timestamp": NOW,
        "validation_state": "valid",
        "quarantine_state": "released",
        "policy_state": "allowed",
        "council_state": "analyze",
        "memory_eligibility": "eligible",
        "retention_class": "standard",
        "content_hash": content_hash({"text": "governed content"}),
        "correlation_id": "corr-1",
    }
    event.update(overrides)
    return event


class DummyMembraneResult:
    def __init__(self, outcome, event=None):
        self.outcome = outcome
        self.event = event


class SurfaceServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteSurfaceRepository(":memory:")
        self.service = SurfaceService(self.repo)

    def tearDown(self):
        self.repo.close()

    def test_ingest_gate_rejects_ungoverned_states(self):
        for bad in (
            {"validation_state": "invalid"},
            {"quarantine_state": "quarantined"},
            {"policy_state": "blocked"},
            {"council_state": "escalate"},
            {"council_state": "quarantine"},
        ):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.service.ingest_released_event(released_event(**bad))

    def test_ingest_released_stores_event_decision_notification(self):
        event_id = self.service.ingest_released_event(released_event())
        self.assertEqual(event_id, "x:tweet-2001")
        self.assertEqual(self.repo.list_events().total, 1)
        self.assertEqual(self.repo.list_decisions().total, 1)
        self.assertEqual(self.repo.list_notifications().total, 1)
        counters = self.repo.counters_snapshot()
        self.assertEqual(counters["events_ingested"], 1)
        self.assertEqual(counters["events_released"], 1)

    def test_ingest_from_membrane_quarantined_never_stored(self):
        result = DummyMembraneResult("quarantined", None)
        outcome = self.service.ingest_from_membrane(result)
        self.assertEqual(outcome, {"outcome": "quarantined", "event_id": None, "stored": False})
        self.assertEqual(self.repo.list_events().total, 0)
        self.assertEqual(self.repo.get_counter("events_quarantined"), 1)

    def test_ingest_from_membrane_duplicate_and_rejected_counters(self):
        self.service.ingest_from_membrane(DummyMembraneResult("duplicate", None))
        self.service.ingest_from_membrane(DummyMembraneResult("rejected", None))
        self.assertEqual(self.repo.get_counter("duplicates_rejected"), 1)
        self.assertEqual(self.repo.get_counter("rejected"), 1)
        self.assertEqual(self.repo.list_events().total, 0)

    def test_ingest_from_membrane_released_stores(self):
        result = DummyMembraneResult("released", released_event())
        outcome = self.service.ingest_from_membrane(result)
        self.assertTrue(outcome["stored"])
        self.assertEqual(self.repo.list_events().total, 1)

    def test_credential_keys_never_reach_views(self):
        # A governed event whose content carries a credential-like key must
        # never expose that key in any view (defense in depth at surface).
        event = released_event(content={"text": "hello", "token": "sk-live-123"})
        self.service.ingest_released_event(event)
        events = self.service.list_events()
        raw = json.dumps(events)
        self.assertNotIn("token", raw)
        self.assertNotIn("sk-live-123", raw)
        inbox = self.service.list_inbox()
        self.assertNotIn("token", json.dumps(inbox))

    def test_create_draft_never_publishes(self):
        draft = self.service.create_draft(
            platform="x", account_id="acct_hermes_public", operator="op",
            action="draft_post", content={"text": "governed draft"},
        )
        self.assertEqual(draft["approval_state"], "pending")
        self.assertEqual(draft["action"], "draft_post")
        self.assertEqual(self.repo.list_drafts().total, 1)
        self.assertEqual(self.repo.list_approvals(status="pending").total, 1)
        self.assertEqual(self.repo.get_counter("drafts_created"), 1)
        # No publish/execute side effect exists: no publish receipts, no
        # execute endpoints in the service surface.
        self.assertEqual(self.repo.list_receipts().total, 0)
        self.assertFalse(hasattr(self.service, "publish"))
        self.assertFalse(hasattr(self.service, "execute"))

    def test_create_draft_sanitizes_and_hashes(self):
        draft = self.service.create_draft(
            platform="discord", account_id="acct_hermes_public", operator="op",
            action="draft_reply", content={"text": "<script>alert(1)</script> clean",
                                           "token": "should-be-stripped"},
        )
        self.assertNotIn("<script>", draft["content"]["text"])
        self.assertNotIn("token", json.dumps(draft))
        self.assertEqual(len(draft["content_hash"]), 64)

    def test_create_draft_invalid_platform_or_action(self):
        with self.assertRaises(ValueError):
            self.service.create_draft("tiktok", "a", "op", "draft_post", {"text": "x"})
        with self.assertRaises(ValueError):
            self.service.create_draft("x", "a", "op", "publish", {"text": "x"})
        with self.assertRaises(ValueError):
            self.service.create_draft("x", "a", "op", "draft_post", {})

    def test_draft_and_approval_views_are_contract_based(self):
        self.service.create_draft(
            platform="x", account_id="acct_hermes_public", operator="op",
            action="draft_post", content={"text": "draft body"},
        )
        approval = self.service.list_approvals()["data"][0]
        self.assertEqual(approval["requested_action"], "approve_draft")
        self.assertEqual(approval["status"], "pending")
        self.assertEqual(approval["required_approvers"], ["human_operator"])
        self.assertEqual(approval["approval_policy"], "draft_gate")
        self.assertEqual(len(approval["content_hash"]), 64)

    def test_receipt_integrity_roundtrip(self):
        receipt = {
            "schema_version": "1.0.0",
            "receipt_id": "rcpt-canary-1",
            "action_type": "draft",
            "platform": "x",
            "account_id": "acct_hermes_public",
            "actor": "op",
            "capability_handle": "handle:x-bearer",
            "approval_ids": ["appr-1"],
            "policy_decision_id": "dec-1",
            "input_hash": "e" * 64,
            "output_hash": "f" * 64,
            "provider_reference": None,
            "started_at": NOW,
            "completed_at": NOW,
            "status": "mocked",
            "provenance": {"connector_id": "conn_x_observe_001",
                           "connector_mode": "native_api", "received_at": NOW},
            "software_versions": {},
            "connector_version": "1.0.0",
            "correlation_id": "corr-1",
        }
        view = self.service.store_receipt(receipt)
        self.assertEqual(view["receipt_id"], "rcpt-canary-1")
        self.assertEqual(view["payload"]["status"], "mocked")
        self.assertEqual(view["payload"]["input_hash"], "e" * 64)
        self.assertEqual(self.repo.get_counter("receipts_stored"), 1)
        got = self.service.get_receipt("rcpt-canary-1")
        self.assertEqual(got["payload"]["receipt_id"], "rcpt-canary-1")
        self.assertIsNone(self.service.get_receipt("missing"))

    def test_analytics_no_data_then_data(self):
        before = self.service.analytics()
        self.assertEqual(before["state"], "NO_DATA")
        self.assertEqual(before["metrics"]["events_ingested"], 0)
        self.assertEqual(before["metrics"]["approval_backlog"], 0)

        self.service.ingest_released_event(released_event())
        self.service.create_draft(
            platform="x", account_id="acct_hermes_public", operator="op",
            action="draft_post", content={"text": "draft"},
        )
        after = self.service.analytics()
        self.assertEqual(after["state"], "AVAILABLE")
        self.assertEqual(after["metrics"]["events_ingested"], 1)
        self.assertEqual(after["metrics"]["risk_distribution"]["low"], 1)
        self.assertEqual(after["metrics"]["approval_backlog"], 1)
        self.assertEqual(after["metrics"]["draft_count"], 1)

    def test_health_reports_live_blocked_and_no_publish(self):
        health = self.service.health()
        self.assertEqual(health["live_status"], "LIVE=BLOCKED")
        self.assertEqual(health["production_approved"], "PRODUCTION-APPROVED=NO")
        self.assertEqual(health["db"], "ok")
        self.assertEqual(health["publish_endpoints"], [])
        self.assertFalse(health["execute_available"])
        self.assertEqual(set(health["platforms"]), {"x", "discord", "farcaster"})

    def test_list_read_models_shapes(self):
        self.service.ingest_released_event(released_event())
        inbox = self.service.list_inbox()
        self.assertEqual(inbox["meta"]["total"], 1)
        self.assertEqual(inbox["data"][0]["event_id"], "x:tweet-2001")
        feed = self.service.list_feed()
        self.assertEqual(feed["meta"]["total"], 1)
        events = self.service.list_events(platform="x", risk_level="low")
        self.assertEqual(events["meta"]["total"], 1)
        self.assertEqual(self.service.list_events(platform="discord")["meta"]["total"], 0)
        notif = self.service.list_notifications()
        self.assertEqual(notif["meta"]["total"], 1)
        self.assertTrue(self.service.mark_notification_read(notif["data"][0]["notification_id"]))
        self.assertEqual(self.service.list_notifications(read=True)["meta"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
