import unittest

from integrations.docking_spatial_projection import project_social_event, project_events


class DockingSpatialProjectionTests(unittest.TestCase):
    def base_event(self):
        return {
            "event_id": "moltbook:evt-1",
            "platform": "moltbook",
            "account_id": "acct-1",
            "author": {"id": "agent-17", "display_name": "Agent 17"},
            "validation_state": "valid",
            "quarantine_state": "released",
            "policy_state": "allowed",
            "council_state": "analyze",
            "source_timestamp": "2026-08-25T03:00:00Z",
        }

    def test_allowed_social_event_projects_to_commons(self):
        projected = project_social_event(self.base_event())
        self.assertEqual(projected["district"], "docking")
        self.assertEqual(projected["space"], "social_commons")
        self.assertEqual(projected["activity"], "meeting")
        self.assertEqual(projected["origin"], "MOLTBOOK")
        self.assertEqual(projected["truth_state"], "LIVE")
        self.assertNotIn("content", projected)

    def test_quarantined_event_projects_blocked(self):
        event = self.base_event()
        event["quarantine_state"] = "quarantined"
        projected = project_social_event(event)
        self.assertEqual(projected["space"], "quarantine_bay")
        self.assertEqual(projected["policy_state"], "blocked")
        self.assertEqual(projected["activity"], "blocked")

    def test_malformed_items_fail_closed_in_batch(self):
        projected = project_events([{}, self.base_event()])
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["agent_id"], "agent-17")


if __name__ == "__main__":
    unittest.main()
