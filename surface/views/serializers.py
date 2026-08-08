"""B4 Social Surface — view serializers (API-safe read models).

Every view is built from a governed record and passes through a recursive
credential scrub. Raw provider payloads are never present in stored records,
so they can never appear in a view. This module is the last defense line for
"no raw credentials in model/UI state".
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# Mirror of the B3 risk signal set; credential-like keys are stripped at any
# depth before a value can become a view.
CREDENTIAL_KEYS = {
    "token", "secret", "password", "authorization", "cookie",
    "api_key", "apikey", "bearer", "client_secret", "access_key",
    "private_key",
}

UNTRUSTED_KEYS = {"untrusted"}


def scrub(value: Any) -> Any:
    """Recursively remove credential-like keys from a value."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in CREDENTIAL_KEYS:
                continue
            out[key] = scrub(item)
        return out
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def _json_loads(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def event_view(record) -> Dict[str, Any]:
    """API-safe view of a governed Social Event record."""
    content = scrub(_json_loads(record.content_json, {"text": record.content_text}))
    provenance = scrub(_json_loads(record.provenance_json, {}))
    return {
        "event_id": record.event_id,
        "platform": record.platform,
        "connector_id": record.connector_id,
        "connector_mode": record.connector_mode,
        "account_id": record.account_id,
        "event_type": record.event_type,
        "author": {"id": record.author_id, "display_name": record.author_display_name},
        "content": content,
        "conversation_id": record.conversation_id,
        "risk": {"score": record.risk_score, "level": record.risk_level},
        "council_state": record.council_state,
        "policy_state": record.policy_state,
        "received_at": record.received_at,
        "source_reference": provenance.get("source_reference"),
        "content_hash": record.content_hash,
        "correlation_id": record.correlation_id,
    }


def inbox_item_view(record) -> Dict[str, Any]:
    """Unified inbox item (platform-neutral read model)."""
    return {
        "event_id": record.event_id,
        "platform": record.platform,
        "event_type": record.event_type,
        "author_display_name": record.author_display_name,
        "text": record.content_text,
        "risk_level": record.risk_level,
        "council_state": record.council_state,
        "received_at": record.received_at,
        "conversation_id": record.conversation_id,
        "content_hash": record.content_hash,
    }


def feed_item_view(record) -> Dict[str, Any]:
    """Feed item (per-platform / per-conversation read model)."""
    return {
        "event_id": record.event_id,
        "platform": record.platform,
        "conversation_id": record.conversation_id,
        "author_display_name": record.author_display_name,
        "text": record.content_text,
        "risk_level": record.risk_level,
        "received_at": record.received_at,
    }


def notification_view(record) -> Dict[str, Any]:
    return {
        "notification_id": record.notification_id,
        "event_id": record.event_id,
        "platform": record.platform,
        "account_id": record.account_id,
        "kind": record.kind,
        "title": record.title,
        "body_text": record.body_text,
        "read": bool(record.read),
        "created_at": record.created_at,
    }


def account_view(record) -> Dict[str, Any]:
    return {
        "account_id": record.account_id,
        "platform": record.platform,
        "display_name": record.display_name,
        "connector_id": record.connector_id,
        "permissions": scrub(_json_loads(record.permissions_json, {})),
        "status": record.status,
        "created_at": record.created_at,
    }


def connector_view(record) -> Dict[str, Any]:
    manifest = scrub(_json_loads(record.manifest_json, {}))
    health = scrub(_json_loads(record.health_json, {}))
    return {
        "connector_id": record.connector_id,
        "platform": record.platform,
        "status": record.status,
        "health": health,
        "manifest": {
            "version": manifest.get("version"),
            "connector_mode": manifest.get("connector_mode"),
            "supported_permissions": manifest.get("supported_permissions"),
            "required_secret_handles": manifest.get("required_secret_handles"),
            "approval_state": manifest.get("approval_state"),
            "status": manifest.get("status"),
            "risk_class": manifest.get("risk_class"),
        },
        "last_checked_at": record.last_checked_at,
    }


def draft_view(record) -> Dict[str, Any]:
    content = scrub(_json_loads(record.content_json, {"text": record.content_text}))
    return {
        "draft_id": record.draft_id,
        "platform": record.platform,
        "account_id": record.account_id,
        "operator": record.operator,
        "action": record.action,
        "content": content,
        "conversation_ref": record.conversation_ref,
        "source_event_id": record.source_event_id,
        "risk": {"score": record.risk_score, "level": record.risk_level},
        "approval_state": record.approval_state,
        "content_hash": record.content_hash,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def approval_view(record) -> Dict[str, Any]:
    """Operator-facing approval queue item from the approval-request contract.

    Never exposes raw secrets — only capability handle names and governed
    metadata carried by the contract.
    """
    payload = scrub(_json_loads(record.payload_json, {}))
    return {
        "approval_id": record.approval_id,
        "requested_action": payload.get("requested_action"),
        "platform": payload.get("platform"),
        "account_id": payload.get("account_id"),
        "draft_id": payload.get("draft_id"),
        "event_id": payload.get("event_id"),
        "risk_level": payload.get("risk_level"),
        "risk_score": payload.get("risk_score"),
        "reason": payload.get("reason"),
        "requested_by": payload.get("requested_by"),
        "required_approvers": payload.get("required_approvers"),
        "approval_policy": payload.get("approval_policy"),
        "status": record.status,
        "expires_at": record.expires_at,
        "created_at": record.created_at,
        "correlation_id": record.correlation_id,
        "content_hash": payload.get("content_hash"),
    }


def decision_view(record) -> Dict[str, Any]:
    return {
        "decision_id": record.decision_id,
        "event_id": record.event_id,
        "council_state": record.council_state,
        "policy_state": record.policy_state,
        "risk_level": record.risk_level,
        "reason": record.reason,
        "decided_at": record.decided_at,
        "correlation_id": record.correlation_id,
    }


def receipt_view(record) -> Dict[str, Any]:
    """Permanent receipt view. Raw receipt payload is contract data, scrubbed."""
    return {
        "receipt_id": record.receipt_id,
        "payload": scrub(_json_loads(record.payload_json, {})),
        "received_at": record.received_at,
    }


def page_view(page, item_view) -> Dict[str, Any]:
    return {
        "data": [item_view(item) for item in page.items],
        "meta": {
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
        },
    }


def analytics_view(analytics: Dict[str, Any]) -> Dict[str, Any]:
    """Operational read-model analytics. No fabricated values."""
    state = "NO_DATA"
    if analytics.get("events_ingested", 0) > 0 or analytics.get("connector_count", 0) > 0:
        state = "AVAILABLE"
    return {"state": state, "metrics": analytics}
