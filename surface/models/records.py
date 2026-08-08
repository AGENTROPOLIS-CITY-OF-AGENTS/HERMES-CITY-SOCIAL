"""B4 Social Surface — persisted record models.

Dataclasses mirroring the B2/B3 governed contracts. These are the ONLY shapes
that enter the surface repository; raw provider payloads are never stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EventRecord:
    """A governed Social Event released by the B3 Ingest Membrane."""

    event_id: str
    platform: str
    connector_id: str
    connector_mode: str
    account_id: str
    event_type: str
    author_id: str
    author_display_name: Optional[str]
    content_text: str
    content_json: str  # sanitized content object (JSON)
    conversation_id: Optional[str]
    engagement_json: str
    provenance_json: str
    risk_score: float
    risk_level: str
    received_at: str
    source_timestamp: str
    validation_state: str
    quarantine_state: str
    policy_state: str
    council_state: str
    memory_eligibility: str
    retention_class: str
    content_hash: str
    correlation_id: str


@dataclass
class DraftRecord:
    """An internal governed draft artifact. NEVER published by B4."""

    draft_id: str
    platform: str
    account_id: str
    operator: str
    action: str  # draft_post | draft_reply
    content_text: str
    content_json: str
    conversation_ref: Optional[str]
    source_event_id: Optional[str]
    provenance_json: str
    risk_score: float
    risk_level: str
    approval_state: str  # pending | approved | rejected | expired | revised | cancelled
    content_hash: str
    created_at: str
    updated_at: str


@dataclass
class ApprovalRecord:
    """An approval-request contract record (schema approval-request v1.0.0)."""

    approval_id: str
    payload_json: str  # full governed approval-request object
    status: str
    created_at: str
    expires_at: str
    correlation_id: str


@dataclass
class DecisionRecord:
    """A council decision attached to an event."""

    decision_id: str
    event_id: str
    council_state: str
    policy_state: str
    risk_level: str
    reason: str
    decided_at: str
    correlation_id: str


@dataclass
class ReceiptRecord:
    """A permanent action-receipt contract record (schema action-receipt v1.0.0)."""

    receipt_id: str
    payload_json: str
    received_at: str


@dataclass
class AccountRecord:
    """A governed social account (derived from pilot connectors)."""

    account_id: str
    platform: str
    display_name: str
    connector_id: str
    permissions_json: str
    status: str
    created_at: str


@dataclass
class NotificationRecord:
    """An operator notification derived from a released event."""

    notification_id: str
    event_id: str
    platform: str
    account_id: str
    kind: str
    title: str
    body_text: str
    read: int
    created_at: str


@dataclass
class ConnectorStateRecord:
    """Current connector state + manifest (status blocked_live in pilot)."""

    connector_id: str
    platform: str
    status: str
    health_json: str
    manifest_json: str
    last_checked_at: str


@dataclass
class Page:
    """Pagination envelope returned by repository list operations."""

    items: List[Any]
    total: int
    limit: int
    offset: int
