"""Farcaster read-only connector adapter (B3).

Permission: OBSERVE only. Live credentials are NOT authorized; the adapter is
exercised through the FixtureProvider with mocked responses.
"""

from ..fixtures.fixture_providers import FixtureConnector


class FarcasterConnector(FixtureConnector):
    connector_id = "conn_farcaster_observe_001"
    platform = "farcaster"
    supported_event_types = ["cast", "reply_cast", "quote_cast"]
    supported_permissions = ["observe"]
    required_secret_handles = ["farcaster_api_key"]
    connector_mode = "native_api"
    risk_class = "low"
    revocation_method = "revoke_token"

    def normalize_event(self, raw_event):
        data = raw_event.get("data", raw_event)
        author = data.get("author", {})
        created_at = data.get("timestamp")
        return {
            "schema_version": "1.0.0",
            "event_id": "farcaster:%s" % data.get("hash", ""),
            "platform": "farcaster",
            "connector_id": self.connector_id,
            "connector_mode": self.connector_mode,
            "account_id": self.account_id,
            "event_type": self._event_type(data),
            "author": {
                "id": str(author.get("fid") or ""),
                "display_name": author.get("username"),
            },
            "content": {"text": data.get("text", "")},
            "media": [],
            "conversation_id": data.get("parent_hash"),
            "engagement": {"reactions": data.get("reactions") or {}},
            "permissions": self._base_permissions(),
            "provenance": {
                "connector_type": self.connector_mode,
                "source_reference": "mock://farcaster/%s" % data.get("hash", ""),
                "retrieved_at": created_at or "",
            },
            "source_timestamp": created_at or "",
        }
