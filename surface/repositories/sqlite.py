"""B4 Social Surface — SQLite development backend.

Implements SurfaceRepository over the standard-library sqlite3 module. The
development backend for B4; PostgreSQL replaces this class in staging and
production behind the same interface.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
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
from .base import SurfaceRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    connector_id TEXT NOT NULL,
    connector_mode TEXT NOT NULL,
    account_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_display_name TEXT,
    content_text TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}',
    conversation_id TEXT,
    engagement_json TEXT NOT NULL DEFAULT '{}',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    risk_score REAL NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    received_at TEXT NOT NULL,
    source_timestamp TEXT NOT NULL DEFAULT '',
    validation_state TEXT NOT NULL DEFAULT 'valid',
    quarantine_state TEXT NOT NULL DEFAULT 'released',
    policy_state TEXT NOT NULL DEFAULT 'allowed',
    council_state TEXT NOT NULL DEFAULT 'analyze',
    memory_eligibility TEXT NOT NULL DEFAULT 'eligible',
    retention_class TEXT NOT NULL DEFAULT 'standard',
    content_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_platform ON events(platform);
CREATE INDEX IF NOT EXISTS idx_events_risk ON events(risk_level);
CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at DESC);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    operator TEXT NOT NULL,
    action TEXT NOT NULL,
    content_text TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}',
    conversation_ref TEXT,
    source_event_id TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    risk_score REAL NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    approval_state TEXT NOT NULL DEFAULT 'pending',
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drafts_platform ON drafts(platform);
CREATE INDEX IF NOT EXISTS idx_drafts_state ON drafts(approval_state);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    council_state TEXT NOT NULL,
    policy_state TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    connector_id TEXT NOT NULL,
    permissions_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    PRIMARY KEY (account_id, platform)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);

CREATE TABLE IF NOT EXISTS connector_states (
    connector_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    status TEXT NOT NULL,
    health_json TEXT NOT NULL DEFAULT '{}',
    manifest_json TEXT NOT NULL DEFAULT '{}',
    last_checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS counters (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
"""


class SQLiteSurfaceRepository(SurfaceRepository):
    """SQLite implementation of the B4 surface repository."""

    def __init__(self, db_path: str = ":memory:"):
        if db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # -- helpers ---------------------------------------------------------

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def _execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    @staticmethod
    def _row_event(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            event_id=row["event_id"],
            platform=row["platform"],
            connector_id=row["connector_id"],
            connector_mode=row["connector_mode"],
            account_id=row["account_id"],
            event_type=row["event_type"],
            author_id=row["author_id"],
            author_display_name=row["author_display_name"],
            content_text=row["content_text"],
            content_json=row["content_json"],
            conversation_id=row["conversation_id"],
            engagement_json=row["engagement_json"],
            provenance_json=row["provenance_json"],
            risk_score=row["risk_score"],
            risk_level=row["risk_level"],
            received_at=row["received_at"],
            source_timestamp=row["source_timestamp"],
            validation_state=row["validation_state"],
            quarantine_state=row["quarantine_state"],
            policy_state=row["policy_state"],
            council_state=row["council_state"],
            memory_eligibility=row["memory_eligibility"],
            retention_class=row["retention_class"],
            content_hash=row["content_hash"],
            correlation_id=row["correlation_id"],
        )

    # -- events ---------------------------------------------------------

    def insert_event(self, record: EventRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO events (
                event_id, platform, connector_id, connector_mode, account_id,
                event_type, author_id, author_display_name, content_text,
                content_json, conversation_id, engagement_json, provenance_json,
                risk_score, risk_level, received_at, source_timestamp,
                validation_state, quarantine_state, policy_state, council_state,
                memory_eligibility, retention_class, content_hash, correlation_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.event_id, record.platform, record.connector_id,
                record.connector_mode, record.account_id, record.event_type,
                record.author_id, record.author_display_name, record.content_text,
                record.content_json, record.conversation_id, record.engagement_json,
                record.provenance_json, record.risk_score, record.risk_level,
                record.received_at, record.source_timestamp,
                record.validation_state, record.quarantine_state,
                record.policy_state, record.council_state,
                record.memory_eligibility, record.retention_class,
                record.content_hash, record.correlation_id,
            ),
        )

    def list_events(
        self,
        platform: Optional[str] = None,
        risk_level: Optional[str] = None,
        council_state: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        where, params = [], []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if risk_level:
            where.append("risk_level = ?")
            params.append(risk_level)
        if council_state:
            where.append("council_state = ?")
            params.append(council_state)
        if account_id:
            where.append("account_id = ?")
            params.append(account_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._query("SELECT COUNT(*) AS c FROM events" + clause, tuple(params))[0]["c"]
        rows = self._query(
            "SELECT * FROM events" + clause + " ORDER BY received_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        return Page([self._row_event(r) for r in rows], int(total), limit, offset)

    def get_event(self, event_id: str) -> Optional[EventRecord]:
        rows = self._query("SELECT * FROM events WHERE event_id = ?", (event_id,))
        return self._row_event(rows[0]) if rows else None

    # -- drafts ---------------------------------------------------------

    def insert_draft(self, record: DraftRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO drafts (
                draft_id, platform, account_id, operator, action, content_text,
                content_json, conversation_ref, source_event_id, provenance_json,
                risk_score, risk_level, approval_state, content_hash,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.draft_id, record.platform, record.account_id,
                record.operator, record.action, record.content_text,
                record.content_json, record.conversation_ref,
                record.source_event_id, record.provenance_json,
                record.risk_score, record.risk_level, record.approval_state,
                record.content_hash, record.created_at, record.updated_at,
            ),
        )

    def list_drafts(
        self,
        platform: Optional[str] = None,
        approval_state: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        where, params = [], []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if approval_state:
            where.append("approval_state = ?")
            params.append(approval_state)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._query("SELECT COUNT(*) AS c FROM drafts" + clause, tuple(params))[0]["c"]
        rows = self._query(
            "SELECT * FROM drafts" + clause + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        records = []
        for row in rows:
            records.append(
                DraftRecord(
                    draft_id=row["draft_id"], platform=row["platform"],
                    account_id=row["account_id"], operator=row["operator"],
                    action=row["action"], content_text=row["content_text"],
                    content_json=row["content_json"],
                    conversation_ref=row["conversation_ref"],
                    source_event_id=row["source_event_id"],
                    provenance_json=row["provenance_json"],
                    risk_score=row["risk_score"], risk_level=row["risk_level"],
                    approval_state=row["approval_state"],
                    content_hash=row["content_hash"],
                    created_at=row["created_at"], updated_at=row["updated_at"],
                )
            )
        return Page(records, int(total), limit, offset)

    def get_draft(self, draft_id: str) -> Optional[DraftRecord]:
        rows = self._query("SELECT * FROM drafts WHERE draft_id = ?", (draft_id,))
        if not rows:
            return None
        row = rows[0]
        return DraftRecord(
            draft_id=row["draft_id"], platform=row["platform"],
            account_id=row["account_id"], operator=row["operator"],
            action=row["action"], content_text=row["content_text"],
            content_json=row["content_json"], conversation_ref=row["conversation_ref"],
            source_event_id=row["source_event_id"],
            provenance_json=row["provenance_json"],
            risk_score=row["risk_score"], risk_level=row["risk_level"],
            approval_state=row["approval_state"], content_hash=row["content_hash"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    # -- approvals ------------------------------------------------------

    def insert_approval(self, record: ApprovalRecord) -> None:
        self._execute(
            "INSERT OR REPLACE INTO approvals (approval_id, payload_json, status, created_at, expires_at, correlation_id) VALUES (?,?,?,?,?,?)",
            (record.approval_id, record.payload_json, record.status,
             record.created_at, record.expires_at, record.correlation_id),
        )

    def list_approvals(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Page:
        where, params = [], []
        if status:
            where.append("status = ?")
            params.append(status)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._query("SELECT COUNT(*) AS c FROM approvals" + clause, tuple(params))[0]["c"]
        rows = self._query(
            "SELECT * FROM approvals" + clause + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        records = [
            ApprovalRecord(
                approval_id=r["approval_id"], payload_json=r["payload_json"],
                status=r["status"], created_at=r["created_at"],
                expires_at=r["expires_at"], correlation_id=r["correlation_id"],
            )
            for r in rows
        ]
        return Page(records, int(total), limit, offset)

    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        rows = self._query("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
        if not rows:
            return None
        r = rows[0]
        return ApprovalRecord(
            approval_id=r["approval_id"], payload_json=r["payload_json"],
            status=r["status"], created_at=r["created_at"],
            expires_at=r["expires_at"], correlation_id=r["correlation_id"],
        )

    # -- decisions ------------------------------------------------------

    def insert_decision(self, record: DecisionRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO decisions (
                decision_id, event_id, council_state, policy_state, risk_level,
                reason, decided_at, correlation_id
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (record.decision_id, record.event_id, record.council_state,
             record.policy_state, record.risk_level, record.reason,
             record.decided_at, record.correlation_id),
        )

    def list_decisions(
        self, event_id: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Page:
        where, params = [], []
        if event_id:
            where.append("event_id = ?")
            params.append(event_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._query("SELECT COUNT(*) AS c FROM decisions" + clause, tuple(params))[0]["c"]
        rows = self._query(
            "SELECT * FROM decisions" + clause + " ORDER BY decided_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        records = [
            DecisionRecord(
                decision_id=r["decision_id"], event_id=r["event_id"],
                council_state=r["council_state"], policy_state=r["policy_state"],
                risk_level=r["risk_level"], reason=r["reason"],
                decided_at=r["decided_at"], correlation_id=r["correlation_id"],
            )
            for r in rows
        ]
        return Page(records, int(total), limit, offset)

    # -- receipts -------------------------------------------------------

    def insert_receipt(self, record: ReceiptRecord) -> None:
        self._execute(
            "INSERT OR REPLACE INTO receipts (receipt_id, payload_json, received_at) VALUES (?,?,?)",
            (record.receipt_id, record.payload_json, record.received_at),
        )

    def list_receipts(
        self, platform: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Page:
        where, params = [], []
        if platform:
            where.append("json_extract(payload_json, '$.platform') = ?")
            params.append(platform)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._query("SELECT COUNT(*) AS c FROM receipts" + clause, tuple(params))[0]["c"]
        rows = self._query(
            "SELECT * FROM receipts" + clause + " ORDER BY received_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        records = [
            ReceiptRecord(receipt_id=r["receipt_id"], payload_json=r["payload_json"],
                          received_at=r["received_at"])
            for r in rows
        ]
        return Page(records, int(total), limit, offset)

    def get_receipt(self, receipt_id: str) -> Optional[ReceiptRecord]:
        rows = self._query("SELECT * FROM receipts WHERE receipt_id = ?", (receipt_id,))
        if not rows:
            return None
        r = rows[0]
        return ReceiptRecord(receipt_id=r["receipt_id"], payload_json=r["payload_json"],
                             received_at=r["received_at"])

    # -- accounts -------------------------------------------------------

    def upsert_account(self, record: AccountRecord) -> None:
        self._execute(
            """
            INSERT INTO accounts (
                account_id, platform, display_name, connector_id,
                permissions_json, status, created_at
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(account_id, platform) DO UPDATE SET
                display_name = excluded.display_name,
                connector_id = excluded.connector_id,
                permissions_json = excluded.permissions_json,
                status = excluded.status,
                created_at = excluded.created_at
            """,
            (record.account_id, record.platform, record.display_name,
             record.connector_id, record.permissions_json, record.status,
             record.created_at),
        )

    def list_accounts(self, platform: Optional[str] = None) -> List[AccountRecord]:
        if platform:
            rows = self._query("SELECT * FROM accounts WHERE platform = ? ORDER BY platform, account_id", (platform,))
        else:
            rows = self._query("SELECT * FROM accounts ORDER BY platform, account_id")
        return [
            AccountRecord(
                account_id=r["account_id"], platform=r["platform"],
                display_name=r["display_name"], connector_id=r["connector_id"],
                permissions_json=r["permissions_json"], status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # -- notifications --------------------------------------------------

    def insert_notification(self, record: NotificationRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO notifications (
                notification_id, event_id, platform, account_id, kind, title,
                body_text, read, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (record.notification_id, record.event_id, record.platform,
             record.account_id, record.kind, record.title, record.body_text,
             record.read, record.created_at),
        )

    def list_notifications(
        self,
        account_id: Optional[str] = None,
        read: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        where, params = [], []
        if account_id:
            where.append("account_id = ?")
            params.append(account_id)
        if read is not None:
            where.append("read = ?")
            params.append(read)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._query("SELECT COUNT(*) AS c FROM notifications" + clause, tuple(params))[0]["c"]
        rows = self._query(
            "SELECT * FROM notifications" + clause + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        records = [
            NotificationRecord(
                notification_id=r["notification_id"], event_id=r["event_id"],
                platform=r["platform"], account_id=r["account_id"],
                kind=r["kind"], title=r["title"], body_text=r["body_text"],
                read=r["read"], created_at=r["created_at"],
            )
            for r in rows
        ]
        return Page(records, int(total), limit, offset)

    def mark_notification_read(self, notification_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE notifications SET read = 1 WHERE notification_id = ?",
                (notification_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    # -- connector state ------------------------------------------------

    def upsert_connector_state(self, record: ConnectorStateRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO connector_states (
                connector_id, platform, status, health_json, manifest_json, last_checked_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (record.connector_id, record.platform, record.status,
             record.health_json, record.manifest_json, record.last_checked_at),
        )

    def list_connector_states(self) -> List[ConnectorStateRecord]:
        rows = self._query("SELECT * FROM connector_states ORDER BY platform, connector_id")
        return [
            ConnectorStateRecord(
                connector_id=r["connector_id"], platform=r["platform"],
                status=r["status"], health_json=r["health_json"],
                manifest_json=r["manifest_json"], last_checked_at=r["last_checked_at"],
            )
            for r in rows
        ]

    # -- counters / analytics ------------------------------------------

    def increment_counter(self, name: str, delta: int = 1) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO counters (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = value + ?",
                (name, delta, delta),
            )
            self._conn.commit()

    def get_counter(self, name: str) -> int:
        rows = self._query("SELECT value FROM counters WHERE key = ?", (name,))
        return int(rows[0]["value"]) if rows else 0

    def counters_snapshot(self) -> dict:
        rows = self._query("SELECT key, value FROM counters ORDER BY key")
        return {r["key"]: int(r["value"]) for r in rows}

    # -- health ---------------------------------------------------------

    def db_health(self) -> bool:
        try:
            rows = self._query("SELECT 1 AS ok")
            return bool(rows) and rows[0]["ok"] == 1
        except Exception:
            return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()
