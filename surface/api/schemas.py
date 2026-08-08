"""B4 Social Surface — API schemas (pydantic response/request models).

These models define the public /api/v1 contract. All content fields are
already sanitized by the B3 pipeline or the surface service; nothing raw
leaves the API.
"""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

Platform = Literal["x", "discord", "farcaster"]
DraftAction = Literal["draft_post", "draft_reply"]


class ListMeta(BaseModel):
    total: int
    limit: int = 50
    offset: int = 0


T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: List[T]
    meta: ListMeta


class AuthorOut(BaseModel):
    id: str
    display_name: Optional[str] = None


class RiskOut(BaseModel):
    score: float
    level: str


class EventOut(BaseModel):
    event_id: str
    platform: str
    connector_id: str
    connector_mode: str
    account_id: str
    event_type: str
    author: AuthorOut
    content: Dict[str, Any]
    conversation_id: Optional[str] = None
    risk: RiskOut
    council_state: str
    policy_state: str
    received_at: str
    source_reference: Optional[str] = None
    content_hash: str
    correlation_id: str


class InboxItemOut(BaseModel):
    event_id: str
    platform: str
    event_type: str
    author_display_name: Optional[str] = None
    text: str
    risk_level: str
    council_state: str
    received_at: str
    conversation_id: Optional[str] = None
    content_hash: str


class FeedItemOut(BaseModel):
    event_id: str
    platform: str
    conversation_id: Optional[str] = None
    author_display_name: Optional[str] = None
    text: str
    risk_level: str
    received_at: str


class NotificationOut(BaseModel):
    notification_id: str
    event_id: str
    platform: str
    account_id: str
    kind: str
    title: str
    body_text: str
    read: bool
    created_at: str


class AccountOut(BaseModel):
    account_id: str
    platform: str
    display_name: str
    connector_id: str
    permissions: Dict[str, Any]
    status: str
    created_at: str


class ConnectorOut(BaseModel):
    connector_id: str
    platform: str
    status: str
    health: Dict[str, Any]
    manifest: Dict[str, Any]
    last_checked_at: str


class DraftOut(BaseModel):
    draft_id: str
    platform: str
    account_id: str
    operator: str
    action: str
    content: Dict[str, Any]
    conversation_ref: Optional[str] = None
    source_event_id: Optional[str] = None
    risk: RiskOut
    approval_state: str
    content_hash: str
    created_at: str
    updated_at: str


class DraftCreateIn(BaseModel):
    platform: Platform
    account_id: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    action: DraftAction
    content: Dict[str, Any]
    conversation_ref: Optional[str] = None
    source_event_id: Optional[str] = None


class ApprovalOut(BaseModel):
    approval_id: str
    requested_action: Optional[str] = None
    platform: Optional[str] = None
    account_id: Optional[str] = None
    draft_id: Optional[str] = None
    event_id: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    reason: Optional[str] = None
    requested_by: Optional[str] = None
    required_approvers: List[str] = Field(default_factory=list)
    approval_policy: Optional[str] = None
    status: str
    expires_at: str
    created_at: str
    correlation_id: str
    content_hash: Optional[str] = None


class DecisionOut(BaseModel):
    decision_id: str
    event_id: str
    council_state: str
    policy_state: str
    risk_level: str
    reason: str
    decided_at: str
    correlation_id: str


class ReceiptOut(BaseModel):
    receipt_id: str
    payload: Dict[str, Any]
    received_at: str


class HealthOut(BaseModel):
    service: str
    version: str
    db: str
    live_status: str
    production_approved: str
    platforms: List[str]
    connectors: List[ConnectorOut]
    counters: Dict[str, int]
    surface_ingest_gate: Dict[str, Any]
    publish_endpoints: List[str]
    execute_available: bool


class AnalyticsOut(BaseModel):
    state: str
    metrics: Dict[str, Any]
