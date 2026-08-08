"""B4 Social Surface — repository abstraction.

The surface service depends only on this interface. SQLite is the development
backend (surface/repositories/sqlite.py); PostgreSQL can implement the same
interface for staging/production without rewriting surface logic.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from ..models.records import (
    AccountRecord,
    ApprovalRecord,
    ConnectorStateRecord,
    DecisionRecord,
    DraftRecord,
    EventRecord,
    NotificationRecord,
    Page,
    ReceiptRecord,
)


class SurfaceRepository(abc.ABC):
    """Storage contract for the B4 read model."""

    # -- events ---------------------------------------------------------
    @abc.abstractmethod
    def insert_event(self, record: EventRecord) -> None:
        """Persist a governed released event."""

    @abc.abstractmethod
    def list_events(
        self,
        platform: Optional[str] = None,
        risk_level: Optional[str] = None,
        council_state: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        """Page released events (newest first)."""

    @abc.abstractmethod
    def get_event(self, event_id: str) -> Optional[EventRecord]:
        """Fetch one event by id."""

    # -- drafts ---------------------------------------------------------
    @abc.abstractmethod
    def insert_draft(self, record: DraftRecord) -> None:
        """Persist an internal governed draft."""

    @abc.abstractmethod
    def list_drafts(
        self,
        platform: Optional[str] = None,
        approval_state: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        """Page drafts (newest first)."""

    @abc.abstractmethod
    def get_draft(self, draft_id: str) -> Optional[DraftRecord]:
        """Fetch one draft by id."""

    # -- approvals ------------------------------------------------------
    @abc.abstractmethod
    def insert_approval(self, record: ApprovalRecord) -> None:
        """Persist an approval-request contract record."""

    @abc.abstractmethod
    def list_approvals(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        """Page approval requests (newest first)."""

    @abc.abstractmethod
    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        """Fetch one approval request by id."""

    # -- council decisions ----------------------------------------------
    @abc.abstractmethod
    def insert_decision(self, record: DecisionRecord) -> None:
        """Persist a council decision."""

    @abc.abstractmethod
    def list_decisions(
        self,
        event_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        """Page council decisions (newest first)."""

    # -- receipts -------------------------------------------------------
    @abc.abstractmethod
    def insert_receipt(self, record: ReceiptRecord) -> None:
        """Persist a permanent action receipt."""

    @abc.abstractmethod
    def list_receipts(
        self,
        platform: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        """Page action receipts (newest first)."""

    @abc.abstractmethod
    def get_receipt(self, receipt_id: str) -> Optional[ReceiptRecord]:
        """Fetch one receipt by id."""

    # -- accounts -------------------------------------------------------
    @abc.abstractmethod
    def upsert_account(self, record: AccountRecord) -> None:
        """Insert or update a governed account."""

    @abc.abstractmethod
    def list_accounts(self, platform: Optional[str] = None) -> List[AccountRecord]:
        """List governed accounts."""

    # -- notifications --------------------------------------------------
    @abc.abstractmethod
    def insert_notification(self, record: NotificationRecord) -> None:
        """Persist a notification."""

    @abc.abstractmethod
    def list_notifications(
        self,
        account_id: Optional[str] = None,
        read: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        """Page notifications (newest first)."""

    @abc.abstractmethod
    def mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification read. Returns True when found."""

    # -- connector state ------------------------------------------------
    @abc.abstractmethod
    def upsert_connector_state(self, record: ConnectorStateRecord) -> None:
        """Insert or update connector state."""

    @abc.abstractmethod
    def list_connector_states(self) -> List[ConnectorStateRecord]:
        """List connector states."""

    # -- counters / analytics ------------------------------------------
    @abc.abstractmethod
    def increment_counter(self, name: str, delta: int = 1) -> None:
        """Increment an operational counter."""

    @abc.abstractmethod
    def get_counter(self, name: str) -> int:
        """Read an operational counter."""

    @abc.abstractmethod
    def counters_snapshot(self) -> dict:
        """Snapshot all operational counters."""

    @abc.abstractmethod
    def db_health(self) -> bool:
        """True when the database is reachable."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the underlying connection."""
