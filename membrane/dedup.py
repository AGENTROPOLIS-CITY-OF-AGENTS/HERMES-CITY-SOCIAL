"""Content-hash deduplication store (B3)."""

import hashlib
import json


def content_hash(content):
    """Canonical sha256 over the content object (sorted keys)."""
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DedupStore:
    """In-memory dedup store keyed by content hash (deterministic)."""

    def __init__(self):
        self._by_hash = {}

    def seen(self, digest):
        return digest in self._by_hash

    def record(self, digest, event_id):
        self._by_hash[digest] = event_id

    def event_id(self, digest):
        return self._by_hash.get(digest)

    def __len__(self):
        return len(self._by_hash)
