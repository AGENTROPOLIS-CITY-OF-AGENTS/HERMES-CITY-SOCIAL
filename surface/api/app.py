"""B4 Social Surface — FastAPI application (versioned /api/v1).

Read-model API for the governed HERMES Social Surface. The ONLY write
endpoint is draft creation (POST /api/v1/drafts), which creates an internal
governed artifact and an approval-request record. There is no publish,
execute, send, or moderate endpoint anywhere in B4.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query

from .. import __version__
from ..repositories.base import SurfaceRepository
from ..repositories.sqlite import SQLiteSurfaceRepository
from ..services.surface import SurfaceService
from . import schemas


def _paginate(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> tuple:
    return limit, offset


def create_app(
    repo: Optional[SurfaceRepository] = None,
    registry=None,
    service: Optional[SurfaceService] = None,
) -> FastAPI:
    """Build the B4 surface API.

    repo: inject a SurfaceRepository (defaults to in-memory SQLite).
    registry: B3 pilot connector registry; when given, seed accounts and
              connector states from real connector manifests.
    service: inject a SurfaceService (defaults to repo-bound service).
    """
    if repo is None:
        repo = SQLiteSurfaceRepository(":memory:")
    if service is None:
        service = SurfaceService(repo)
    if registry is not None:
        service.seed_pilot(registry)

    app = FastAPI(
        title="HERMES Social Surface (B4)",
        version=__version__,
        description="Governed read-model surface above the B3 Social Ingest Membrane. LIVE=BLOCKED; no publish path.",
    )
    app.state.surface_repo = repo
    app.state.surface_service = service

    def get_service() -> SurfaceService:
        return app.state.surface_service

    # -- system health ---------------------------------------------------

    @app.get("/api/v1/health", response_model=schemas.HealthOut, tags=["system"])
    def health() -> Dict[str, Any]:
        return get_service().health()

    # -- events ----------------------------------------------------------

    @app.get("/api/v1/events", response_model=schemas.DataResponse[schemas.EventOut], tags=["events"])
    def list_events(
        platform: Optional[str] = Query(None, pattern="^(x|discord|farcaster)$"),
        risk_level: Optional[str] = Query(None, pattern="^(low|moderate|high|critical)$"),
        council_state: Optional[str] = Query(None, pattern="^(analyze|draft)$"),
        account_id: Optional[str] = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_events(
            platform=platform, risk_level=risk_level,
            council_state=council_state, account_id=account_id,
            limit=limit, offset=offset,
        )

    @app.get("/api/v1/events/{event_id}", response_model=schemas.EventOut, tags=["events"])
    def get_event(event_id: str) -> Dict[str, Any]:
        view = get_service().get_event(event_id)
        if view is None:
            raise HTTPException(status_code=404, detail="event not found")
        return view

    # -- inbox / feeds ---------------------------------------------------

    @app.get("/api/v1/inbox", response_model=schemas.DataResponse[schemas.InboxItemOut], tags=["inbox"])
    def list_inbox(
        platform: Optional[str] = Query(None, pattern="^(x|discord|farcaster)$"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_inbox(platform=platform, limit=limit, offset=offset)

    @app.get("/api/v1/feeds", response_model=schemas.DataResponse[schemas.FeedItemOut], tags=["feeds"])
    def list_feeds(
        platform: Optional[str] = Query(None, pattern="^(x|discord|farcaster)$"),
        conversation_id: Optional[str] = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_feed(
            platform=platform, conversation_id=conversation_id,
            limit=limit, offset=offset,
        )

    # -- notifications ---------------------------------------------------

    @app.get("/api/v1/notifications", response_model=schemas.DataResponse[schemas.NotificationOut], tags=["notifications"])
    def list_notifications(
        account_id: Optional[str] = None,
        read: Optional[bool] = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_notifications(
            account_id=account_id, read=read, limit=limit, offset=offset,
        )

    @app.post("/api/v1/notifications/{notification_id}/read", tags=["notifications"])
    def mark_notification_read(notification_id: str) -> Dict[str, Any]:
        ok = get_service().mark_notification_read(notification_id)
        if not ok:
            raise HTTPException(status_code=404, detail="notification not found")
        return {"ok": True, "notification_id": notification_id}

    # -- accounts / connectors -------------------------------------------

    @app.get("/api/v1/accounts", response_model=schemas.DataResponse[schemas.AccountOut], tags=["accounts"])
    def list_accounts(
        platform: Optional[str] = Query(None, pattern="^(x|discord|farcaster)$"),
    ) -> Dict[str, Any]:
        return get_service().list_accounts(platform=platform)

    @app.get("/api/v1/connectors", response_model=schemas.DataResponse[schemas.ConnectorOut], tags=["connectors"])
    def list_connectors() -> Dict[str, Any]:
        return get_service().list_connectors()

    # -- drafts (governed artifact; never publishes) ---------------------

    @app.post("/api/v1/drafts", response_model=schemas.DraftOut, status_code=201, tags=["drafts"])
    def create_draft(payload: schemas.DraftCreateIn) -> Dict[str, Any]:
        try:
            return get_service().create_draft(
                platform=payload.platform,
                account_id=payload.account_id,
                operator=payload.operator,
                action=payload.action,
                content=payload.content,
                conversation_ref=payload.conversation_ref,
                source_event_id=payload.source_event_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/drafts", response_model=schemas.DataResponse[schemas.DraftOut], tags=["drafts"])
    def list_drafts(
        platform: Optional[str] = Query(None, pattern="^(x|discord|farcaster)$"),
        approval_state: Optional[str] = Query(None, pattern="^(pending|approved|rejected|expired|revised|cancelled)$"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_drafts(
            platform=platform, approval_state=approval_state, limit=limit, offset=offset,
        )

    @app.get("/api/v1/drafts/{draft_id}", response_model=schemas.DraftOut, tags=["drafts"])
    def get_draft(draft_id: str) -> Dict[str, Any]:
        view = get_service().get_draft(draft_id)
        if view is None:
            raise HTTPException(status_code=404, detail="draft not found")
        return view

    # -- approval queue --------------------------------------------------

    @app.get("/api/v1/approvals", response_model=schemas.DataResponse[schemas.ApprovalOut], tags=["approvals"])
    def list_approvals(
        status: Optional[str] = Query(None, pattern="^(pending|approved|rejected|expired|revised|cancelled)$"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_approvals(status=status, limit=limit, offset=offset)

    @app.get("/api/v1/approvals/{approval_id}", response_model=schemas.ApprovalOut, tags=["approvals"])
    def get_approval(approval_id: str) -> Dict[str, Any]:
        view = get_service().get_approval(approval_id)
        if view is None:
            raise HTTPException(status_code=404, detail="approval not found")
        return view

    # -- council decisions -----------------------------------------------

    @app.get("/api/v1/council", response_model=schemas.DataResponse[schemas.DecisionOut], tags=["council"])
    def list_decisions(
        event_id: Optional[str] = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_decisions(event_id=event_id, limit=limit, offset=offset)

    # -- receipts --------------------------------------------------------

    @app.get("/api/v1/receipts", response_model=schemas.DataResponse[schemas.ReceiptOut], tags=["receipts"])
    def list_receipts(
        platform: Optional[str] = Query(None, pattern="^(x|discord|farcaster)$"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        return get_service().list_receipts(platform=platform, limit=limit, offset=offset)

    @app.get("/api/v1/receipts/{receipt_id}", response_model=schemas.ReceiptOut, tags=["receipts"])
    def get_receipt(receipt_id: str) -> Dict[str, Any]:
        view = get_service().get_receipt(receipt_id)
        if view is None:
            raise HTTPException(status_code=404, detail="receipt not found")
        return view

    # -- analytics -------------------------------------------------------

    @app.get("/api/v1/analytics", response_model=schemas.AnalyticsOut, tags=["analytics"])
    def analytics() -> Dict[str, Any]:
        return get_service().analytics()

    return app
