# Hermes Agent + Buzz Social Integration

HERMES-SOCIAL uses Buzz as the shared production room and Hermes Agent as the bounded execution runtime for short-form video and social distribution.

```text
Content signal
  -> Buzz production channel
  -> signed brief or mention
  -> Hermes social dispatcher
  -> policy-scoped Hermes job
  -> research, script, clip, caption, or edit artifact
  -> human review
  -> approved publishing lane
  -> receipt returned to the originating thread
```

## Recommended agents

| Agent | Function | Default authority |
|---|---|---|
| `hermes-trend-scout` | Research trends, references, and source material | Read-only external access |
| `hermes-scriptwriter` | Hooks, scripts, captions, shot lists | Workspace write only |
| `hermes-clip-editor` | Clip extraction and edit manifests | Approved media directories only |
| `hermes-reviewer` | Brand, claims, rights, safety, and receipt review | Read-only with comments |
| `hermes-publisher` | Posts approved assets to social platforms | Explicit approval required |

## Buzz channels

```text
#social-signals
#script-room
#clip-forge
#brand-review
#publish-queue
#receipts
```

## Artifact layout

```text
RESEARCH/   sources, trends, and reference notes
SCRIPTS/    hooks, scripts, captions, and shot lists
EDITS/      clip manifests and export instructions
OUTBOX/     publish-ready packages
RECEIPTS/   hashes, approvals, tool use, and platform side effects
```

## Required controls

- signed identity is not publishing authority
- each agent receives an independent tool and credential policy
- publishing, deletion, paid promotion, and account changes require approval
- retrieved content is treated as untrusted input
- copyrighted or client media remains within approved storage roots
- duplicate Buzz events do not create duplicate posts
- every external post records platform, account, asset hash, approval event, and result

## First implementation slice

1. Connect one Buzz production channel to `hermes-trend-scout` and `hermes-scriptwriter`.
2. Produce review-ready artifacts without external publishing access.
3. Return paths and hashes to the original thread.
4. Add a human approval gate before `hermes-publisher` receives credentials.
5. Surface status and receipts to AGENTROPOLIS Mission Control.

**Buzz coordinates the room. Hermes creates the work. Humans approve publication. Receipts preserve the record.**