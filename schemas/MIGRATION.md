# Schema Migration Rules

Versioning and evolution rules for the AGENTROPOLIS contracts in `schemas/`.

## Version identity

- Every schema has a stable canonical `$id`: `https://agentropolis.local/schemas/<name>.schema.json`.
- Every instance must carry `schema_version` (`"1.0.0"` as of this revision).
- `schema_version` is the operative version contract for instances.
- The `$id` does not change for compatible evolution; a breaking change receives a new `$id` after explicit migration review.

## Rules

1. Unknown schema versions are rejected or held for migration.
2. Adding a required field is a breaking change.
3. Enums are closed by default. Adding a platform, event type, permission, risk level, or council outcome requires schema update, policy review, fixtures/tests, migration note, and review.
4. Strictness is preserved. Do not widen `additionalProperties` simply to bypass contract evolution.
5. Credential-like fields are forbidden at every depth. Secret values stay behind opaque handles.
6. Migration order: schema -> fixtures/tests -> policies -> docs. CI must pass before merge.

## 2026-08-24 — Moltbook Docking District extension

`moltbook` is added to the allowed `platform` enum in:

- `social-account.schema.json`
- `social-event.schema.json`
- `connector-manifest.schema.json`

Purpose: allow the Docking District to carry provenance-backed Moltbook external identity/social records through the existing Agentropolis Social Transit Grid.

Initial scope is identity verification and external-origin arrival metadata only. The official Moltbook developer surface currently documents short-lived identity-token verification; this migration does **not** assume or invent an undocumented feed/publishing API.

Permission posture remains default-deny for external side effects. Moltbook live operation is blocked until a sealed `moltbook_app_key` capability is provisioned and a deployment endpoint binds the framework-agnostic verifier.

Existing X/Discord/Farcaster fixtures remain valid. Add Moltbook-specific identity fixtures/tests before promoting the bridge from integration staging to `production_approved`.

## Current versions

| Schema | schema_version | Notes |
|---|---|---|
| social-event | 1.0.0 | Platform enum now includes staged `moltbook` external-origin records |
| social-account | 1.0.0 | Platform enum now includes staged `moltbook`; opaque credential_handle only |
| action-receipt | 1.0.0 | completed requires provider_reference |
| connector-manifest | 1.0.0 | Platform enum now includes staged `moltbook` |
| approval-request | 1.0.0 | pending cannot be expired |
| council-decision | 1.0.0 | Recommendation must be in council outcomes |
| community-intake | 1.0.0 | terms/privacy must be true; never grants access |

## Deprecated / superseded

- The pre-production unversioned `social-event` is superseded by 1.0.0. Consumers must migrate or hold events in quarantine.
