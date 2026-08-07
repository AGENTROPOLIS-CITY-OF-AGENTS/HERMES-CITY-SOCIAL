"""Social Ingest Membrane (B3).

External event -> quarantine -> normalize -> schema validation -> provenance
-> content hash -> deduplication -> risk classification -> sanitization ->
policy evaluation -> council routing -> eligible event bus.

External content is UNTRUSTED SENSOR DATA. Raw provider payloads never enter
model-facing representations; the membrane emits a sanitized, provenance-linked
model_view instead.
"""
