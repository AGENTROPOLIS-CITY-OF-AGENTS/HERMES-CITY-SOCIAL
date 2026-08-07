"""Provider adapter exports and the default pilot registry (B3)."""

from ..registry import ConnectorRegistry
from .discord_provider import DiscordConnector
from .farcaster_provider import FarcasterConnector
from .x_provider import XConnector

__all__ = ["XConnector", "DiscordConnector", "FarcasterConnector", "build_pilot_registry"]


def build_pilot_registry():
    """Register the three pilot adapters with fixture providers (mocked)."""
    registry = ConnectorRegistry()
    registry.register(XConnector())
    registry.register(DiscordConnector())
    registry.register(FarcasterConnector())
    return registry
