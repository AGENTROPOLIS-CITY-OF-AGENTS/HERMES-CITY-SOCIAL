"""B4 Social Surface — canary tests (B3 pipeline -> B4 surface).

Uses REAL B3 pipeline + REAL pilot fixture connectors. Proves:
  - X / Discord / Farcaster events flow through the pipeline into B4
  - quarantined events never appear in the operator feed
  - credential-like values never appear in surface responses
  - a draft can be created without triggering publication
  - released events remain schema-valid against social-event v1.0.0
"""

import json
import unittest

from jsonschema import Draft202012Validator

from surface.ingest import run_canary

SOCIAL_EVENT_SCHEMA_PATH = "schemas/social-event.schema.json"


class SurfaceCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_canary()
        cls.service = cls.report["service"]
        cls.repo = cls.report["repo"]

    @classmethod
    def tearDownClass(cls):
        cls.repo.close()

    def test_platforms_flow_through_pipeline_into_surface(self):
        for platform in ("x", "discord", "farcaster"):
            info = self.report["platforms"][platform]
            self.assertGreater(info["fixtures"], 0, platform)
            self.assertGreater(info["released"], 0, platform)
            stored = [r for r in info["events"] if r["stored"]]
            self.assertTrue(stored, platform)
        # The released fixtures are visible in the unified inbox.
        inbox = self.service.list_inbox(limit=200, offset=0)
        event_ids = {item["event_id"] for item in inbox["data"]}
        self.assertIn("x:tweet-2001", event_ids)
        self.assertIn("discord:msg-501", event_ids)
        self.assertIn("farcaster:cast-301", event_ids)

    def test_quarantined_event_never_visible(self):
        outcome = self.report["adversarial"]["quarantined_outcome"]
        self.assertFalse(outcome["stored"])
        self.assertEqual(self.repo.get_counter("events_quarantined"), 1)
        events = self.service.list_events(limit=200, offset=0)
        raw = json.dumps(events)
        self.assertNotIn("tweet-evil-9000", raw)

    def test_credential_like_values_never_in_surface_response(self):
        outcome = self.report["adversarial"]["credential_event_outcome"]
        # The membrane handled the event (released with elevated risk).
        self.assertTrue(outcome["stored"])
        raw = json.dumps(self.service.list_events(limit=200, offset=0))
        self.assertNotIn("token", raw)
        self.assertNotIn("secret", raw)
        self.assertNotIn("api_key", raw)
        # The credential/injection event carries elevated risk (link + signal).
        event = self.service.get_event("x:tweet-cred-9001")
        self.assertIsNotNone(event)
        self.assertIn(event["risk"]["level"], ("moderate", "high"))

    def test_draft_created_without_publication(self):
        draft = self.report["draft"]
        self.assertEqual(draft["approval_state"], "pending")
        self.assertEqual(self.repo.get_counter("drafts_created"), 1)
        self.assertEqual(self.repo.list_receipts().total, 0)
        # No publish/send/execute routes anywhere in the app surface.
        self.assertFalse(hasattr(self.service, "publish"))
        self.assertFalse(hasattr(self.service, "execute"))
        approvals = self.service.list_approvals(status="pending")
        self.assertGreaterEqual(approvals["meta"]["total"], 1)
        for approval in approvals["data"]:
            self.assertEqual(approval["requested_action"], "approve_draft")
            self.assertNotIn("required_secret_handles", json.dumps(approval))

    def test_connectors_blocked_live(self):
        connectors = self.service.list_connectors()["data"]
        self.assertEqual(len(connectors), 3)
        for connector in connectors:
            self.assertEqual(connector["status"], "blocked_live")
            self.assertEqual(connector["manifest"]["status"], "blocked_live")
        health = self.service.health()
        self.assertEqual(health["live_status"], "LIVE=BLOCKED")
        self.assertEqual(health["production_approved"], "PRODUCTION-APPROVED=NO")
        self.assertFalse(health["execute_available"])

    def test_released_events_remain_schema_valid(self):
        with open(SOCIAL_EVENT_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        validator = Draft202012Validator(schema)
        for record in self.repo.list_events(limit=200, offset=0).items:
            payload = json.loads(record.content_json)
            event = {
                "schema_version": "1.0.0",
                "event_id": record.event_id,
                "platform": record.platform,
                "connector_id": record.connector_id,
                "connector_mode": record.connector_mode,
                "account_id": record.account_id,
                "event_type": record.event_type,
                "author": {"id": record.author_id, "display_name": record.author_display_name},
                "content": payload,
                "media": [],
                "conversation_id": record.conversation_id,
                "engagement": json.loads(record.engagement_json),
                "permissions": {"observe": True, "analyze": False, "draft": False, "execute": False},
                "provenance": json.loads(record.provenance_json),
                "risk_score": record.risk_score,
                "risk_level": record.risk_level,
                "received_at": record.received_at,
                "source_timestamp": record.source_timestamp,
                "validation_state": record.validation_state,
                "quarantine_state": record.quarantine_state,
                "policy_state": record.policy_state,
                "council_state": record.council_state,
                "memory_eligibility": record.memory_eligibility,
                "retention_class": record.retention_class,
                "content_hash": record.content_hash,
                "correlation_id": record.correlation_id,
            }
            errors = list(validator.iter_errors(event))
            self.assertEqual(errors, [], record.event_id)

    def test_analytics_reflects_canary_activity(self):
        analytics = self.service.analytics()
        self.assertEqual(analytics["state"], "AVAILABLE")
        metrics = analytics["metrics"]
        self.assertGreaterEqual(metrics["events_ingested"], 3)
        self.assertEqual(metrics["draft_count"], 1)
        self.assertGreaterEqual(metrics["approval_backlog"], 1)
        self.assertEqual(metrics["connector_count"], 3)
        self.assertEqual(metrics["connector_status"].get("blocked_live"), 3)


if __name__ == "__main__":
    unittest.main()
