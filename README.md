# HERMES-SOCIAL

Private implementation repository for the **AGENTROPOLIS Social Layer** and the **HERMES Social Surface**.

HERMES-SOCIAL is no longer limited to short-form video direction. It is the governed multichannel social infrastructure behind HERMES Desktop, supporting Web2 social networks, community and messaging systems, and Web3 social protocols through modular adapters.

The public-safe architecture is published through the `social/` section of `wiredchaos/HERMES-CITY`.

---

## Canonical Role

```text
External social channels
  -> API / browser / ingest adapters
  -> AGENTROPOLIS Ingest Membrane
  -> ASBE + policy checks
  -> normalized Social Event
  -> HERMES council
  -> ignore / analyze / draft / escalate / approve / execute
  -> permanent action receipt
```

HERMES is the operator and orchestration surface.

The AGENTROPOLIS Social Transit Grid is the governed infrastructure beneath it.

---

## Supported Channel Classes

### Web2 Social

- X
- LinkedIn
- Instagram
- Facebook
- Threads
- TikTok
- YouTube
- Reddit

### Community and Messaging

- Discord
- Telegram
- WhatsApp
- Slack

### Web3 Social and Community

- Farcaster
- Bluesky
- Lens
- Mirror
- Paragraph
- Guild
- Snapshot

Future platforms must be added through adapters without changing the core interface or normalized event model.

---

## Connector Modes

### Native API Connector

Structured reads, notifications, analytics, publishing, moderation, and messaging where platform permissions allow.

### Secure Browser Surface

Isolated authenticated sessions for platforms with limited or restricted APIs. Raw passwords, cookies, and tokens must never enter model context.

### Social Ingest Connector

Webhooks, RSS, APIs, approved crawlers, email notifications, and bounded browser extraction.

---

## Shared Social Event Schema

Every external signal must normalize into a shared event containing at minimum:

- `platform`
- `account_id`
- `event_type`
- `author`
- `content`
- `media`
- `conversation_id`
- `engagement`
- `permissions`
- `provenance`
- `risk_score`
- `timestamp`

External social content is untrusted sensor data. It must pass the Ingest Membrane, ASBE checks, provenance checks, and policy controls before entering memory, RAG, task creation, or execution.

---

## Permission Model

Permissions are scoped separately per account and channel:

1. **Observe** — read feeds, comments, trends, and notifications.
2. **Analyze** — summarize, classify, score, and detect opportunities.
3. **Draft** — prepare posts, replies, messages, campaigns, and media instructions.
4. **Execute** — publish, message, moderate, or perform another external action.

Execution is never implied by read access. High-risk or irreversible actions require human approval or dual control.

---

## HERMES Desktop Surface

```text
LEFT
sessions / agents / skills / artifacts / memory

CENTER
HERMES conversation / council / research / drafting / execution

RIGHT
platform tabs / unified inbox / feeds / notifications
analytics / composer / drafts / approval queue
```

---

## Capability Namespace

```text
social.<platform>.read_feed
social.<platform>.read_notifications
social.<platform>.draft_post
social.<platform>.draft_reply
social.<platform>.publish
social.<platform>.send_message
social.<platform>.moderate
```

Agents receive bounded capability handles. They do not receive raw secrets.

---

## Security Doctrine

- Credentials remain inside sealed vaults.
- Raw passwords and tokens never enter model context.
- Authenticated browser sessions remain isolated.
- Each platform has separate permissions, rate limits, budgets, and action policies.
- All actions carry provenance and permanent receipts.
- No untrusted social content writes directly to sovereign memory.
- No platform adapter bypasses the AGENTROPOLIS Policy/Risk Layer.

---

## Existing Media Capability

The original HERMES social-video capability remains an internal module for:

- TikTok
- Instagram Reels
- YouTube Shorts
- clip extraction
- platform-native media transformation
- Skills and MCP-driven production workflows

It now operates as one capability inside the broader Social Transit Grid.

---

## License

Apache License 2.0. See `LICENSE`.
