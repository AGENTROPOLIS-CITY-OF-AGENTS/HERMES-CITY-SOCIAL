"""AGENTROPOLIS Social Transit Grid — B4 governed HERMES Social Surface.

The operator/read-model surface above the B3 Ingest Membrane. B4 consumes
ONLY governed, sanitized B2/B3 outputs (released Social Events, approval
requests, action receipts, council decisions). It never reads raw quarantined
platform payloads.

Live social credentials are NOT authorized in this release.
"""
__version__ = "0.4.0"
LIVE_STATUS = "LIVE=BLOCKED"
PRODUCTION_APPROVED = "PRODUCTION-APPROVED=NO"
