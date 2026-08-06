# Shadow Commit for Social Actions

The HERMES Social Surface may use the Civic Foundry Runtime for isolated campaign tools, moderation consoles, analytics gadgets, and account-specific workflows. Social execution remains governed by the Social Transit Grid.

## Required flow

```text
social event or operator intent
  -> HERMES council
  -> draft
  -> shadow publish/message/moderation result
  -> approval bundle
  -> platform-state and permission revalidation
  -> approved execution
  -> platform response comparison
  -> permanent action receipt
```

## Rules

- A simulated post, reply, message, moderation action, or campaign is never represented as published.
- Account, channel, audience, attachments, final text, timing, budget, and action class must be visible in the approval bundle.
- Platform permissions, rate limits, conversation state, and content hashes are revalidated immediately before execution.
- Raw social tokens, cookies, passwords, and authenticated session material remain sealed outside model context and generated applications.
- Cross-platform Blueprints must request separate capabilities for each account and channel.
- Deletion, blocking, banning, paid promotion, mass messaging, and high-reach publishing require explicit approval or dual control.