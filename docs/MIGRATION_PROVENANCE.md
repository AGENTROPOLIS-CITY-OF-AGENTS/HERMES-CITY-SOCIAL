# Migration Provenance — HERMES-CITY-SOCIAL

This document records the migration of the AGENTROPOLIS Social Transit Grid production
layers from the legacy source repository into this canonical repository.

## Source repository

- Legacy source: `wiredchaos/HERMES-SOCIAL` — now **legacy / reference-only**.
- Do not merge its open PRs into any production line.
- Do not delete it; it remains the archival source of record for pre-migration history.

## Migration scope

| Batch | Source PR | Source branch        | Source head SHA                             | Migrated branch              |
|-------|-----------|----------------------|---------------------------------------------|------------------------------|
| B2    | #4        | production/social-contracts | `45563a2149477a55cc8df803a736000539babef2` | `migration/b2-social-contracts` |
| B3    | #5        | production/social-ingest    | `60371c2e399ec9453afb17fe27317564d50e2fa0` | `migration/b3-social-ingest`    |

## Commit mapping (source SHA -> canonical commit)

### B2 — production/social-contracts (PR #4)

| Source commit                              | Canonical commit | Message |
|-------------------------------------------|------------------|---------|
| `5c2c74ae3609` (docs: Hermes Agent/Buzz)   | `08de843`        | docs: add Hermes Agent and Buzz social integration |
| `520f996b73e0` (docs: Buzz media/Devin)    | `b2dc41d`        | docs: add Buzz media and Devin workflow |
| `1e29609ae70a` (Expand to Transit Grid)    | `be709c9`        | Expand HERMES-SOCIAL into the AGENTROPOLIS Social Transit Grid |
| `6232273cb67b` (social event schema)       | `44073f4`        | Add canonical social event schema |
| `1c6a12ec2495` (social account schema)     | `3ccc72c`        | Add social account schema |
| `2fb586320afb` (action receipt schema)     | `9c05a94`        | Add social action receipt schema |
| `bff6fb54c0af` (permission policy)         | `9549262`        | Add social permission policy |
| `fc0f1caae2ad` (risk levels)               | `e6ba84e`        | Add social risk levels |
| `e5e7bcfdca5a` (approval gates)            | `ad43186`        | Add social approval gates |
| `5c06d7ec0919` (connector contract)        | `0d83dc6`        | Add governed connector contract |
| `49ec1efe1e15` (shadow commit docs)        | `86fa0a1`        | docs: apply Shadow Commit to social execution |
| `d515ce30e9c6` (dual control docs)         | `884ccf0`        | docs: bind social shadow commits to immutable bundles and dual control |
| `45563a214947` (**B2 head**)               | `9fc402e`        | feat(hermes-social): versioned production contracts (schemas, fixtures, policies, tests) |

Merge commits from source main (`8d71f36`, `499d425`) were not replayed; their content
is fully carried by the two docs commits they merged (`5c2c74a`, `520f996`).

### B3 — production/social-ingest (PR #5)

| Source commit                              | Canonical commit | Message |
|-------------------------------------------|------------------|---------|
| `30d83fd65df9` (B3 adapters + membrane)    | *(applied in step 2)* | feat(hermes-social): connector adapters and Social Ingest Membrane (B3) |
| `60371c2e399e` (**B3 head**, gitleaks fix) | *(applied in step 2)* | fix(hermes-social): construct credential fixture (gitleaks allowlist for tests/) |

Each canonical commit carries the `(cherry picked from commit <source-sha>)` trailer,
preserving direct SHA mapping at the commit level.

## Verification

- B2: `python scripts/verify-contracts.py` — PASS (fresh run in canonical repo).
- B3: `python scripts/verify-contracts.py` + `uv run --with jsonschema --with pyyaml
  python -m unittest discover -s tests -v` — PASS.
- Tree parity: canonical migration branch trees match source head trees byte-for-byte
  for all migrated paths (checked with `git diff <source-sha> <canonical-branch>`).

## Canonicalization (deliberate divergence)

The only intentional divergence from source content is `README.md`, which was retitled
for the canonical repository and gained this provenance section. All schemas, fixtures,
tests, policies, security controls, connectors, membrane code, and receipts are
byte-identical to their source counterparts.
