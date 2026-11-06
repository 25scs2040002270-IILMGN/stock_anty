import asyncio
import pytest
from app.market_data.providers.upstox_instrument_resolver import UpstoxInstrumentResolver
from app.config.settings import settings


def test_resolve_instruments_success(temp_db):
    """Verify that HDFCBANK and ICICIBANK resolve correctly with official keys."""
    async def _test():
        resolver = UpstoxInstrumentResolver()
        resolved = await resolver.resolve_instruments()

        assert "HDFCBANK" in resolved
        assert "ICICIBANK" in resolved

        hdfc = resolved["HDFCBANK"]
        assert hdfc.instrument_key == "NSE_EQ|INE040A01034"
        assert hdfc.exchange in ("NSE_EQ", "NSE")
        assert hdfc.instrument_type == "EQ"
        assert hdfc.is_active is True

        icici = resolved["ICICIBANK"]
        assert icici.instrument_key == "NSE_EQ|INE090A01021"
        assert icici.exchange in ("NSE_EQ", "NSE")
        assert icici.instrument_type == "EQ"

        # Verify saved in database
        db_instruments = temp_db.get_instruments(active_only=True)
        symbols_in_db = [i["trading_symbol"] for i in db_instruments]
        assert "HDFCBANK" in symbols_in_db
        assert "ICICIBANK" in symbols_in_db
        assert "RELIANCE" not in symbols_in_db

    asyncio.run(_test())


def test_resolve_instruments_forbids_prohibited(temp_db, monkeypatch):
    """Verify that resolver refuses to resolve RELIANCE."""
    async def _test():
        resolver = UpstoxInstrumentResolver()
        monkeypatch.setattr(settings, "FORBIDDEN_INSTRUMENTS_SET", {"RELIANCE"})
        monkeypatch.setattr(settings, "SUPPORTED_INSTRUMENTS", "HDFCBANK,RELIANCE")

        with pytest.raises(ValueError, match="CRITICAL VIOLATION"):
            await resolver.resolve_instruments()

    asyncio.run(_test())
