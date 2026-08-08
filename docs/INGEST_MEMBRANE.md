# HERMES Social Ingest Membrane (B3)

Status: IMPLEMENTED / CONTRACT-TESTED / MOCK-TESTED
Live: BLOCKED (no live credentials authorized; fixture providers only)

This document describes the B3 connector layer and Social Ingest Membrane in
`wiredchaos/HERMES-SOCIAL`. It is the runtime counterpart of the B2 versioned
contracts (`schemas/`, `policies/`).

## Execution path

Every external social event must traverse the membrane:

```
EXTERNAL SOCIAL EVENT
  -> QUARANTINE (size / static / media-type gates)
  -> CONNECTOR VALIDATION (adapter contract + capability-scoped handles)
  -> NORMALIZATION (adapter normalize_event -> pre-schema Social Event)
  -> SANITIZATION (content neutralized BEFORE hashing/validation)
  -> SCHEMA VALIDATION (social-event.schema.json; quarantine exit gate)
  -> PROVENANCE CAPTURE (source_reference required)
  -> CONTENT HASH (sha256 over sanitized content)
  -> DEDUPLICATION (content-hash store)
  -> RISK CLASSIFICATION (risk.py bands; policy/risk-levels.yaml parity)
  -> POLICY EVALUATION (policy.py; council.yaml routing parity)
  -> COUNCIL ROUTING (analyze/draft eligible; escalate/quarantine otherwise)
  -> ELIGIBLE EVENT BUS
```

## Untrusted sensor data rule

External social content is UNTRUSTED SENSOR DATA. It may NOT directly write
to: sovereign memory, RAG, task creation, tool execution, publishing,
credentials, policy, or system instructions.

- Prompt/instruction injection inside social content remains DATA. It is
  sanitized and risk-scored; it never becomes a policy field or an execution
  signal.
- Content is sanitized BEFORE content hashing, schema validation, and publish.
  The event that leaves the membrane carries sanitized content only; raw
  payloads stay in quarantine by construction.
- Credential-like values (token, secret, password, authorization, cookie,
  api_key, ...) are stripped from content and reported as `credential_hits`
  in the model view. They never appear in the bus event or model view.
- `model_view` is always marked `untrusted: True`.

## Connector adapters

| Adapter | connector_id | Permissions | Status |
|---------|--------------|-------------|--------|
| X | conn_x_observe_001 | observe | blocked_live |
| Discord | conn_discord_observe_001 | observe, analyze | blocked_live |
| Farcaster | conn_farcaster_observe_001 | observe | blocked_live |

Execute is default-deny everywhere. `required_secret_handles` are opaque
NAMES only — values live in the sealed secret provider and never enter
manifests, events, logs, or model context.

## Components

- `connectors/base.py` — nine-method Connector contract (initialize,
  health_check, read_events, normalize_event, validate_event,
  checkpoint_cursor, get_checkpoint, handle_rate_limit, revoke, shutdown)
  plus durable checkpoint persistence through an optional CheckpointStore.
- `connectors/errors.py` — typed errors (rate_limited, revoked,
  authentication_failed, provider_timeout, malformed_response,
  permission_denied, provider_unavailable); messages are safe summaries.
- `connectors/manifest.py` — manifest loading + structural/schema validation
  against `schemas/connector-manifest.schema.json`.
- `connectors/registry.py` — connector registry (register/get/has/manifest/
  ids/health_snapshot/revoke); never holds raw credentials.
- `connectors/fixtures/fixture_providers.py` — deterministic mock provider
  (normal | rate_limited | timeout | auth_failure | malformed |
  revoked_signal) + pagination (`fetch_page` returns events + next_cursor)
  + the FixtureConnector base.
- `connectors/checkpoint.py` — file-backed, atomic (temp + rename) cursor
  store for durable checkpoint persistence.
- `connectors/providers/*.py` — X, Discord, Farcaster adapters (mock-only).
- `membrane/pipeline.py` — IngestMembrane orchestrator (the path above).
- `membrane/quarantine.py` — entry gates (payload size, media types, static
  JSON).
- `membrane/dedup.py` — content-hash dedup store.
- `membrane/risk.py` — deterministic risk scoring (bands mirror
  policies/risk-levels.yaml).
- `membrane/sanitize.py` — content sanitization (HTML strip, truncation,
  URL capture, credential-key removal, javascript: URL warnings).
- `membrane/policy.py` — policy evaluation + council routing (mirrors
  policies/council.yaml).
- `membrane/bus.py` — EligibleEventBus (only released events).
- `membrane/metrics.py` — thermodynamic observability counters/rates with NO
  payload exposure.

## Pagination and checkpoints

`FixtureProvider.fetch_page(checkpoint, page_size)` returns
`(events, next_cursor)`; `FixtureConnector.read_page(page_size)` persists the
advancing cursor through the CheckpointStore so a resumed connector starts
after the last returned event. Cursor semantics mirror real provider APIs
(no duplicate replay in the fixture).

## Observability

`membrane/metrics.py` maintains (counts + derived rates): event backlog,
quarantine rate, validation failure rate, duplicate rate, connector failure
rate, retry pressure, rate-limit pressure, policy-denial rate, approval
latency (samples/avg), schema drift, connector drift, dead-letter volume,
manual intervention frequency. Metrics contain counters only — never event
content, provenance, or credential material.

## Adversarial coverage (tests/test_membrane.py)

prompt injection, instruction injection, malformed JSON, unknown schema
version, oversized payload, duplicate event, missing provenance, malicious
URL, HTML/script payload, unsupported media, provider timeout, rate limit,
authentication failure, revoked connector, replayed event, credential-like
content, unexpected fields, invalid content hashes.

## Verification

```bash
uv run --with jsonschema --with pyyaml python -m unittest discover -s tests -v
python scripts/verify-contracts.py
```

## HERMES Bridge

hermes-bridge (HERMES-CITY) is NOT part of the controlled B3 pilot path and
remains NOT TESTED on production branches (see production ledger).

## Rollback

Revert the B3 PR; no live credentials, publishing, or infrastructure are
touched by this lane. Live status remains BLOCKED until a separate human
authorization supplies credentials and re-enables provider connectivity.
