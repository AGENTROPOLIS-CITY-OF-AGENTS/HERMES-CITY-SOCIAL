"""Connector adapter interface (B3).

Every adapter implements the nine-method connector contract. Connectors
receive capability-scoped secret handles, never raw credentials. All outputs
must validate against the Social Event schema before leaving quarantine.
"""
import abc


class Connector(abc.ABC):
    """Bounded, read-only connector adapter contract.

    Pilot permissions:
      x         -> observe
      discord   -> observe, analyze
      farcaster -> observe
    Execute is default-deny everywhere.
    """

    connector_id = None
    platform = None
    manifest = None  # validated against connector-manifest.schema.json

    def __init__(self, secret_handles=None, fixture_provider=None, checkpoint_store=None):
        self._secret_handles = dict(secret_handles or {})
        self._fixture_provider = fixture_provider
        self._checkpoint_store = checkpoint_store
        self._revoked = False
        self._checkpoint = {}
        self._initialized = False

    # -- lifecycle ---------------------------------------------------------

    @abc.abstractmethod
    def initialize(self):
        """Bind capability handles; must not touch live credentials."""

    def health_check(self):
        """Deterministic health state: dict with status ok/degraded/down."""
        if self._revoked:
            return {"status": "down", "reason": "revoked", "connector_id": self.connector_id}
        if not self._initialized:
            return {"status": "degraded", "reason": "not_initialized", "connector_id": self.connector_id}
        return {"status": "ok", "connector_id": self.connector_id}

    @abc.abstractmethod
    def read_events(self):
        """Return a list of raw provider events since the checkpoint."""

    @abc.abstractmethod
    def normalize_event(self, raw_event):
        """Normalize a provider event into the pre-schema Social Event shape."""

    def validate_event(self, normalized):
        """Schema validation is applied by the Ingest Membrane (quarantine exit).
        Adapters may perform cheap structural checks here and return bool."""
        return isinstance(normalized, dict)

    # -- cursor / checkpoint ----------------------------------------------

    def checkpoint_cursor(self, cursor):
        """Persist the cursor. If a CheckpointStore is bound, save atomically."""
        self._checkpoint = dict(cursor or {})
        if self._checkpoint_store is not None:
            self._checkpoint_store.save(self._checkpoint)

    def get_checkpoint(self):
        """Return the checkpoint. If empty and a store is bound, load it."""
        if not self._checkpoint and self._checkpoint_store is not None:
            self._checkpoint = self._checkpoint_store.load()
        return dict(self._checkpoint)

    # -- rate limits -------------------------------------------------------

    def handle_rate_limit(self, retry_after):
        """Deterministic backoff policy. Returns seconds to wait."""
        return max(1.0, float(retry_after))

    # -- revocation / shutdown ---------------------------------------------

    def revoke(self):
        """Revoke this connector. All subsequent operations must fail closed."""
        self._revoked = True

    def shutdown(self):
        self._revoked = True
        self._initialized = False

    def _ensure_active(self):
        if self._revoked:
            raise ConnectorRevoked("connector revoked: %s" % self.connector_id)
        if not self._initialized:
            self.initialize()


from .errors import (  # noqa: E402  (imported after class to avoid cycle)
    ConnectorRevoked,
)
