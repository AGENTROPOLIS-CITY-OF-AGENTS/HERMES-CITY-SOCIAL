# B4 — Governed HERMES Social Surface

Status: **IMPLEMENTED — fixture/mock only** · Live: **LIVE=BLOCKED** ·
Production: **PRODUCTION-APPROVED=NO**

B4 is the operator/read-model surface above the B3 Social Ingest Membrane.
It turns governed, sanitized B2/B3 outputs into the read models an operator
needs: a unified inbox, feeds, notifications, accounts, connector state,
drafts, an approval queue, council decisions, permanent action receipts, and
system/ingest health.

B4 is **not** a new ingest path. It never consumes raw quarantined platform
payloads; it only ever reads outputs that already passed the B3 membrane.

---

## 1. Architecture

```
external platform
  → connector (B3, fixture/mock, blocked_live)
  → quarantine (B3: size / static / media gates)
  → sanitize (B3: HTML strip, credential-key strip, untrusted marker)
  → normalize (B3 adapter)
  → provenance capture (B3)
  → risk / policy / council eligibility (B3)
  → released Social Event (schema social-event v1.0.0)
  → B4 Social Surface (surface/)
        ├── api/           FastAPI app, /api/v1 routes, pydantic schemas
        ├── services/      SurfaceService — governed ingest gate + read models
        ├── repositories/  SurfaceRepository ABC + SQLiteSurfaceRepository
        ├── models/        persisted record dataclasses (contract-shaped)
        └── views/         API-safe serializers (recursive credential scrub)
```

The surface package is dependency-light: `models/`, `repositories/`,
`services/`, and `views/` use only the Python standard library plus the
existing B3 membrane modules (`membrane.sanitize`, `membrane.risk`,
`membrane.dedup`). Only `surface/api/` requires FastAPI/pydantic.

## 2. Data flow

1. A B3 connector reads fixture (mock) events and normalizes them.
2. `membrane.pipeline.IngestMembrane.run()` applies quarantine checks,
   sanitization, schema validation, provenance capture, deduplication, risk
   classification, and policy/council evaluation.
3. Only `released` outcomes (validation_state=valid, quarantine_state=
   released, policy_state=allowed, council_state in analyze|draft) are handed
   to the surface via `SurfaceService.ingest_from_membrane()`.
4. Every other membrane outcome (quarantined / rejected / duplicate) is
   **counter-only**: it increments operational metrics and is never stored as
   a visible read model.
5. The surface also enforces its own ingest gate (`ingest_released_event`)
   and re-scrubs every view through `surface/views/serializers.scrub()`.

The canary (`scripts/canary-b4.py`, `tests/test_surface_canary.py`) runs the
real B3 pipeline over the real pilot fixture connectors (X, Discord,
Farcaster) and proves released events become visible in B4 while a
quarantined event never appears in the operator feed.

## 3. API

Versioned endpoints under `/api/v1`. All list endpoints return
`{"data": [...], "meta": {"total", "limit", "offset"}}` and support
`limit` (1-200, default 50) and `offset` pagination.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | system health, live status, connector states, counters |
| GET | `/api/v1/events` | released Social Events (filters: platform, risk_level, council_state, account_id) |
| GET | `/api/v1/events/{event_id}` | one event |
| GET | `/api/v1/inbox` | unified inbox (optional platform tab) |
| GET | `/api/v1/feeds` | feed items (optional platform, conversation_id) |
| GET | `/api/v1/notifications` | operator notifications (account_id, read filters) |
| POST | `/api/v1/notifications/{id}/read` | mark one notification read |
| GET | `/api/v1/accounts` | governed accounts (platform filter) |
| GET | `/api/v1/connectors` | connector state + manifests (blocked_live) |
| POST | `/api/v1/drafts` | **only write endpoint** — create governed draft |
| GET | `/api/v1/drafts` | drafts (platform, approval_state filters) |
| GET | `/api/v1/drafts/{draft_id}` | one draft |
| GET | `/api/v1/approvals` | approval queue from the approval-request contract |
| GET | `/api/v1/approvals/{approval_id}` | one approval request |
| GET | `/api/v1/council` | council decisions (event_id filter) |
| GET | `/api/v1/receipts` | permanent action receipts (platform filter) |
| GET | `/api/v1/receipts/{receipt_id}` | one receipt |
| GET | `/api/v1/analytics` | operational read-model analytics |

**No publish, send, moderate, or execute endpoint exists in B4.** The health
response exposes `publish_endpoints: []` and `execute_available: false` as a
machine-checkable assertion of that invariant.

### Draft creation

`POST /api/v1/drafts` accepts:

```json
{
  "platform": "x",
  "account_id": "acct_hermes_public",
  "operator": "op-1",
  "action": "draft_post",
  "content": {"text": "governed draft body"},
  "conversation_ref": "conv-991",
  "source_event_id": "x:tweet-2001"
}
```

`action` is `draft_post` or `draft_reply`. The service sanitizes content via
the B3 sanitizer, hashes it, risk-scores it, stores the draft with
`approval_state=pending`, and creates an approval-request record
(`requested_action=approve_draft`, `required_approvers=[human_operator]`,
`approval_policy=draft_gate`) for the queue. Creating a draft **never**
triggers publication; there is no code path that publishes.

## 4. Repository abstraction

`surface/repositories/base.py` defines `SurfaceRepository`, the storage
contract used by every service method. `SQLiteSurfaceRepository`
(`surface/repositories/sqlite.py`) implements it with the standard-library
`sqlite3` module and is the development backend.

Staging/production can swap in a PostgreSQL implementation of the same
interface without rewriting surface logic. No application logic is
hard-wired to SQLite — services depend only on the ABC.

Tables: `events`, `drafts`, `approvals`, `decisions`, `receipts`, `accounts`
(composite key `(account_id, platform)`), `notifications`,
`connector_states`, `counters`.

## 5. Security boundary

Non-negotiable properties enforced by code + tests:

- **External social content remains untrusted sensor data.** Every event
  carries B3's sanitized content; views mark nothing from content as policy.
- **No raw connector payload bypass.** The surface ingest gate rejects any
  event that is not `valid` / `released` / `allowed` / `analyze|draft`.
- **No raw credentials in model/UI state.** B3 strips credential keys before
  hashing; the surface view layer re-scrubs recursively at any depth
  (`CREDENTIAL_KEYS` mirror). Tests assert credential-shaped values never
  appear in any API response.
- **No tokens/passwords/cookies in logs.** gitleaks scans full history; the
  .gitleaks.toml allowlist is narrowed to the tests/ path only for
  secret-shaped fixture values.
- **Capability handles only.** Connector manifests carry opaque
  `required_secret_handles` names; values live only in a sealed secret
  provider that does not exist in this repo.
- **Execute remains default-deny.** council.yaml `pilot.execute_enabled:
  false`; no connector grants execute; the membrane downgrades any execute
  outcome to escalate; B4 exposes no execute route.
- **Approval gates remain authoritative.** Draft approval state comes from
  the approval-request contract; the queue renders contract data.
- **Platform permissions remain separate.** Accounts are keyed by
  `(account_id, platform)`; permission sets come from connector manifests.
- **Permanent receipts remain required.** Receipts are stored as
  action-receipt contract objects; no action is claimed completed unless a
  completed/confirmed receipt exists (fixture receipts are `mocked`).
- **No direct write into sovereign memory.** B4 writes only its own read
  model; memory_eligibility is metadata, not a memory write.
- **No bypass of ASBE/policy/council controls.** The surface consumes only
  post-membrane outputs; quarantine/reject/duplicate outcomes are counters.

## 6. UI integration contract

The Social Surface is a clean composable module: a FastAPI app factory
(`surface.api.create_app(repo=None, registry=None, service=None)`) and a
service object. A UI consumes the JSON contract in section 3 — nothing else.
Rendering rules for missing data: analytics returns
`{"state": "NO_DATA" | "AVAILABLE", "metrics": {...}}`; empty lists return
`data: []` with `total: 0`; absent connectors return empty connector lists.
UI must display `UNAVAILABLE` / `NO DATA` / `NOT CONNECTED` from these real
values — never fabricated dashboards.

## 7. Hermes Desktop integration

The surface maps to the RIGHT Social Surface pane of the HERMES Desktop:

- platform tabs        → `platform` filter on `/api/v1/inbox` + `/api/v1/feeds`
- unified inbox        → `/api/v1/inbox`
- feeds                → `/api/v1/feeds`
- notifications        → `/api/v1/notifications` + read toggle
- analytics            → `/api/v1/analytics`
- composer             → `POST /api/v1/drafts` (draft post / draft reply)
- drafts               → `/api/v1/drafts`
- approval queue       → `/api/v1/approvals`

LEFT (sessions/agents/skills/artifacts/memory) and CENTER
(conversation/council/research/drafting/execution) remain owned by the Hermes
runtime; B4 exposes only the right-side read models and never reaches into
sessions, memory, or skill state.

## 8. Cyber TUI integration

The AGENTROPOLIS Cyber TUI can mount the surface as a docked panel: call the
same `/api/v1` JSON endpoints over the local API and render the read models
in the TUI's layout. The surface has no UI of its own; it is intentionally
UI-agnostic. A TUI widget would bind `create_app()` to a SQLite file or
shared repo handle.

## 9. Limitations

- SQLite is the dev backend; PostgreSQL adapter is not yet implemented.
- Connectors are fixture/mock only — live provider verification is BLOCKED
  (no credentials authorized).
- Analytics are operational read-model metrics computed from real stored
  data; no event-sourcing projections, no time-series retention.
- No authentication/authorization layer on the API (local/trusted deployment
  only in the pilot).
- Notifications are derived from released events only; no push delivery.
- Draft approval transitions (approve/reject) are not yet exposed as write
  endpoints — the queue is read-only in B4.

## 10. Live status

- **LIVE=BLOCKED** — no live social credentials; all connectors report
  `status: blocked_live` and exercise fixture providers.
- **PRODUCTION-APPROVED=NO** — no production approval has been granted.
- Canary (`scripts/canary-b4.py`) is fixture-based and requires no live
  credentials.

## 11. Verification

```bash
python scripts/verify-contracts.py                      # full gate (syntax + tests + gitleaks + diff)
uv run --with jsonschema --with pyyaml --with fastapi --with httpx \
    python -m unittest discover -s tests -v             # complete suite (B2 + B3 + B4)
uv run --with jsonschema --with pyyaml --with fastapi --with httpx \
    python scripts/canary-b4.py                         # B3 pipeline -> B4 canary
```
