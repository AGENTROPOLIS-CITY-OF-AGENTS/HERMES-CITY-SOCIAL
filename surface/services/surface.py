"""B4 Social Surface — service layer.

Consumes ONLY governed B2/B3 outputs:
  - released Social Events (validation_state=valid, quarantine_state=released,
    policy_state=allowed, council_state in analyze|draft) from the B3 Ingest
    Membrane
  - approval-request contract objects
  - action-receipt contract objects
  - council decisions derived from pipeline evaluation

B4 never ingests raw quarantined payloads; non-released membrane outcomes
increment operational counters only and never become visible read models.
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid
from typing import Any, Dict, List, Optional

from membrane.dedup import content_hash
from membrane.risk import level_for_score, score_content
from membrane.sanitize import sanitize_content

from .. import LIVE_STATUS, PRODUCTION_APPROVED, __version__
from ..models.records import (
    AccountRecord,
    ApprovalRecord,
    ConnectorStateRecord,
    DecisionRecord,
    DraftRecord,
    EventRecord,
    NotificationRecord,
    ReceiptRecord,
)
from ..repositories.base import SurfaceRepository
from ..views import serializers

PLATFORMS = ("x", "discord", "farcaster")
DRAFT_ACTIONS = ("draft_post", "draft_reply")
ELIGIBLE_COUNCIL_STATES = ("analyze", "draft")
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

_APPROVAL_REQUEST_SCHEMA_VERSION = "1.0.0"


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uuid(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


class SurfaceService:
    """B4 surface orchestrator bound to a repository."""

    def __init__(self, repo: SurfaceRepository):
        self.repo = repo

    # -- pilot seeding --------------------------------------------------

    def seed_pilot(self, registry) -> None:
        """Seed accounts + connector states from B3 pilot connector manifests.

        Real data from the governed connector definitions; nothing fabricated.
        Live status remains blocked_live (LIVE=BLOCKED).
        """
        now = _utcnow()
        for connector_id in registry.ids():
            connector = registry.get(connector_id)
            manifest = connector.manifest or {}
            health = connector.health_check()
            self.repo.upsert_connector_state(
                ConnectorStateRecord(
                    connector_id=connector_id,
                    platform=manifest.get("platform", ""),
                    status=manifest.get("status", "blocked_live"),
                    health_json=json.dumps(health),
                    manifest_json=json.dumps(manifest),
                    last_checked_at=now,
                )
            )
            permissions = {
                "observe": "observe" in (manifest.get("supported_permissions") or []),
                "analyze": "analyze" in (manifest.get("supported_permissions") or []),
                "draft": "draft" in (manifest.get("supported_permissions") or []),
                "execute": False,
            }
            self.repo.upsert_account(
                AccountRecord(
                    account_id=connector.account_id or "acct_hermes_public",
                    platform=manifest.get("platform", ""),
                    display_name="HERMES %s public" % manifest.get("platform", "").upper(),
                    connector_id=connector_id,
                    permissions_json=json.dumps(permissions),
                    status="active",
                    created_at=now,
                )
            )
        self.repo.increment_counter("connector_seed_count", len(registry.ids()))

    # -- governed ingest gate -------------------------------------------

    def ingest_released_event(self, event: Dict[str, Any]) -> str:
        """Persist ONE governed released event. Returns the stored event_id.

        Rejects anything that is not a fully governed, released B3 output.
        """
        validation_state = event.get("validation_state")
        quarantine_state = event.get("quarantine_state")
        policy_state = event.get("policy_state")
        council_state = event.get("council_state")
        if validation_state != "valid":
            raise ValueError("surface ingest requires validation_state=valid, got %r" % validation_state)
        if quarantine_state != "released":
            raise ValueError("surface ingest requires quarantine_state=released, got %r" % quarantine_state)
        if policy_state != "allowed":
            raise ValueError("surface ingest requires policy_state=allowed, got %r" % policy_state)
        if council_state not in ELIGIBLE_COUNCIL_STATES:
            raise ValueError("surface ingest requires council_state in analyze|draft, got %r" % council_state)

        content = event.get("content") or {}
        author = event.get("author") or {}
        provenance = event.get("provenance") or {}
        engagement = event.get("engagement") or {}
        record = EventRecord(
            event_id=str(event.get("event_id") or ""),
            platform=str(event.get("platform") or ""),
            connector_id=str(event.get("connector_id") or ""),
            connector_mode=str(event.get("connector_mode") or ""),
            account_id=str(event.get("account_id") or ""),
            event_type=str(event.get("event_type") or ""),
            author_id=str(author.get("id") or ""),
            author_display_name=author.get("display_name"),
            content_text=str(content.get("text") or ""),
            content_json=json.dumps(content, sort_keys=True),
            conversation_id=event.get("conversation_id"),
            engagement_json=json.dumps(engagement, sort_keys=True),
            provenance_json=json.dumps(provenance, sort_keys=True),
            risk_score=float(event.get("risk_score") or 0),
            risk_level=str(event.get("risk_level") or "low"),
            received_at=str(event.get("received_at") or _utcnow()),
            source_timestamp=str(event.get("source_timestamp") or ""),
            validation_state=validation_state,
            quarantine_state=quarantine_state,
            policy_state=policy_state,
            council_state=council_state,
            memory_eligibility=str(event.get("memory_eligibility") or "review_required"),
            retention_class=str(event.get("retention_class") or "standard"),
            content_hash=str(event.get("content_hash") or ""),
            correlation_id=str(event.get("correlation_id") or ""),
        )
        self.repo.insert_event(record)
        self.repo.increment_counter("events_ingested")
        self.repo.increment_counter("events_released")

        # decision record from the event's own governed evaluation
        self.repo.insert_decision(
            DecisionRecord(
                decision_id=_uuid("dec"),
                event_id=record.event_id,
                council_state=council_state,
                policy_state=policy_state,
                risk_level=record.risk_level,
                reason="membrane released to eligible council state %s" % council_state,
                decided_at=record.received_at,
                correlation_id=record.correlation_id,
            )
        )

        # operator notification derived from the released event
        self.repo.insert_notification(
            NotificationRecord(
                notification_id=_uuid("notif"),
                event_id=record.event_id,
                platform=record.platform,
                account_id=record.account_id,
                kind="event_released",
                title="%s %s" % (record.platform, record.event_type),
                body_text=record.content_text[:200],
                read=0,
                created_at=record.received_at,
            )
        )
        return record.event_id

    def ingest_from_membrane(self, result) -> Dict[str, Any]:
        """Bridge the B3 Ingest Membrane result into the surface.

        released -> stored read model; anything else -> counter only.
        """
        outcome = result.outcome
        if outcome == "released":
            event_id = self.ingest_released_event(result.event)
            return {"outcome": outcome, "event_id": event_id, "stored": True}
        if outcome == "quarantined":
            self.repo.increment_counter("events_quarantined")
        elif outcome == "duplicate":
            self.repo.increment_counter("duplicates_rejected")
        elif outcome == "rejected":
            self.repo.increment_counter("rejected")
        return {"outcome": outcome, "event_id": None, "stored": False}

    # -- read models -----------------------------------------------------

    def list_inbox(
        self, platform: Optional[str] = None, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_events(platform=platform, limit=limit, offset=offset)
        return serializers.page_view(page, serializers.inbox_item_view)

    def list_feed(
        self,
        platform: Optional[str] = None,
        conversation_id: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_events(platform=platform, limit=limit, offset=offset)
        items = []
        for record in page.items:
            if conversation_id and record.conversation_id != conversation_id:
                continue
            items.append(serializers.feed_item_view(record))
        total = len(items)
        return {"data": items[offset:], "meta": {"total": total, "limit": limit, "offset": offset}}

    def list_events(
        self,
        platform: Optional[str] = None,
        risk_level: Optional[str] = None,
        council_state: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_events(
            platform=platform, risk_level=risk_level,
            council_state=council_state, account_id=account_id,
            limit=limit, offset=offset,
        )
        return serializers.page_view(page, serializers.event_view)

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        record = self.repo.get_event(event_id)
        return serializers.event_view(record) if record else None

    def list_notifications(
        self,
        account_id: Optional[str] = None,
        read: Optional[bool] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_notifications(
            account_id=account_id, read=(None if read is None else int(read)),
            limit=limit, offset=offset,
        )
        return serializers.page_view(page, serializers.notification_view)

    def mark_notification_read(self, notification_id: str) -> bool:
        return self.repo.mark_notification_read(notification_id)

    def list_accounts(self, platform: Optional[str] = None) -> Dict[str, Any]:
        records = self.repo.list_accounts(platform=platform)
        return {"data": [serializers.account_view(r) for r in records],
                "meta": {"total": len(records)}}

    def list_connectors(self) -> Dict[str, Any]:
        records = self.repo.list_connector_states()
        return {"data": [serializers.connector_view(r) for r in records],
                "meta": {"total": len(records)}}

    # -- drafts (governed artifact; never published by B4) --------------

    def create_draft(
        self,
        platform: str,
        account_id: str,
        operator: str,
        action: str,
        content: Dict[str, Any],
        conversation_ref: Optional[str] = None,
        source_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an internal governed draft. NEVER triggers publication.

        Content is sanitized through the B3 sanitizer, hashed, risk-scored,
        and an approval-request (approve_draft) is created for the queue.
        """
        if platform not in PLATFORMS:
            raise ValueError("platform must be one of %s" % (PLATFORMS,))
        if action not in DRAFT_ACTIONS:
            raise ValueError("action must be one of %s" % (DRAFT_ACTIONS,))
        if not isinstance(content, dict) or not str(content.get("text") or "").strip():
            raise ValueError("draft content.text is required")

        sanitized, warnings, links, creds = sanitize_content(content)
        digest = content_hash(sanitized)
        risk_score = score_content(sanitized)
        if creds:
            risk_score = min(100, risk_score + 30)
        risk_level = level_for_score(risk_score)

        now = _utcnow()
        draft_id = _uuid("draft")
        correlation_id = _uuid("corr")
        draft = DraftRecord(
            draft_id=draft_id,
            platform=platform,
            account_id=account_id,
            operator=operator,
            action=action,
            content_text=str(sanitized.get("text") or ""),
            content_json=json.dumps(sanitized, sort_keys=True),
            conversation_ref=conversation_ref,
            source_event_id=source_event_id,
            provenance_json=json.dumps({
                "created_by": operator,
                "source_event_id": source_event_id,
                "warnings": warnings,
                "links": links,
            }, sort_keys=True),
            risk_score=float(risk_score),
            risk_level=risk_level,
            approval_state="pending",
            content_hash=digest,
            created_at=now,
            updated_at=now,
        )
        self.repo.insert_draft(draft)

        expires_at = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        approval = {
            "schema_version": _APPROVAL_REQUEST_SCHEMA_VERSION,
            "approval_id": _uuid("appr"),
            "event_id": source_event_id,
            "draft_id": draft_id,
            "requested_action": "approve_draft",
            "requested_by": operator,
            "required_approvers": ["human_operator"],
            "approval_policy": "draft_gate",
            "status": "pending",
            "approvals": [],
            "rejections": [],
            "revision_requests": [],
            "content_hash": digest,
            "created_at": now,
            "expires_at": expires_at,
            "correlation_id": correlation_id,
            "platform": platform,
            "account_id": account_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "reason": "internal governed draft awaiting human review",
        }
        self.repo.insert_approval(
            ApprovalRecord(
                approval_id=approval["approval_id"],
                payload_json=json.dumps(approval, sort_keys=True),
                status="pending",
                created_at=now,
                expires_at=expires_at,
                correlation_id=correlation_id,
            )
        )
        self.repo.increment_counter("drafts_created")
        return serializers.draft_view(draft)

    def list_drafts(
        self,
        platform: Optional[str] = None,
        approval_state: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_drafts(platform=platform, approval_state=approval_state,
                                     limit=limit, offset=offset)
        return serializers.page_view(page, serializers.draft_view)

    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        record = self.repo.get_draft(draft_id)
        return serializers.draft_view(record) if record else None

    # -- approvals ------------------------------------------------------

    def list_approvals(
        self, status: Optional[str] = None, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_approvals(status=status, limit=limit, offset=offset)
        return serializers.page_view(page, serializers.approval_view)

    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        record = self.repo.get_approval(approval_id)
        return serializers.approval_view(record) if record else None

    # -- council decisions ----------------------------------------------

    def list_decisions(
        self, event_id: Optional[str] = None, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_decisions(event_id=event_id, limit=limit, offset=offset)
        return serializers.page_view(page, serializers.decision_view)

    # -- receipts -------------------------------------------------------

    def store_receipt(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Store a permanent action-receipt contract object (read-only for MVP)."""
        receipt_id = str(receipt.get("receipt_id") or "")
        if not receipt_id:
            raise ValueError("receipt_id is required")
        now = _utcnow()
        self.repo.insert_receipt(
            ReceiptRecord(
                receipt_id=receipt_id,
                payload_json=json.dumps(receipt, sort_keys=True),
                received_at=now,
            )
        )
        self.repo.increment_counter("receipts_stored")
        return serializers.receipt_view(self.repo.get_receipt(receipt_id))

    def list_receipts(
        self, platform: Optional[str] = None, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), MAX_LIMIT)
        page = self.repo.list_receipts(platform=platform, limit=limit, offset=offset)
        return serializers.page_view(page, serializers.receipt_view)

    def get_receipt(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        record = self.repo.get_receipt(receipt_id)
        return serializers.receipt_view(record) if record else None

    # -- analytics / health ---------------------------------------------

    def analytics(self) -> Dict[str, Any]:
        """Operational read-model analytics computed from real stored data."""
        counters = self.repo.counters_snapshot()
        risk_distribution = {}
        for record in self.repo.list_events(limit=MAX_LIMIT, offset=0).items:
            risk_distribution[record.risk_level] = risk_distribution.get(record.risk_level, 0) + 1
        connectors = self.repo.list_connector_states()
        connector_status = {}
        for record in connectors:
            connector_status[record.status] = connector_status.get(record.status, 0) + 1
        metrics = {
            "events_ingested": counters.get("events_ingested", 0),
            "events_released": counters.get("events_released", 0),
            "events_quarantined": counters.get("events_quarantined", 0),
            "duplicates_rejected": counters.get("duplicates_rejected", 0),
            "rejected": counters.get("rejected", 0),
            "drafts_created": counters.get("drafts_created", 0),
            "receipts_stored": counters.get("receipts_stored", 0),
            "draft_count": self.repo.list_drafts(limit=1, offset=0).total,
            "approval_backlog": self.repo.list_approvals(status="pending", limit=1, offset=0).total,
            "approvals_total": self.repo.list_approvals(limit=1, offset=0).total,
            "receipts_total": self.repo.list_receipts(limit=1, offset=0).total,
            "decisions_total": self.repo.list_decisions(limit=1, offset=0).total,
            "notifications_total": self.repo.list_notifications(limit=1, offset=0).total,
            "risk_distribution": risk_distribution,
            "connector_count": len(connectors),
            "connector_status": connector_status,
        }
        return serializers.analytics_view(metrics)

    def health(self) -> Dict[str, Any]:
        counters = self.repo.counters_snapshot()
        connectors = [serializers.connector_view(r) for r in self.repo.list_connector_states()]
        return {
            "service": "hermes-social-surface",
            "version": __version__,
            "db": "ok" if self.repo.db_health() else "unavailable",
            "live_status": LIVE_STATUS,
            "production_approved": PRODUCTION_APPROVED,
            "platforms": list(PLATFORMS),
            "connectors": connectors,
            "counters": counters,
            "surface_ingest_gate": {
                "validation_state": "valid",
                "quarantine_state": "released",
                "policy_state": "allowed",
                "council_state": ["analyze", "draft"],
            },
            "publish_endpoints": [],
            "execute_available": False,
        }
