"""Ingest Membrane pipeline orchestrator (B3).

External event -> quarantine -> normalize -> schema validation -> provenance
capture -> content hash -> deduplication -> risk classification ->
sanitization -> policy evaluation -> council routing -> eligible event bus.

Raw external payloads never enter model-facing representations. Every state
transition is recorded on the result for audit.
"""
import datetime as _dt
import hashlib
import json
import os
import uuid

from .bus import EligibleEventBus
from .dedup import DedupStore, content_hash
from .metrics import MembraneMetrics
from .policy import ELIGIBLE_COUNCIL_STATES, evaluate_policy
from .quarantine import (
    QuarantineError,
    check_media_types,
    check_size,
    check_static,
)
from .risk import score_content, level_for_score
from . import sanitize as _sanitize

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.normpath(os.path.join(HERE, "..", "schemas"))
SOCIAL_EVENT_SCHEMA = os.path.join(SCHEMAS_DIR, "social-event.schema.json")


class MembraneResult:
    def __init__(self, outcome, reason="", transitions=None, event=None, model_view=None):
        self.outcome = outcome  # released | quarantined | rejected | duplicate
        self.reason = reason
        self.transitions = transitions or []
        self.event = event
        self.model_view = model_view

    def __repr__(self):
        return "<MembraneResult %s: %s>" % (self.outcome, self.reason)


def _utcnow():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload_len(payload_bytes):
    """Byte length of a raw payload (bytes/str) or an int length."""
    if payload_bytes is None:
        return 0
    if isinstance(payload_bytes, (bytes, bytearray)):
        return len(payload_bytes)
    if isinstance(payload_bytes, str):
        return len(payload_bytes.encode("utf-8"))
    return int(payload_bytes)


class IngestMembrane:
    def __init__(self, validator_factory=None, dedup_store=None, bus=None,
                 council_routing=None, now=None, metrics=None):
        """validator_factory: callable(schema_dict) -> jsonschema validator."""
        self.validator_factory = validator_factory
        self.dedup = dedup_store or DedupStore()
        self.bus = bus or EligibleEventBus()
        self.council_routing = council_routing
        self.now = now or _utcnow
        self.metrics = metrics or MembraneMetrics()
        self._schema = None

    def _load_schema(self):
        if self._schema is None:
            with open(SOCIAL_EVENT_SCHEMA, encoding="utf-8") as fh:
                self._schema = json.load(fh)
        return self._schema

    def _record(self, transitions, step, state):
        transitions.append({"step": step, "state": state})

    def run(self, connector, raw_event, payload_bytes=None, pre_normalized=None):
        """Run the membrane on a raw provider event.

        pre_normalized: an already-normalized Social Event shape (used by
        schema/provenance-level adversarial tests).
        """
        transitions = []
        self.metrics.inc("received")
        try:
            self._record(transitions, "receive", "received")
            check_size(payload_bytes)
            self._record(transitions, "quarantine_size", "ok")

            if pre_normalized is not None:
                event = dict(pre_normalized)
            else:
                event = connector.normalize_event(raw_event)
            self._record(transitions, "provider_normalization", "ok")

            check_static(payload_bytes)
            self._record(transitions, "static_validation", "ok")

            # media type gate
            check_media_types(event.get("media", []))
            self._record(transitions, "type_validation", "ok")

            # sanitization happens BEFORE hashing/validation/publish so the
            # event that leaves the membrane never carries raw untrusted
            # content (credential-like values, HTML, injection text). The
            # content hash binds the SANITIZED bytes; raw payloads stay in
            # quarantine by construction.
            sanitized, warnings, links, creds = _sanitize.sanitize_content(event.get("content", {}))
            event["content"] = sanitized
            self._record(transitions, "sanitization", "contained")

            # pipeline-assigned fields
            event.setdefault("received_at", self.now())
            event.setdefault("correlation_id", "corr_%s" % uuid.uuid4().hex[:12])
            event["content_hash"] = content_hash(event.get("content", {}))
            event["risk_score"] = score_content(
                event.get("content", {}),
                invalid_media=False,
                oversized=_payload_len(payload_bytes) > 200_000,
            )
            event["risk_level"] = level_for_score(event["risk_score"])
            if creds:
                event["risk_score"] = min(100, event["risk_score"] + 30)
                event["risk_level"] = level_for_score(event["risk_score"])
            event["memory_eligibility"] = "eligible" if event["risk_level"] in ("low", "moderate") else "review_required"
            event["retention_class"] = "standard" if event["risk_level"] != "critical" else "sensitive"
            event["validation_state"] = "valid"
            event["quarantine_state"] = "quarantined"
            event["policy_state"] = "unreviewed"
            event["council_state"] = "pending"

            # schema validation (quarantine exit gate)
            if self.validator_factory is not None:
                schema = self._load_schema()
                validator = self.validator_factory(schema)
                errs = sorted(validator.iter_errors(event), key=lambda e: str(e.path))
                if errs:
                    version = event.get("schema_version")
                    if version and version != "1.0.0":
                        event["validation_state"] = "held_for_migration"
                        self.metrics.inc("validation_failures")
                        self.metrics.inc("schema_drift_events")
                        self.metrics.inc("dead_letter")
                        self._record(transitions, "schema_validation", "held_for_migration")
                        return MembraneResult("quarantined", "unknown schema version: %s" % version,
                                              transitions, event, None)
                    self.metrics.inc("validation_failures")
                    self.metrics.inc("rejected")
                    self._record(transitions, "schema_validation", "invalid")
                    return MembraneResult("rejected", "; ".join(e.message for e in errs[:3]),
                                          transitions, event, None)
                self._record(transitions, "schema_validation", "valid")

            # provenance capture
            prov = event.get("provenance") or {}
            src = prov.get("source_reference") or ""
            if not src or src.endswith(("/", ":")):
                self.metrics.inc("dead_letter")
                self.metrics.inc("rejected")
                self._record(transitions, "provenance", "missing")
                return MembraneResult("rejected", "missing provenance", transitions, event, None)
            self._record(transitions, "provenance", "captured")

            # deduplication
            digest = event["content_hash"]
            if self.dedup.seen(digest):
                self.metrics.inc("duplicate")
                self._record(transitions, "deduplication", "duplicate")
                return MembraneResult("duplicate", "duplicate content hash", transitions, event, None)
            self.dedup.record(digest, event.get("event_id", ""))
            self._record(transitions, "deduplication", "unique")

            # risk classification
            self._record(transitions, "risk_classification", event["risk_level"])

            # model view (raw payload excluded by construction — content was
            # already sanitized before hashing/validation)
            model_view = {
                "content": event["content"],
                "provenance": {
                    "connector_id": event.get("connector_id"),
                    "platform": event.get("platform"),
                    "source_reference": prov.get("source_reference"),
                    "retrieved_at": prov.get("retrieved_at"),
                },
                "risk": {"score": event["risk_score"], "level": event["risk_level"]},
                "untrusted": True,
                "warnings": warnings,
                "links": links,
                "credential_hits": creds,
            }
            self._record(transitions, "model_view", "contained")

            # policy evaluation + council routing
            policy_state, council_state, reasons = evaluate_policy(event, self.council_routing)
            event["policy_state"] = policy_state
            event["council_state"] = council_state
            if policy_state in ("blocked", "restricted"):
                self.metrics.inc("policy_denials")
            self._record(transitions, "policy_evaluation", policy_state)
            self._record(transitions, "council_routing", council_state)

            if council_state in ELIGIBLE_COUNCIL_STATES and policy_state == "allowed":
                event["quarantine_state"] = "released"
                self.bus.publish(event)
                self.metrics.inc("released")
                self.metrics.record_bus_backlog(len(self.bus))
                self._record(transitions, "event_bus", "published")
                return MembraneResult("released", "released to eligible bus", transitions, event, model_view)

            event["quarantine_state"] = "released"
            self.metrics.inc("quarantined")
            self._record(transitions, "event_bus", "not_eligible")
            return MembraneResult("quarantined", "council_state=%s policy_state=%s" % (council_state, policy_state),
                                  transitions, event, model_view)

        except QuarantineError as exc:
            self.metrics.inc("quarantined")
            self.metrics.inc("validation_failures")
            self._record(transitions, "quarantine", "rejected")
            return MembraneResult("quarantined", str(exc), transitions, None, None)
