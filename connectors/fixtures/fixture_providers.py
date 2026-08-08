"""Deterministic fixture providers and the FixtureConnector base (B3).

MOCKED provider responses only — live provider access is BLOCKED (no live
credentials authorized). FixtureProvider modes simulate provider behaviors:
normal | rate_limited | timeout | auth_failure | malformed | revoked_signal.
"""
import hashlib
import json
import os

from ..base import Connector
from ..errors import (
    ConnectorAuthenticationError,
    ConnectorMalformedResponse,
    ConnectorRateLimited,
    ConnectorRevoked,
    ConnectorTimeout,
)

HERE = os.path.dirname(os.path.abspath(__file__))
RESPONSES = os.path.join(HERE, "responses")


class FixtureProvider:
    """Read-only mock provider reading canned responses from disk."""

    def __init__(self, platform, mode="normal", retry_after=15.0):
        self.platform = platform
        self.mode = mode
        self.retry_after = retry_after
        self.dir = os.path.join(RESPONSES, platform)

    def fetch(self, checkpoint=None):
        if self.mode == "rate_limited":
            raise ConnectorRateLimited(self.retry_after)
        if self.mode == "timeout":
            raise ConnectorTimeout("provider timed out")
        if self.mode == "auth_failure":
            raise ConnectorAuthenticationError("provider rejected credentials")
        if self.mode == "revoked_signal":
            raise ConnectorRevoked("provider reports connector revoked")
        if self.mode == "malformed":
            raise ConnectorMalformedResponse("provider returned unparseable payload")
        events = []
        for name in sorted(os.listdir(self.dir)):
            if name.endswith(".json"):
                with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                    events.append(json.load(fh))
        return events

    def fetch_page(self, checkpoint=None, page_size=10):
        """Paginated fetch: returns (events, next_cursor).

        Deterministic fixture pagination: events are read in sorted filename
        order, filtered to those after the cursor, then truncated to
        page_size. next_cursor is the id of the last returned event (or
        None when exhausted). Cursor semantics mirror real provider APIs.
        """
        all_events = self.fetch(checkpoint)
        cursor = None
        if checkpoint and isinstance(checkpoint, dict):
            cursor = checkpoint.get("after")
        page = []
        for event in all_events:
            event_id = str((event.get("data") or event).get("id") or "")
            if cursor is not None and event_id <= str(cursor):
                continue
            page.append(event)
            if len(page) >= page_size:
                break
        next_cursor = None
        if page:
            last = page[-1]
            next_cursor = str((last.get("data") or last).get("id") or "")
        return page, next_cursor

    def fetch_raw_text(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()


def manifest_checksum(connector_id):
    return hashlib.sha256(connector_id.encode("utf-8")).hexdigest()


class FixtureConnector(Connector):
    """Base adapter binding the Connector contract to a FixtureProvider."""

    platform = None
    connector_version = "1.0.0"
    supported_event_types = []
    supported_permissions = []
    required_secret_handles = []
    connector_mode = "native_api"
    risk_class = "low"
    provenance_method = "api_reference"
    revocation_method = "revoke_token"
    rate_limits = {"reads_per_minute": 300, "writes_per_hour": 0}
    data_retention = {"default_days": 30, "sensitive_days": 7, "delete_on_request": True}

    def __init__(self, secret_handles=None, fixture_provider=None, account_id="acct_hermes_public", require_handles=False, checkpoint_store=None):
        super().__init__(secret_handles, fixture_provider or FixtureProvider(self.platform), checkpoint_store=checkpoint_store)
        self.account_id = account_id
        self.require_handles = require_handles
        self.manifest = {
            "schema_version": "1.0.0",
            "connector_id": self.connector_id,
            "platform": self.platform,
            "version": self.connector_version,
            "connector_mode": self.connector_mode,
            "supported_event_types": self.supported_event_types,
            "supported_permissions": self.supported_permissions,
            "required_capabilities": [],
            "required_secret_handles": self.required_secret_handles,
            "rate_limits": self.rate_limits,
            "data_retention": self.data_retention,
            "provenance_method": self.provenance_method,
            "health_check": {"strategy": "fixture_provider", "timeout_seconds": 10},
            "revocation_method": self.revocation_method,
            "risk_class": self.risk_class,
            "approval_state": "approved_observe",
            "checksum": manifest_checksum(self.connector_id),
            "maintainer": "HERMES-SOCIAL",
            "license": "Apache-2.0",
            "status": "blocked_live",
        }

    def initialize(self):
        if self.require_handles and self.required_secret_handles:
            missing = [h for h in self.required_secret_handles if h not in self._secret_handles]
            if missing:
                raise ConnectorAuthenticationError(
                    "missing capability handles: %s" % ", ".join(missing)
                )
        self._initialized = True

    def read_events(self):
        self._ensure_active()
        return self._fixture_provider.fetch(self.get_checkpoint())

    def read_page(self, page_size=10):
        """Paged read: returns (events, next_cursor) and persists the cursor.

        The cursor advances deterministically so a resumed connector starts
        after the last returned event (no duplicate replay in the fixture).
        """
        self._ensure_active()
        events, next_cursor = self._fixture_provider.fetch_page(self.get_checkpoint(), page_size=page_size)
        if next_cursor:
            self.checkpoint_cursor({"after": next_cursor})
        return events, next_cursor

    def normalize_event(self, raw_event):
        raise NotImplementedError

    def _base_permissions(self):
        return {
            "observe": "observe" in self.supported_permissions,
            "analyze": "analyze" in self.supported_permissions,
            "draft": "draft" in self.supported_permissions,
            "execute": "execute" in self.supported_permissions,
        }

    def _event_type(self, raw_event):
        return self.supported_event_types[0] if self.supported_event_types else "post"
