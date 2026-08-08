"""Durable checkpoint store (B3).

Cursor/checkpoint persistence for connectors. The store is file-backed,
stdlib-only, and written atomically (temp file + os.replace) so a crash
mid-write never corrupts the last known cursor. Live providers are NOT
contacted; persistence is exercised through the fixture providers.
"""
import json
import os
import tempfile


def _utcnow():
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CheckpointStore:
    """File-backed cursor store for one connector.

    Load/save a small JSON document: {"cursor": {...}, "saved_at": "..."}.
    Missing or corrupt files load as an empty cursor (fail-open on read);
    writes fail loudly so callers can surface persistence errors.
    """

    def __init__(self, path):
        self.path = os.path.abspath(path)

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("cursor"), dict):
                return dict(data["cursor"])
            return {}
        except FileNotFoundError:
            return {}
        except (ValueError, OSError):
            # Corrupt checkpoint: do not fabricate a cursor; start fresh.
            return {}

    def save(self, cursor):
        payload = {"cursor": dict(cursor or {}), "saved_at": _utcnow()}
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory or ".", suffix=".ckpt.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def clear(self):
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
