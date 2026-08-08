"""Membrane observability metrics (B3).

Thermodynamic observability without exposing payloads: every metric is a
counter or derived ratio over counters. No event content, provenance, or
credential material ever enters the metrics — only counts and rates.

Tracks (mandate list):
  event backlog, quarantine rate, validation failure rate, duplicate rate,
  connector failure rate, retry pressure, rate-limit pressure,
  policy-denial rate, approval latency, schema drift, connector drift,
  dead-letter volume, manual intervention frequency.
"""
import datetime


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MembraneMetrics:
    """In-memory counters + derived rates. Deterministic; no payload data."""

    _COUNTERS = (
        "received",
        "released",
        "quarantined",
        "rejected",
        "duplicate",
        "validation_failures",
        "connector_failures",
        "rate_limit_hits",
        "policy_denials",
        "retry_pressure",
        "dead_letter",
        "manual_interventions",
        "schema_drift_events",
        "connector_drift_events",
    )

    def __init__(self):
        self._counts = {name: 0 for name in self._COUNTERS}
        self._bus_backlog = 0
        self._approval_latency_total_ms = 0
        self._approval_latency_samples = 0
        self._started_at = _utcnow()

    def inc(self, name, amount=1):
        if name in self._counts:
            self._counts[name] += amount

    def record_bus_backlog(self, count):
        self._bus_backlog = count

    def record_approval_latency_ms(self, ms):
        self._approval_latency_total_ms += ms
        self._approval_latency_samples += 1

    def _rate(self, numerator, denominator):
        if not denominator:
            return 0.0
        return round(numerator / float(denominator), 4)

    def snapshot(self):
        counts = dict(self._counts)
        received = counts["received"]
        quarantined = counts["quarantined"]
        released = counts["released"]
        rejected = counts["rejected"]
        duplicate = counts["duplicate"]
        approved = self._approval_latency_samples
        return {
            "started_at": self._started_at,
            "snapshot_at": _utcnow(),
            "counts": counts,
            "backlog": {
                "event_backlog": self._bus_backlog,
                "dead_letter_volume": counts["dead_letter"],
            },
            "rates": {
                "quarantine_rate": self._rate(quarantined, received),
                "validation_failure_rate": self._rate(counts["validation_failures"], received),
                "duplicate_rate": self._rate(duplicate, received),
                "connector_failure_rate": self._rate(counts["connector_failures"], received),
                "rate_limit_pressure": self._rate(counts["rate_limit_hits"], received),
                "policy_denial_rate": self._rate(counts["policy_denials"], received),
                "retry_pressure": counts["retry_pressure"],
                "manual_intervention_frequency": counts["manual_interventions"],
            },
            "drift": {
                "schema_drift": counts["schema_drift_events"],
                "connector_drift": counts["connector_drift_events"],
            },
            "latency": {
                "approval_latency_samples": approved,
                "approval_latency_avg_ms": (
                    round(self._approval_latency_total_ms / approved, 2) if approved else None
                ),
            },
        }
