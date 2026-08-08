"""Policy evaluation and council routing (B3).

Defaults mirror policies/council.yaml routing_defaults; the policy test suite
asserts they match (single source of truth).
"""

COUNCIL_OUTCOMES = {
    "ignore", "analyze", "draft", "escalate", "approve", "execute", "reject", "quarantine",
}

DEFAULT_ROUTING = {
    "low": "analyze",
    "moderate": "draft",
    "high": "escalate",
    "critical": "quarantine",
}

ELIGIBLE_COUNCIL_STATES = {"analyze", "draft"}


def evaluate_policy(event, council_routing=None):
    """Return (policy_state, council_state, reasons)."""
    routing = dict(DEFAULT_ROUTING)
    if council_routing:
        routing.update(council_routing)

    reasons = []
    risk_level = event.get("risk_level", "low")
    permissions = event.get("permissions", {})

    if not permissions.get("observe"):
        return "blocked", "quarantine", ["observe permission missing"]

    if event.get("validation_state") == "held_for_migration":
        return "restricted", "quarantine", ["unknown schema version"]

    if risk_level == "critical":
        return "blocked", "quarantine", ["critical risk"]

    if risk_level == "high":
        return "restricted", "escalate", ["high risk routed to escalation"]

    council_state = routing.get(risk_level, "analyze")
    if council_state == "execute":
        # Execute is default-deny in the pilot; never auto-route.
        council_state = "escalate"
        reasons.append("execute outcome downgraded to escalate (pilot deny)")
    if council_state == "draft":
        reasons.append("draft requires human approval queue")
    return "allowed", council_state, reasons
