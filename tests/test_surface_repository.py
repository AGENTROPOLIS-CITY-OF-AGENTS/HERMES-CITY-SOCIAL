"""B4 Social Surface — SQLite repository tests.

Covers the repository abstraction contract, SQLite dev backend, pagination,
filtering, empty states, and record integrity for every read model.
"""

import json
import os
import tempfile
import unittest

from surface.models.records import (
    AccountRecord,
    ApprovalRecord,
    ConnectorStateRecord,
    DecisionRecord,
    DraftRecord,
    EventRecord,
    NotificationRecord,
    ReceiptRecord,
)
from surface.repositories.sqlite import SQLiteSurfaceRepository

NOW = "2026-08-08T00:00:00Z"


def event_record(event_id="x:tweet-1", platform="x", risk_level="low",
                 council_state="analyze", received_at=NOW) -> EventRecord:
    return EventRecord(
        event_id=event_id, platform=platform, connector_id="conn_x_observe_001",
        connector_mode="native_api", account_id="acct_hermes_public",
        event_type="tweet", author_id="user_1", author_display_name="alice",
        content_text="hello surface", content_json=json.dumps({"text": "hello surface"}),
        conversation_id=None, engagement_json="{}", provenance_json=json.dumps(
            {"source_reference": "mock://x/1", "retrieved_at": NOW}),
        risk_score=5.0, risk_level=risk_level, received_at=received_at,
        source_timestamp=NOW, validation_state="valid", quarantine_state="released",
        policy_state="allowed", council_state=council_state,
        memory_eligibility="eligible", retention_class="standard",
        content_hash="a" * 64, correlation_id="corr-1",
    )


class SQLiteRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteSurfaceRepository(":memory:")

    def tearDown(self):
        self.repo.close()

    def test_db_health_and_empty_states(self):
        self.assertTrue(self.repo.db_health())
        self.assertEqual(self.repo.list_events().total, 0)
        self.assertEqual(self.repo.list_drafts().total, 0)
        self.assertEqual(self.repo.list_approvals().total, 0)
        self.assertEqual(self.repo.list_decisions().total, 0)
        self.assertEqual(self.repo.list_receipts().total, 0)
        self.assertEqual(self.repo.list_notifications().total, 0)
        self.assertEqual(self.repo.list_accounts(), [])
        self.assertEqual(self.repo.list_connector_states(), [])
        self.assertEqual(self.repo.counters_snapshot(), {})

    def test_event_roundtrip_and_filters(self):
        self.repo.insert_event(event_record("x:tweet-1", risk_level="low"))
        self.repo.insert_event(event_record("d:msg-1", platform="discord",
                                            risk_level="high", received_at="2026-08-08T00:01:00Z"))
        page = self.repo.list_events(limit=50, offset=0)
        self.assertEqual(page.total, 2)
        # newest first
        self.assertEqual(page.items[0].event_id, "d:msg-1")
        # filters
        self.assertEqual(self.repo.list_events(platform="discord").total, 1)
        self.assertEqual(self.repo.list_events(risk_level="high").total, 1)
        self.assertEqual(self.repo.list_events(council_state="analyze").total, 2)
        self.assertEqual(self.repo.list_events(council_state="draft").total, 0)
        # get
        rec = self.repo.get_event("x:tweet-1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.content_text, "hello surface")
        self.assertIsNone(self.repo.get_event("nope"))

    def test_event_pagination(self):
        for i in range(15):
            self.repo.insert_event(event_record("x:tweet-%d" % i, received_at="2026-08-08T00:%02d:00Z" % i))
        page = self.repo.list_events(limit=5, offset=0)
        self.assertEqual(len(page.items), 5)
        self.assertEqual(page.total, 15)
        self.assertEqual(page.limit, 5)
        self.assertEqual(page.offset, 0)
        page2 = self.repo.list_events(limit=5, offset=5)
        self.assertEqual(len(page2.items), 5)
        self.assertNotEqual([i.event_id for i in page.items], [i.event_id for i in page2.items])

    def test_draft_roundtrip_and_filter(self):
        draft = DraftRecord(
            draft_id="draft-1", platform="x", account_id="acct_hermes_public",
            operator="op", action="draft_post", content_text="draft body",
            content_json=json.dumps({"text": "draft body"}), conversation_ref=None,
            source_event_id=None, provenance_json="{}", risk_score=5.0,
            risk_level="low", approval_state="pending", content_hash="b" * 64,
            created_at=NOW, updated_at=NOW,
        )
        self.repo.insert_draft(draft)
        self.assertEqual(self.repo.list_drafts().total, 1)
        self.assertEqual(self.repo.list_drafts(approval_state="pending").total, 1)
        self.assertEqual(self.repo.list_drafts(approval_state="approved").total, 0)
        got = self.repo.get_draft("draft-1")
        self.assertEqual(got.content_hash, "b" * 64)
        self.assertIsNone(self.repo.get_draft("missing"))

    def test_approval_roundtrip(self):
        approval = ApprovalRecord(
            approval_id="appr-1", payload_json=json.dumps({"requested_action": "approve_draft"}),
            status="pending", created_at=NOW, expires_at="2026-08-15T00:00:00Z",
            correlation_id="corr-1",
        )
        self.repo.insert_approval(approval)
        self.assertEqual(self.repo.list_approvals().total, 1)
        self.assertEqual(self.repo.list_approvals(status="pending").total, 1)
        self.assertEqual(self.repo.list_approvals(status="approved").total, 0)
        self.assertEqual(self.repo.get_approval("appr-1").status, "pending")

    def test_receipt_roundtrip_and_platform_filter(self):
        payload = {"receipt_id": "rcpt-1", "action_type": "draft", "platform": "x",
                   "account_id": "acct_hermes_public", "actor": "op",
                   "capability_handle": "handle:x-1", "approval_ids": [],
                   "policy_decision_id": "dec-1", "input_hash": "c" * 64,
                   "output_hash": "d" * 64, "provider_reference": None,
                   "started_at": NOW, "completed_at": NOW, "status": "mocked",
                   "provenance": {"connector_id": "conn_x_observe_001",
                                  "connector_mode": "native_api", "received_at": NOW},
                   "software_versions": {}, "connector_version": "1.0.0",
                   "correlation_id": "corr-1"}
        self.repo.insert_receipt(ReceiptRecord("rcpt-1", json.dumps(payload), NOW))
        self.assertEqual(self.repo.list_receipts().total, 1)
        self.assertEqual(self.repo.list_receipts(platform="x").total, 1)
        self.assertEqual(self.repo.list_receipts(platform="discord").total, 0)
        got = self.repo.get_receipt("rcpt-1")
        self.assertIn("action_type", json.loads(got.payload_json))

    def test_notifications_and_mark_read(self):
        self.repo.insert_notification(NotificationRecord(
            "notif-1", "x:tweet-1", "x", "acct_hermes_public", "event_released",
            "x tweet", "body", 0, NOW,
        ))
        self.assertEqual(self.repo.list_notifications().total, 1)
        self.assertEqual(self.repo.list_notifications(read=0).total, 1)
        self.assertEqual(self.repo.list_notifications(read=1).total, 0)
        self.assertTrue(self.repo.mark_notification_read("notif-1"))
        self.assertFalse(self.repo.mark_notification_read("missing"))
        self.assertEqual(self.repo.list_notifications(read=1).total, 1)

    def test_accounts_and_connector_state(self):
        self.repo.upsert_account(AccountRecord(
            "acct_hermes_public", "x", "HERMES X public", "conn_x_observe_001",
            json.dumps({"observe": True, "execute": False}), "active", NOW,
        ))
        self.repo.upsert_account(AccountRecord(
            "acct_hermes_public", "discord", "HERMES DISCORD public", "conn_discord_observe_001",
            json.dumps({"observe": True, "execute": False}), "active", NOW,
        ))
        self.assertEqual(len(self.repo.list_accounts()), 2)
        self.assertEqual(len(self.repo.list_accounts(platform="x")), 1)
        # upsert replaces
        self.repo.upsert_account(AccountRecord(
            "acct_hermes_public", "x", "HERMES X public v2", "conn_x_observe_001",
            json.dumps({"observe": True, "execute": False}), "active", NOW,
        ))
        self.assertEqual(len(self.repo.list_accounts(platform="x")), 1)

        self.repo.upsert_connector_state(ConnectorStateRecord(
            "conn_x_observe_001", "x", "blocked_live", "{}", "{}", NOW,
        ))
        states = self.repo.list_connector_states()
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].status, "blocked_live")

    def test_counters_increment_and_snapshot(self):
        self.assertEqual(self.repo.get_counter("nope"), 0)
        self.repo.increment_counter("events_ingested")
        self.repo.increment_counter("events_ingested")
        self.repo.increment_counter("events_quarantined")
        snap = self.repo.counters_snapshot()
        self.assertEqual(snap["events_ingested"], 2)
        self.assertEqual(snap["events_quarantined"], 1)

    def test_file_backed_database_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "surface.db")
            repo = SQLiteSurfaceRepository(path)
            repo.insert_event(event_record("x:tweet-file"))
            repo.close()
            repo2 = SQLiteSurfaceRepository(path)
            self.assertEqual(repo2.list_events().total, 1)
            repo2.close()


if __name__ == "__main__":
    unittest.main()
