"""Eligible event bus (B3).

Only events released by the membrane with eligible council states
(analyze/draft) and policy_state allowed are published. Publish is the ONLY
write path; raw payloads never enter the bus.
"""


class EligibleEventBus:
    def __init__(self):
        self._events = []

    def publish(self, event):
        self._events.append(event)

    def items(self):
        return list(self._events)

    def clear(self):
        self._events.clear()

    def __len__(self):
        return len(self._events)
