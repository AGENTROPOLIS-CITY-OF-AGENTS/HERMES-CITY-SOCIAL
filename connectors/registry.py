"""Connector registry (B3).

Registers adapters by connector_id and exposes manifests, health checks, and
revocation. The registry never holds raw credentials — only capability-scoped
secret handle names.
"""
from .errors import ConnectorError


class ConnectorRegistry:
    def __init__(self):
        self._connectors = {}
        self._manifests = {}

    def register(self, connector):
        if connector.connector_id in self._connectors:
            raise ConnectorError("duplicate connector_id: %s" % connector.connector_id)
        self._connectors[connector.connector_id] = connector
        self._manifests[connector.connector_id] = connector.manifest

    def get(self, connector_id):
        if connector_id not in self._connectors:
            raise KeyError("unknown connector: %s" % connector_id)
        return self._connectors[connector_id]

    def has(self, connector_id):
        return connector_id in self._connectors

    def manifest(self, connector_id):
        if connector_id not in self._manifests:
            raise KeyError("unknown connector: %s" % connector_id)
        return self._manifests[connector_id]

    def ids(self):
        return sorted(self._connectors)

    def health_snapshot(self):
        return {cid: self._connectors[cid].health_check() for cid in self.ids()}

    def revoke(self, connector_id):
        if connector_id not in self._connectors:
            raise KeyError("unknown connector: %s" % connector_id)
        self._connectors[connector_id].revoke()
