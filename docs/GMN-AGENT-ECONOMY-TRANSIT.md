# GMN Agent Economy Transit

HERMES-CITY-SOCIAL is the governed operator and external-network transit surface for GMN-related social activity. It does not own GMN editorial truth, canonical KOL identity, or financial execution authority.

## Canonical path

```text
external social / agent networks
  -> connector / ingest
  -> Ingest Membrane
  -> validation + provenance + policy
  -> normalized Social Event
  -> HERMES council / operator
  -> GMN analysis candidate or SOCIALS interaction
  -> approved draft / publish action
  -> Action Receipt
```

Outbound GMN distribution follows the inverse governed path:

```text
GMN verified intelligence
  -> Social Magnet programming recommendation
  -> Social Systems persona + SocialAuthorityGrant
  -> HERMES external adapter
  -> external platform action
  -> permanent receipt
```

## GMN requirements

GMN-bound or GMN-originated external social events SHOULD preserve:

- correlation ID
- source reference and retrieval timestamp
- content hash
- permissions state
- validation / quarantine / policy state
- risk score and risk level
- GMN verification state when the event has been editorially reviewed
- disclosure references when the content concerns a sponsored, affiliated, treasury-exposed or agent-launched asset

## Connector scope

The current pilot connector classes remain X, Discord and Farcaster. Additional platforms must be introduced through the existing connector and schema migration process. No GMN feature may bypass connector permissions, sealed credentials, policy gates or action receipts.

## Financial boundary

External publishing or social engagement never implies authority to trade, move treasury assets, mint, settle, bridge or alter fiscal policy.
