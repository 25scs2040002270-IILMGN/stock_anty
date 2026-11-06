import pytest
from app.market_data.protobuf import decode_feed_response, pb
from app.market_data.providers.upstox_provider import UpstoxMarketDataProvider


def create_synthetic_upstox_protobuf_fixture(
    instrument_key: str = "NSE_EQ|INE040A01034",
    ltp: float = 1525.75,
    timestamp_ms: int = 1730800000000,
    ltq: int = 100,
    volume: int = 2500000
) -> bytes:
    """
    [SYNTHETIC TEST FIXTURE]
    Constructs a valid Upstox V3 Market Data Feed Protobuf binary payload.
    Clearly labeled as TEST DATA.
    """
    feed_response = pb.FeedResponse()
    feed_response.type = pb.Type.live_feed
    feed_response.currentTs = timestamp_ms

    feed = feed_response.feeds[instrument_key]
    mff = feed.fullFeed.marketFF
    mff.ltpc.ltp = ltp
    mff.ltpc.ltt = timestamp_ms
    mff.ltpc.ltq = ltq
    mff.ltpc.cp = 1520.0
    mff.atp = 1523.50
    mff.vtt = volume

    # Add OHLC
    ohlc = mff.marketOHLC.ohlc.add()
    ohlc.open = 1520.0
    ohlc.high = 1530.0
    ohlc.low = 1518.0
    ohlc.close = ltp
    ohlc.volume = volume
    ohlc.ts = timestamp_ms

    # Add top 2 bids/asks
    q1 = mff.marketLevel.bidAskQuote.add()
    q1.bidP = ltp - 0.05
    q1.bidQ = 500
    q1.bidOrders = 3
    q1.askP = ltp + 0.05
    q1.askQ = 450
    q1.askOrders = 2

    return feed_response.SerializeToString()


def test_protobuf_decoding():
    """Verify that binary Protobuf payload decodes correctly."""
    binary_payload = create_synthetic_upstox_protobuf_fixture()
    decoded = decode_feed_response(binary_payload)

    assert decoded.type == pb.Type.live_feed
    assert "NSE_EQ|INE040A01034" in decoded.feeds
    feed = decoded.feeds["NSE_EQ|INE040A01034"]
    assert feed.fullFeed.marketFF.ltpc.ltp == 1525.75
    assert feed.fullFeed.marketFF.vtt == 2500000
    assert len(feed.fullFeed.marketFF.marketLevel.bidAskQuote) == 1


def test_market_feed_normalization(temp_db):
    """Verify that decoded protobuf feed is normalized into provider-independent MarketTick."""
    provider = UpstoxMarketDataProvider()
    binary_payload = create_synthetic_upstox_protobuf_fixture(
        instrument_key="NSE_EQ|INE040A01034",
        ltp=1525.75,
        timestamp_ms=1730800000000,
        ltq=100,
        volume=2500000
    )
    decoded = decode_feed_response(binary_payload)
    feed = decoded.feeds["NSE_EQ|INE040A01034"]

    tick = provider._normalize_protobuf_feed("NSE_EQ|INE040A01034", "HDFCBANK", feed)
    assert tick is not None
    assert tick.symbol == "HDFCBANK"
    assert tick.instrument_key == "NSE_EQ|INE040A01034"
    assert tick.ltp == 1525.75
    assert tick.exchange_timestamp == 1730800000000
    assert tick.last_traded_quantity == 100
    assert tick.cumulative_volume == 2500000
    assert tick.provider == "UPSTOX"
    assert tick.data_status == "LIVE"
    assert len(tick.bids) == 1
    assert tick.bids[0].price == 1525.70
    assert tick.bids[0].quantity == 500
    assert len(tick.asks) == 1
    assert tick.asks[0].price == 1525.80
    assert tick.asks[0].quantity == 450

