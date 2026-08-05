# Connector Contract

Every HERMES Social connector must implement the same governed boundary.

## Required functions

- identify the platform and account
- declare connector mode: native API, secure browser, or social ingest
- declare supported capabilities
- return normalized Social Event objects
- expose rate-limit and permission state
- preserve source references and timestamps
- emit action receipts for every attempted side effect

## Prohibited behavior

Connectors must not place raw passwords, cookies, tokens, API keys, or wallet secrets in model context, logs, prompts, events, or receipts. Connectors must not silently upgrade permissions or perform write actions through read-only capability handles.

## Default state

New connectors enter quarantine and may only receive Observe permission after validation. Analyze, Draft, and Execute require separate approval.

## Initial pilot

The first bounded pilot targets X, Discord, and Farcaster in read-only mode. The allowed flow is read, normalize, classify, summarize, draft, and queue for human approval. Autonomous publishing is disabled.
