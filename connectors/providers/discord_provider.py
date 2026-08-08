"""Discord read-only connector adapter (B3).

Permission: OBSERVE + ANALYZE. Live credentials are NOT authorized; the
adapter is exercised through the FixtureProvider with mocked responses.
"""

from ..fixtures.fixture_providers import FixtureConnector


class DiscordConnector(FixtureConnector):
    connector_id = "conn_discord_observe_001"
    platform = "discord"
    supported_event_types = ["message", "channel_message"]
    supported_permissions = ["observe", "analyze"]
    required_secret_handles = ["discord_bot_token"]
    connector_mode = "native_api"
    risk_class = "moderate"
    revocation_method = "revoke_token"

    def normalize_event(self, raw_event):
        data = raw_event.get("data", raw_event)
        author = data.get("author", {})
        created_at = data.get("timestamp")
        return {
            "schema_version": "1.0.0",
            "event_id": "discord:%s" % data.get("id", ""),
            "platform": "discord",
            "connector_id": self.connector_id,
            "connector_mode": self.connector_mode,
            "account_id": self.account_id,
            "event_type": self._event_type(data),
            "author": {
                "id": str(author.get("id") or ""),
                "display_name": author.get("username"),
            },
            "content": {"text": data.get("content", "")},
            "media": [{"type": a.get("content_type"), "url": a.get("url")} for a in data.get("attachments", [])],
            "conversation_id": data.get("channel_id"),
            "engagement": {},
            "permissions": self._base_permissions(),
            "provenance": {
                "connector_type": self.connector_mode,
                "source_reference": "mock://discord/%s" % data.get("id", ""),
                "retrieved_at": created_at or "",
            },
            "source_timestamp": created_at or "",
        }
