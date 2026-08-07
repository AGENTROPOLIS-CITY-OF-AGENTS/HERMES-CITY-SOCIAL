"""B3 connector contract tests: interface, registry, manifests, adapters,
fixture providers, health, rate limits, revocation, checkpoints, pagination.

Run via:
  uv run --with jsonschema python -m unittest discover -s tests -v
"""
import json
import os
import tempfile
import unittest

from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys_path = os.path.join(ROOT)
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

from connectors.base import Connector  # noqa: E402
from connectors.checkpoint import CheckpointStore  # noqa: E402
from connectors.errors import (  # noqa: E402
    ConnectorAuthenticationError,
    ConnectorError,
    ConnectorMalformedResponse,
    ConnectorRateLimited,
    ConnectorRevoked,
    ConnectorTimeout,
)
from connectors.fixtures.fixture_providers import FixtureConnector, FixtureProvider  # noqa: E402
from connectors.manifest import MANIFEST_SCHEMA, validate_manifest  # noqa: E402
from connectors.providers import (  # noqa: E402
    DiscordConnector,
    FarcasterConnector,
    XConnector,
    build_pilot_registry,
)
from connectors.registry import ConnectorRegistry  # noqa: E402

RESPONSES = os.path.join(ROOT, "connectors", "fixtures", "responses")


def load_fixture(platform, name):
    with open(os.path.join(RESPONSES, platform, name), encoding="utf-8") as fh:
        return json.load(fh)


class ConnectorContractTests(unittest.TestCase):
    """The nine-method contract is present on every adapter."""

    def test_contract_methods_present(self):
        for cls in (XConnector, DiscordConnector, FarcasterConnector):
            for method in (
                "initialize", "health_check", "read_events", "normalize_event",
                "validate_event", "checkpoint_cursor", "get_checkpoint",
                "handle_rate_limit", "revoke", "shutdown",
            ):
                self.assertTrue(callable(getattr(cls, method, None)),
                                "%s missing %s" % (cls.__name__, method))

    def test_pilot_permission_matrix(self):
        # X: observe only. Discord: observe+analyze. Farcaster: observe.
        # Execute is default-deny everywhere.
        matrix = {
            "conn_x_observe_001": (["observe"], False),
            "conn_discord_observe_001": (["observe", "analyze"], False),
            "conn_farcaster_observe_001": (["observe"], False),
        }
        for cid, (perms, execute) in matrix.items():
            registry = build_pilot_registry()
            connector = registry.get(cid)
            self.assertEqual(connector.supported_permissions, perms)
            self.assertEqual(connector._base_permissions()["execute"], execute)

    def test_adapter_initialize_and_health(self):
        connector = XConnector()
        self.assertEqual(connector.health_check()["status"], "degraded")
        connector.initialize()
        self.assertEqual(connector.health_check()["status"], "ok")

    def test_revoke_fails_closed(self):
        connector = XConnector()
        connector.initialize()
        connector.revoke()
        self.assertEqual(connector.health_check()["status"], "down")
        with self.assertRaises(ConnectorRevoked):
            connector.read_events()

    def test_shutdown_fails_closed(self):
        connector = DiscordConnector()
        connector.initialize()
        connector.shutdown()
        self.assertEqual(connector.health_check()["status"], "down")
        with self.assertRaises(ConnectorRevoked):
            connector.read_events()

    def test_handle_rate_limit_deterministic(self):
        connector = XConnector()
        self.assertEqual(connector.handle_rate_limit(15), 15.0)
        self.assertEqual(connector.handle_rate_limit(0), 1.0)
        self.assertEqual(connector.handle_rate_limit(-5), 1.0)


class RegistryTests(unittest.TestCase):
    def test_build_pilot_registry(self):
        registry = build_pilot_registry()
        self.assertEqual(registry.ids(), [
            "conn_discord_observe_001",
            "conn_farcaster_observe_001",
            "conn_x_observe_001",
        ])
        self.assertTrue(registry.has("conn_x_observe_001"))
        self.assertFalse(registry.has("conn_nope"))

    def test_duplicate_register_rejected(self):
        registry = build_pilot_registry()
        with self.assertRaises(ConnectorError):
            registry.register(XConnector())

    def test_unknown_connector_raises(self):
        registry = build_pilot_registry()
        with self.assertRaises(KeyError):
            registry.get("conn_nope")

    def test_health_snapshot_and_revoke(self):
        registry = build_pilot_registry()
        snapshot = registry.health_snapshot()
        self.assertEqual(len(snapshot), 3)
        self.assertTrue(all(v["status"] in ("ok", "degraded", "down") for v in snapshot.values()))
        registry.revoke("conn_x_observe_001")
        self.assertEqual(registry.health_snapshot()["conn_x_observe_001"]["status"], "down")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        with open(MANIFEST_SCHEMA, encoding="utf-8") as fh:
            self.schema = json.load(fh)
        self.validator = Draft202012Validator(self.schema)

    def test_pilot_manifests_validate_against_schema(self):
        registry = build_pilot_registry()
        for cid in registry.ids():
            manifest = registry.manifest(cid)
            validate_manifest(manifest, lambda schema: self.validator)
            errors = list(self.validator.iter_errors(manifest))
            self.assertEqual(errors, [], "%s manifest invalid: %s" % (cid, errors))

    def test_missing_required_field_rejected(self):
        manifest = build_pilot_registry().manifest("conn_x_observe_001")
        stripped = {k: v for k, v in manifest.items() if k != "connector_id"}
        with self.assertRaises(Exception):
            validate_manifest(stripped, lambda schema: self.validator)

    def test_manifest_status_blocked_live(self):
        # Live credentials are NOT authorized: every pilot manifest is
        # blocked_live, never live.
        registry = build_pilot_registry()
        for cid in registry.ids():
            self.assertEqual(registry.manifest(cid)["status"], "blocked_live")


class FixtureProviderTests(unittest.TestCase):
    def test_normal_mode_returns_fixtures(self):
        provider = FixtureProvider("x")
        events = provider.fetch()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"]["id"], "tweet-2001")

    def test_failure_modes_raise_typed_errors(self):
        cases = [
            ("rate_limited", ConnectorRateLimited),
            ("timeout", ConnectorTimeout),
            ("auth_failure", ConnectorAuthenticationError),
            ("revoked_signal", ConnectorRevoked),
            ("malformed", ConnectorMalformedResponse),
        ]
        for mode, exc_type in cases:
            provider = FixtureProvider("x", mode=mode)
            with self.assertRaises(exc_type):
                provider.fetch()

    def test_pagination_advances_cursor(self):
        provider = FixtureProvider("x")
        # Deterministic: one fixture -> first page has it, next page empty.
        page1, cursor1 = provider.fetch_page(page_size=1)
        self.assertEqual(len(page1), 1)
        self.assertEqual(cursor1, "tweet-2001")
        page2, cursor2 = provider.fetch_page({"after": cursor1}, page_size=1)
        self.assertEqual(page2, [])
        self.assertIsNone(cursor2)

    def test_pagination_respects_page_size(self):
        provider = FixtureProvider("discord")
        page, cursor = provider.fetch_page(page_size=1)
        self.assertLessEqual(len(page), 1)


class NormalizerTests(unittest.TestCase):
    """Normalizer output must be pre-schema Social Event shapes."""

    def test_x_normalizer(self):
        connector = XConnector()
        normalized = connector.normalize_event(load_fixture("x", "tweet.json"))
        self.assertEqual(normalized["platform"], "x")
        self.assertEqual(normalized["event_id"], "x:tweet-2001")
        self.assertEqual(normalized["event_type"], "tweet")
        self.assertTrue(normalized["permissions"]["observe"])
        self.assertFalse(normalized["permissions"]["execute"])
        self.assertIn("source_reference", normalized["provenance"])
        self.assertEqual(normalized["provenance"]["source_reference"], "mock://x/tweet-2001")

    def test_discord_normalizer(self):
        connector = DiscordConnector()
        normalized = connector.normalize_event(load_fixture("discord", "message.json"))
        self.assertEqual(normalized["platform"], "discord")
        self.assertEqual(normalized["event_id"], "discord:msg-501")
        self.assertTrue(normalized["permissions"]["analyze"])
        self.assertFalse(normalized["permissions"]["execute"])
        self.assertEqual(normalized["conversation_id"], "ch-77")

    def test_farcaster_normalizer(self):
        connector = FarcasterConnector()
        normalized = connector.normalize_event(load_fixture("farcaster", "cast.json"))
        self.assertEqual(normalized["platform"], "farcaster")
        self.assertEqual(normalized["event_id"], "farcaster:cast-301")
        self.assertFalse(normalized["permissions"]["analyze"])
        self.assertFalse(normalized["permissions"]["execute"])


class CheckpointTests(unittest.TestCase):
    def test_checkpoint_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(os.path.join(tmp, "ckpt.json"))
            store.save({"after": "tweet-2001"})
            self.assertEqual(store.load(), {"after": "tweet-2001"})

    def test_checkpoint_store_missing_file_loads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(os.path.join(tmp, "missing.json"))
            self.assertEqual(store.load(), {})

    def test_connector_checkpoint_persists_through_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(os.path.join(tmp, "ckpt.json"))
            connector = XConnector(checkpoint_store=store)
            connector.checkpoint_cursor({"after": "tweet-2001"})
            fresh = XConnector(checkpoint_store=store)
            self.assertEqual(fresh.get_checkpoint(), {"after": "tweet-2001"})

    def test_read_page_persists_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(os.path.join(tmp, "ckpt.json"))
            connector = XConnector(checkpoint_store=store)
            connector.initialize()
            events, cursor = connector.read_page(page_size=1)
            self.assertEqual(len(events), 1)
            self.assertEqual(cursor, "tweet-2001")
            self.assertEqual(connector.get_checkpoint(), {"after": "tweet-2001"})

    def test_require_handles_blocks_without_capability(self):
        connector = XConnector(secret_handles={}, require_handles=True)
        with self.assertRaises(ConnectorAuthenticationError):
            connector.initialize()

    def test_require_handles_passes_with_capability(self):
        connector = XConnector(secret_handles={"x_bearer_token": "opaque-handle"}, require_handles=True)
        connector.initialize()
        self.assertEqual(connector.health_check()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
