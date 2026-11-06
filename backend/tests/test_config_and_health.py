import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.config.settings import Settings, settings
from app.main import app


def test_strict_instruments_policy():
    """Verify that only HDFCBANK and ICICIBANK are permitted and RELIANCE is strictly rejected."""
    # Allowed symbols
    s = Settings(SUPPORTED_INSTRUMENTS="HDFCBANK,ICICIBANK")
    assert s.instruments_list == ["HDFCBANK", "ICICIBANK"]

    # Attempting to configure RELIANCE must raise a ValueError
    with pytest.raises(ValueError, match="CRITICAL VIOLATION.*RELIANCE"):
        Settings(SUPPORTED_INSTRUMENTS="HDFCBANK,RELIANCE")

    # Attempting to configure any other symbol must raise ValueError
    with pytest.raises(ValueError, match="Unsupported instrument 'TCS'"):
        Settings(SUPPORTED_INSTRUMENTS="HDFCBANK,TCS")


def test_backend_health_endpoint():
    """Verify GET /api/health endpoint returns 200 with required structure."""
    async def _test():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert "market_open" in data
            assert "current_time_ist" in data
            assert data["supported_instruments"] == ["HDFCBANK", "ICICIBANK"]
            assert data["forbidden_instruments_enforced"] is True

    asyncio.run(_test())
