# Buzz Media and Devin Workflow

HERMES SOCIAL adopts two new upstream implementation lanes:

- `tonbistudio/buzz-skills` for native Hermes-to-Buzz connection and verified media attachments
- merged `block/buzz#3225` for Devin as a built-in ACP coding preset

## Social production flow

```text
Campaign brief
  -> Buzz thread
  -> Hermes research and production
  -> approved asset
  -> native Buzz attachment
  -> accepted event ID
  -> human review
  -> publish approval
```

The `buzz-media-attachments` skill is the preferred delivery path for local clips, GIFs, and approved media. A gateway response alone is not proof of delivery. The workflow must retain the Buzz `accepted` result and event ID.

When MP4 media is rejected, the skill may use fast-start remuxing, canonical metadata-free H.264/AAC re-encoding, or GIF fallback. The source must remain unchanged unless the operator explicitly approves replacement.

## Devin lane

Devin may be selected through Buzz's built-in ACP preset for approved repository tasks such as social-site fixes, media pipeline code, tests, and patch generation.

Devin does not receive automatic authority to publish posts, upload media to external platforms, merge code, deploy applications, access unrelated repositories, or use production credentials.

## Required controls

- owner-only agent invocation by default
- dedicated Buzz agent identity
- no private keys or auth tags in chat or argv
- human approval before external publishing
- artifact and transformed-media hashes
- accepted Buzz event ID in the receipt
- explicit record of any external side effect
