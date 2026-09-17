# Hermes Cross-Surface Continuity Adapter

Status: ADAPTER / CANARY
Canonical owner: false
Authority source: Agentropolis Continuity Plane + Context Capsule contract

## Role

HERMES-CITY-SOCIAL adapts messaging surfaces into governed continuation. It does not own continuity law, agent identity, mandate, or execution authority.

The adapter exists to carry a bounded continuation request between Hermes and permitted messaging surfaces while preserving provenance and producing a correlated receipt.

## Required flow

```text
source session
  -> build bounded Context Capsule
  -> Ingest Membrane / policy checks
  -> resolve allowed destination
  -> emit handoff request
  -> destination accepts or rejects
  -> rebind/continue permitted session state
  -> emit delivery receipt
  -> publish receipt/event to BUZZ when configured
  -> resume-capable state remains bounded by original mandate
```

## Handoff event

A handoff event SHOULD include:

```yaml
event_type: continuity.handoff.requested
continuity_id:
request_id:
agent_identity_ref:
mandate_ref:
source_runtime:
source_surface:
source_session_ref:
target_runtime:
target_surface:
target_destination_ref:
workspace_ref:
context_capsule_ref:
authority_fingerprint:
requested_at:
expires_at:
```

No secret material belongs in the event body.

## Receipt event

```yaml
event_type: continuity.handoff.receipt
continuity_id:
request_id:
status:
source_session_ref:
target_session_ref:
target_destination_ref:
context_items_sent:
context_items_accepted:
context_items_rejected:
redaction_count:
authority_fingerprint_before:
authority_fingerprint_after:
completed_at:
```

## Security rules

1. External chat history is untrusted input.
2. Channel membership does not grant execution authority.
3. Destination IDs are routing references, not agent identity.
4. Target destinations MUST be allowlisted and validated at send time.
5. Handoffs MUST be idempotent by `request_id`.
6. Missing delivery proof MUST result in `RECEIPT_MISSING`, not assumed success.
7. Authority fingerprints MUST remain stable across ordinary continuation.
8. Private keys, bearer tokens, OAuth refresh tokens, wallet signers, raw `.env` content, and hidden chain-of-thought MUST NOT transit the adapter.
9. Returned channel content re-enters through the Ingest Membrane before consequential use.
10. BUZZ coordinates and records the workflow. BUZZ does not grant the receiving agent additional authority.

## Canary destinations

Initial validation SHOULD use a non-sensitive Telegram destination with a synthetic task. Slack/Discord/WhatsApp/BotBae surfaces can follow after the same invariants pass.

## Failure states

```text
DELIVERED
PARTIAL
REJECTED
EXPIRED
DESTINATION_UNAVAILABLE
DESTINATION_NOT_ALLOWED
RECEIPT_MISSING
AUTHORITY_MISMATCH
INGEST_POLICY_BLOCK
SECRET_POLICY_BLOCK
```

## Definition of done

The adapter is ready for broader testing when one Hermes session can move to an approved social surface and back while preserving objective, workspace, provenance, unresolved work, and receipt correlation, with no authority gain and no unexpected secret transfer.
