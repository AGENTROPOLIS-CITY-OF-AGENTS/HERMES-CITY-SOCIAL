# Schema Migration Rules

Versioning and evolution rules for the AGENTROPOLIS contracts in `schemas/`.

## Version identity

- Every schema has a stable canonical `$id`:
  `https://agentropolis.local/schemas/<name>.schema.json`.
- Every instance must carry `schema_version` (`"1.0.0"` as of this revision).
- `schema_version` is the operative version contract for instances.
  The `$id` does not change for compatible evolution; a breaking change
  receives a new `$id` (e.g. `.../social-event/v2.schema.json`) AFTER an
  explicit migration review — never silently.

## Rules

1. **Unknown schema versions are rejected or held for migration.**
   A payload with `schema_version` not in the supported set goes to
   `validation_state: held_for_migration` / `quarantine_state: quarantined`,
   never into the approved event bus.
2. **Adding a required field is a breaking change.** Required additions need a
   version bump (or a documented dual-write window where the field is optional).
3. **Enums are closed by default.** Adding a platform, event type, permission,
   risk level, or council outcome requires: (a) updating the schema,
   (b) updating `policies/*.yaml` where the enum mirrors policy,
   (c) adding fixtures, (d) a migration note in this file, (e) review.
   Pilot platforms are `x`, `discord`, `farcaster`.
4. **Strictness is preserved.** All schemas use `additionalProperties: false`.
   Do not widen to allow arbitrary properties; encode new fields explicitly.
5. **Credential-like fields are forbidden at every depth.** The validation
   suite (`tests/test_schemas.py`) scans instances for credential keys and
   secret-looking values. New fields that could carry secrets must use opaque
   handles (`^handle:[a-z0-9-]+$`) or be documented as forbidden.
6. **Migration order:** schema first -> fixtures -> tests -> policies -> docs.
   CI (`scripts/verify-contracts.py`) must pass before merge.

## Current versions

| Schema | schema_version | Notes |
|---|---|---|
| social-event | 1.0.0 | Mandate field set; enums for platform/event type/risk/validation/quarantine/council |
| social-account | 1.0.0 | Opaque credential_handle only |
| action-receipt | 1.0.0 | completed requires provider_reference (business rule) |
| connector-manifest | 1.0.0 | required_secret_handles are NAMES only |
| approval-request | 1.0.0 | pending cannot be expired (business rule) |
| council-decision | 1.0.0 | Recommendation must be in council outcomes |
| community-intake | 1.0.0 | terms/privacy must be true; never grants access |

## Deprecated / superseded

- The pre-production unversioned `social-event` (no `schema_version`, older
  required set) is superseded by 1.0.0. Consumers must migrate or hold events
  in quarantine.
