import asyncio
import time
import pytest
from app.market_data.connection.connection_manager import ConnectionManager
from app.market_data.providers.base import ConnectionState


def test_connection_state_lifecycle(temp_db):
    """Verify connection states: DISCONNECTED -> STALE (connected waiting) -> LIVE -> STALE (timeout)."""
    async def _test():
        mgr = ConnectionManager(provider_name="UPSTOX")
        assert mgr.current_state == ConnectionState.DISCONNECTED

        # When socket connects, state becomes STALE initially (fresh updates not yet arrived)
        await mgr.update_socket_status(True, "Handshake ok")
        assert mgr.current_state == ConnectionState.STALE

        # When fresh market tick arrives, state evaluates to LIVE
        now_ms = int(time.time() * 1000)
        mgr.record_tick_received(now_ms)
        evaluated = await mgr.evaluate_freshness()
        assert evaluated == ConnectionState.LIVE

        # Simulate staleness by setting last_tick_received_at to 30 seconds ago
        mgr.last_tick_received_at = time.time() - 35
        stale_eval = await mgr.evaluate_freshness()
        assert stale_eval == ConnectionState.STALE

    asyncio.run(_test())


def test_duplicate_subscription_prevention(temp_db):
    """Verify that redundant subscription requests are filtered out before sending."""
    mgr = ConnectionManager(provider_name="UPSTOX")

    # First subscription
    new_keys = mgr.record_subscription(["NSE_EQ|INE040A01034", "NSE_EQ|INE090A01021"])
    assert len(new_keys) == 2

    # Second subscription with overlapping key
    duplicate_attempt = mgr.record_subscription(["NSE_EQ|INE040A01034"])
    assert duplicate_attempt == []  # Filtered out!
