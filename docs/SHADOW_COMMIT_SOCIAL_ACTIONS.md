# Shadow Commit for Social Actions

The HERMES Social Surface may use the Civic Foundry Runtime for isolated campaign tools, moderation consoles, analytics gadgets, and account-specific workflows. Social execution remains governed by the Social Transit Grid.

Authority follows the Civic Foundry Runtime doctrine: AEGIS issues the policy decision, AGENTROPOLIS-AGENT-MCP issues and enforces the capability envelope and commit control, and HERMES presents approvals but never self-authorizes a capability.

## Required flow

```text
social event or operator intent
  -> HERMES council
  -> AEGIS policy decision
  -> Agent MCP capability envelope
  -> draft
  -> shadow publish/message/moderation result
  -> immutable approval bundle
  -> required human or dual-control approval
  -> pre-execution bundle comparison and revalidation
  -> atomic execution
  -> platform response comparison
  -> permanent receipt (every terminal outcome)
```

## Immutable approval bundle

Every social execution is bound to an immutable approval bundle that captures all of the following fields:

- Platform, account, channel, and audience
- Conversation context and moderation target
- Final content and attachments, with content hashes
- Timing, budget, and action class
- Campaign configuration and simulation hash
- Platform state version and expiration
- Idempotency key

The execution request is compared against the bundle immediately before the side effect. A different-but-valid account or channel, or any other change to a bound field, invalidates the approval and blocks execution; a stale approval may never execute.

## Mandatory dual control

Dual control is required for the following action classes:

- Deletion
- Blocking and banning
- Paid promotion
- Financial actions
- Mass messaging
- High-reach publishing
- Irreversible moderation
- Identity or account changes

These are execute_high_risk actions under the approval-gates policy: they require both a human_operator and a second_controller. HERMES presents the approval for review but cannot grant its own authority.

## Receipts for terminal outcomes

Every terminal outcome produces a permanent receipt:

- committed
- denied
- cancelled
- expired
- failed
- blocked
- revoked
- revalidation-mismatch

Receipts are emitted for every terminal outcome, including pre-execution outcomes such as denial, cancellation, expiry, failure, blocking, revocation, and revalidation mismatch; they are not limited to outcomes that reach the platform response comparison.

## Rules

- A simulated post, reply, message, moderation action, or campaign is never represented as published.
- Platform permissions, rate limits, conversation state, and content hashes are revalidated immediately before execution, at the same point the execution request is compared against the immutable bundle.
- Raw social tokens, cookies, passwords, and authenticated session material remain sealed outside model context and generated applications.
- Cross-platform Blueprints must request separate capabilities for each account and channel.
