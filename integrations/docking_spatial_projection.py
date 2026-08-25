"""Public-safe Docking District spatial projection.

This module converts already-normalized/governed Social Events into the minimum
state HERMES-CITY needs to animate agent presence. It intentionally drops raw
content, media, credentials, private metadata, and unreviewed provider payloads.
"""
from datetime import datetime, timezone

ALLOWED_SPACES = {
    "arrival_gate", "identity_customs", "quarantine_bay", "passport_hall",
    "social_commons", "berth_exchange", "dispatch_concourse",
    "observation_gallery", "audit_terminal", "return_gate",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _space_for(event):
    policy = event.get("policy_state", "unreviewed")
    quarantine = event.get("quarantine_state", "received")
    council = event.get("council_state", "pending")
    validation = event.get("validation_state", "unvalidated")

    if quarantine in {"quarantined", "rejected", "dead_letter"} or policy == "blocked":
        return "quarantine_bay", "blocked", "blocked"
    if validation != "valid" or policy in {"unreviewed", "escalated"}:
        return "identity_customs", "reviewing", "review"
    if council in {"draft", "analyze", "pending"}:
        return "social_commons", "meeting", "allowed"
    if council in {"approve", "execute"}:
        return "dispatch_concourse", "moving", "allowed"
    if council == "reject":
        return "quarantine_bay", "blocked", "blocked"
    return "passport_hall", "idle", "allowed"


def project_social_event(event, truth_state="LIVE"):
    """Return a public-safe spatial event from a governed Social Event."""
    if not isinstance(event, dict):
        raise TypeError("event must be a dict")

    event_id = str(event.get("event_id") or "")
    if not event_id:
        raise ValueError("event_id required")

    author = event.get("author") or {}
    agent_id = str(author.get("id") or event.get("account_id") or "")
    if not agent_id:
        raise ValueError("author.id or account_id required")

    space, activity, policy_state = _space_for(event)
    if space not in ALLOWED_SPACES:
        raise ValueError("invalid projected space")

    platform = str(event.get("platform") or "EXTERNAL").upper()
    timestamp = event.get("source_timestamp") or event.get("received_at") or _now_iso()
    receipt_id = event.get("receipt_id")

    return {
        "schema_version": "1.0.0",
        "event_id": "spatial:%s" % event_id,
        "agent_id": agent_id,
        "district": "docking",
        "space": space,
        "activity": activity,
        "origin": platform[:32],
        "policy_state": policy_state,
        "truth_state": truth_state,
        "timestamp": timestamp,
        "source_event_id": event_id,
        "receipt_id": str(receipt_id) if receipt_id else None,
        "public_label": "%s -> %s" % (agent_id, space.replace("_", " ")),
    }


def project_events(events, truth_state="LIVE"):
    """Project a sequence while failing closed on malformed items."""
    projected = []
    for event in events or []:
        try:
            projected.append(project_social_event(event, truth_state=truth_state))
        except (TypeError, ValueError):
            continue
    return projected
