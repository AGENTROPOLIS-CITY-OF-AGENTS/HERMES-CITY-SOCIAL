# HERMES CITY x Oh My Hermes

Oh My Hermes (OMH) is an optional workflow-intelligence layer above Hermes-native execution and below AGENTROPOLIS governance.

## Runtime relationship

AGENTROPOLIS mandate/policy -> Dispatch -> OMH workflow -> Hermes/Pantheon agents -> executor -> receipt -> independent verification

OMH can coordinate named agents, parallel lanes, coding executors, project memory and bounded workflow loops. Hermes remains the runtime; OMH does not become identity or authority.

## Pantheon / peer rules

- bot-to-bot messages are coordination data, not authorization
- group-chat membership does not expand capability
- @mentions do not create mandates
- cron/routine work revalidates its mandate and policy scope at execution time
- live steering may narrow or stop work but may not silently expand authority

## Provider fallback

HERMES CITY should support `omh` and `hermes-native` workflow providers behind the same dispatch contract. Provider failure must degrade gracefully rather than disable the city.

## Evidence

Surface provider, executor/model, phase, cost, evidence and verification state to Mission Control. Executor/provider completion is `REPORTED_DONE` until independently verified.