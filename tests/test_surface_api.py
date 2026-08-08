"""B4 Social Surface — API contract tests (FastAPI TestClient).

Covers API schemas, pagination, filtering, empty states, quarantine and
credential exclusion in responses, approval states, receipt integrity,
draft-not-publish invariant, and platform/account permission boundaries.
"""

import json
import unittest

from fastapi.testclient import TestClient

from surface.api.app import create_app
from surface.repositories.sqlite import SQLiteSurfaceRepository

try:
    from test_surface_service import released_event
except ModuleNotFoundError:  # invoked as a package module (python -m unittest tests.test_surface_api)
    from tests.test_surface_service import released_event


class SurfaceApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteSurfaceRepository(":memory:")
        self.app = create_app(repo=self.repo)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.repo.close()

    def _ingest(self, **overrides):
        event = released_event(**overrides)
        self.repo.increment_counter("events_ingested")
        self.repo.increment_counter("events_released")
        from surface.models.records import EventRecord, DecisionRecord, NotificationRecord
        record = EventRecord(
            event_id=event["event_id"], platform=event["platform"],
            connector_id=event["connector_id"], connector_mode=event["connector_mode"],
            account_id=event["account_id"], event_type=event["event_type"],
            author_id=event["author"]["id"], author_display_name=event["author"]["display_name"],
            content_text=event["content"].get("text", ""),
            content_json=json.dumps(event["content"], sort_keys=True),
            conversation_id=event.get("conversation_id"),
            engagement_json=json.dumps(event.get("engagement", {}), sort_keys=True),
            provenance_json=json.dumps(event.get("provenance", {}), sort_keys=True),
            risk_score=event["risk_score"], risk_level=event["risk_level"],
            received_at=event["received_at"], source_timestamp=event["source_timestamp"],
            validation_state=event["validation_state"],
            quarantine_state=event["quarantine_state"],
            policy_state=event["policy_state"], council_state=event["council_state"],
            memory_eligibility=event.get("memory_eligibility", "eligible"),
            retention_class=event.get("retention_class", "standard"),
            content_hash=event["content_hash"], correlation_id=event["correlation_id"],
        )
        self.repo.insert_event(record)
        self.repo.insert_decision(DecisionRecord(
            "dec-1", event["event_id"], event["council_state"], event["policy_state"],
            event["risk_level"], "released", event["received_at"], "corr-1",
        ))
        self.repo.insert_notification(NotificationRecord(
            "notif-1", event["event_id"], event["platform"], event["account_id"],
            "event_released", "x tweet", event["content"].get("text", "")[:200], 0,
            event["received_at"],
        ))
        return event["event_id"]

    # -- health -----------------------------------------------------------

    def test_health_endpoint(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["service"], "hermes-social-surface")
        self.assertEqual(body["live_status"], "LIVE=BLOCKED")
        self.assertEqual(body["production_approved"], "PRODUCTION-APPROVED=NO")
        self.assertEqual(body["db"], "ok")
        self.assertEqual(body["publish_endpoints"], [])
        self.assertFalse(body["execute_available"])

    # -- empty states -----------------------------------------------------

    def test_empty_states_all_endpoints(self):
        for path in ("/api/v1/events", "/api/v1/inbox", "/api/v1/feeds",
                     "/api/v1/notifications", "/api/v1/drafts", "/api/v1/approvals",
                     "/api/v1/council", "/api/v1/receipts"):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, path)
            body = resp.json()
            self.assertEqual(body["data"], [], path)
            self.assertEqual(body["meta"]["total"], 0, path)
        analytics = self.client.get("/api/v1/analytics").json()
        self.assertEqual(analytics["state"], "NO_DATA")
        self.assertEqual(self.client.get("/api/v1/accounts").json()["data"], [])
        self.assertEqual(self.client.get("/api/v1/connectors").json()["data"], [])

    # -- events / pagination / filtering ----------------------------------

    def test_events_pagination_and_filtering(self):
        for i in range(7):
            self._ingest(event_id="x:tweet-%d" % i,
                         received_at="2026-08-08T00:%02d:00Z" % i)
        page1 = self.client.get("/api/v1/events", params={"limit": 3, "offset": 0}).json()
        self.assertEqual(len(page1["data"]), 3)
        self.assertEqual(page1["meta"]["total"], 7)
        page2 = self.client.get("/api/v1/events", params={"limit": 3, "offset": 3}).json()
        self.assertEqual(len(page2["data"]), 3)
        ids1 = {e["event_id"] for e in page1["data"]}
        ids2 = {e["event_id"] for e in page2["data"]}
        self.assertFalse(ids1 & ids2)
        filtered = self.client.get("/api/v1/events", params={"platform": "x"}).json()
        self.assertEqual(filtered["meta"]["total"], 7)
        self.assertEqual(self.client.get("/api/v1/events", params={"platform": "discord"}).json()["meta"]["total"], 0)
        self.assertEqual(self.client.get("/api/v1/events", params={"risk_level": "low"}).json()["meta"]["total"], 7)
        self.assertEqual(self.client.get("/api/v1/events", params={"council_state": "draft"}).json()["meta"]["total"], 0)
        # invalid platform -> 422 (schema boundary)
        self.assertEqual(self.client.get("/api/v1/events", params={"platform": "tiktok"}).status_code, 422)

    def test_event_detail_and_404(self):
        self._ingest()
        resp = self.client.get("/api/v1/events/x:tweet-2001")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["event_id"], "x:tweet-2001")
        self.assertEqual(self.client.get("/api/v1/events/missing").status_code, 404)

    # -- quarantine exclusion ---------------------------------------------

    def test_quarantined_event_never_appears_in_operator_feed(self):
        # A quarantined-state event must not be present in the surface at all.
        bad = released_event(event_id="x:tweet-evil",
                             quarantine_state="quarantined",
                             validation_state="held_for_migration")
        self.repo.increment_counter("events_quarantined")
        # Surface ingest gate rejects it at the service boundary.
        from surface.services.surface import SurfaceService
        with self.assertRaises(ValueError):
            SurfaceService(self.repo).ingest_released_event(bad)
        inbox = self.client.get("/api/v1/inbox").json()
        events = self.client.get("/api/v1/events").json()
        self.assertEqual(inbox["meta"]["total"], 0)
        self.assertEqual(events["meta"]["total"], 0)
        analytics = self.client.get("/api/v1/analytics").json()
        self.assertEqual(analytics["metrics"]["events_quarantined"], 1)

    # -- credential exclusion ---------------------------------------------

    def test_credential_like_values_never_in_response(self):
        self._ingest(content={"text": "hello", "token": "sk-live-123",
                              "authorization": "Bearer secret"})
        for path in ("/api/v1/events", "/api/v1/inbox", "/api/v1/feeds",
                     "/api/v1/notifications"):
            raw = json.dumps(self.client.get(path).json())
            self.assertNotIn("sk-live-123", raw, path)
            self.assertNotIn("Bearer secret", raw, path)
            self.assertNotIn("authorization", raw, path)

    # -- drafts -----------------------------------------------------------

    def test_draft_create_endpoint_and_no_publish_path(self):
        resp = self.client.post("/api/v1/drafts", json={
            "platform": "x",
            "account_id": "acct_hermes_public",
            "operator": "op-1",
            "action": "draft_post",
            "content": {"text": "governed draft body"},
            "conversation_ref": "conv-991",
        })
        self.assertEqual(resp.status_code, 201)
        draft = resp.json()
        self.assertEqual(draft["approval_state"], "pending")
        self.assertEqual(draft["platform"], "x")
        self.assertEqual(draft["conversation_ref"], "conv-991")
        self.assertEqual(len(draft["content_hash"]), 64)
        # Draft appears in the queue.
        drafts = self.client.get("/api/v1/drafts").json()
        self.assertEqual(drafts["meta"]["total"], 1)
        self.assertEqual(self.client.get("/api/v1/drafts/%s" % draft["draft_id"]).status_code, 200)
        # Approval request was created with real contract state.
        approvals = self.client.get("/api/v1/approvals").json()
        self.assertEqual(approvals["meta"]["total"], 1)
        self.assertEqual(approvals["data"][0]["requested_action"], "approve_draft")
        self.assertEqual(approvals["data"][0]["status"], "pending")
        self.assertEqual(approvals["data"][0]["draft_id"], draft["draft_id"])
        # NO publish/send/execute/moderate endpoint exists.
        app_paths = {route.path for route in self.app.routes}
        for forbidden in ("/api/v1/publish", "/api/v1/send", "/api/v1/execute",
                          "/api/v1/moderate", "/api/v1/approvals/approve"):
            self.assertNotIn(forbidden, app_paths, forbidden)
            self.assertIn(self.client.post(forbidden).status_code, (404, 405), forbidden)

    def test_draft_invalid_platform_422_and_empty_content_422(self):
        resp = self.client.post("/api/v1/drafts", json={
            "platform": "tiktok", "account_id": "a", "operator": "op",
            "action": "draft_post", "content": {"text": "x"},
        })
        self.assertEqual(resp.status_code, 422)
        resp2 = self.client.post("/api/v1/drafts", json={
            "platform": "x", "account_id": "a", "operator": "op",
            "action": "draft_post", "content": {"text": ""},
        })
        self.assertEqual(resp2.status_code, 422)

    def test_draft_sanitized_in_response(self):
        resp = self.client.post("/api/v1/drafts", json={
            "platform": "discord", "account_id": "acct_hermes_public",
            "operator": "op", "action": "draft_reply",
            "content": {"text": "<b>hi</b>", "token": "nope"},
        })
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertNotIn("<b>", body["content"]["text"])
        self.assertNotIn("token", json.dumps(body))

    # -- approvals / receipts / council -----------------------------------

    def test_approval_queue_filters_and_detail(self):
        self.client.post("/api/v1/drafts", json={
            "platform": "x", "account_id": "a", "operator": "op",
            "action": "draft_post", "content": {"text": "draft"},
        })
        pending = self.client.get("/api/v1/approvals", params={"status": "pending"}).json()
        self.assertEqual(pending["meta"]["total"], 1)
        approved = self.client.get("/api/v1/approvals", params={"status": "approved"}).json()
        self.assertEqual(approved["meta"]["total"], 0)
        approval_id = pending["data"][0]["approval_id"]
        detail = self.client.get("/api/v1/approvals/%s" % approval_id)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/approvals/missing").status_code, 404)

    def test_receipt_endpoints_and_integrity(self):
        from surface.services.surface import SurfaceService
        service = SurfaceService(self.repo)
        receipt = {
            "schema_version": "1.0.0", "receipt_id": "rcpt-api-1",
            "action_type": "draft", "platform": "x", "account_id": "acct_hermes_public",
            "actor": "op", "capability_handle": "handle:x-1", "approval_ids": [],
            "policy_decision_id": "dec-1", "input_hash": "e" * 64,
            "output_hash": "f" * 64, "provider_reference": None,
            "started_at": "2026-08-08T00:00:00Z", "completed_at": "2026-08-08T00:00:00Z",
            "status": "mocked",
            "provenance": {"connector_id": "conn_x_observe_001",
                           "connector_mode": "native_api", "received_at": "2026-08-08T00:00:00Z"},
            "software_versions": {}, "connector_version": "1.0.0",
            "correlation_id": "corr-1",
        }
        service.store_receipt(receipt)
        resp = self.client.get("/api/v1/receipts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["meta"]["total"], 1)
        payload = resp.json()["data"][0]["payload"]
        self.assertEqual(payload["input_hash"], "e" * 64)
        self.assertEqual(payload["status"], "mocked")
        self.assertEqual(self.client.get("/api/v1/receipts/rcpt-api-1").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/receipts/missing").status_code, 404)

    def test_council_decisions_endpoint(self):
        self._ingest()
        resp = self.client.get("/api/v1/council")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["meta"]["total"], 1)
        decision = resp.json()["data"][0]
        self.assertEqual(decision["council_state"], "analyze")
        self.assertEqual(decision["event_id"], "x:tweet-2001")

    # -- platform/account permission boundaries ---------------------------

    def test_platform_and_account_filter_boundaries(self):
        self._ingest()
        self._ingest(event_id="d:msg-1", platform="discord",
                     account_id="acct_hermes_public",
                     received_at="2026-08-08T00:01:00Z")
        by_account = self.client.get("/api/v1/events", params={"account_id": "acct_hermes_public"}).json()
        self.assertEqual(by_account["meta"]["total"], 2)
        none_account = self.client.get("/api/v1/events", params={"account_id": "nobody"}).json()
        self.assertEqual(none_account["meta"]["total"], 0)
        # accounts endpoint separates platform boundaries
        accounts = self.client.get("/api/v1/accounts").json()
        self.assertEqual(accounts["meta"]["total"], 0)  # no seed in this test app


if __name__ == "__main__":
    unittest.main()
