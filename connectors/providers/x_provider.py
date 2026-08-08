"""X (Twitter) read-only connector adapter (B3).

Permission: OBSERVE only. Live credentials are NOT authorized; the adapter is
exercised through the FixtureProvider with mocked provider responses.
"""

from ..fixtures.fixture_providers import FixtureConnector


class XConnector(FixtureConnector):
    connector_id = "conn_x_observe_001"
    platform = "x"
    supported_event_types = ["tweet", "mention", "reply"]
    supported_permissions = ["observe"]
    required_secret_handles = ["x_bearer_token"]
    connector_mode = "native_api"
    risk_class = "low"
    revocation_method = "revoke_token"

    def normalize_event(self, raw_event):
        data = raw_event.get("data", raw_event)
        author = data.get("author", {})
        created_at = data.get("created_at") or raw_event.get("timestamp")
        return {
            "schema_version": "1.0.0",
            "event_id": "x:%s" % data.get("id", ""),
            "platform": "x",
            "connector_id": self.connector_id,
            "connector_mode": self.connector_mode,
            "account_id": self.account_id,
            "event_type": self._event_type(data),
            "author": {
                "id": str(author.get("id") or data.get("author_id") or ""),
                "display_name": author.get("display_name") or data.get("username"),
            },
            "content": {"text": data.get("text", ""), "raw_language": data.get("lang")},
            "media": [],
            "conversation_id": data.get("conversation_id"),
            "engagement": data.get("public_metrics") or {},
            "permissions": self._base_permissions(),
            "provenance": {
                "connector_type": self.connector_mode,
                "source_reference": "mock://x/%s" % data.get("id", ""),
                "retrieved_at": created_at or "",
            },
            "source_timestamp": created_at or "",
        }
