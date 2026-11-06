from . import MarketDataFeedV3_pb2 as pb
from typing import Optional


def decode_feed_response(binary_data: bytes) -> pb.FeedResponse:
    """
    Decodes a binary Protobuf message received from Upstox Market Data Feed V3.
    """
    response = pb.FeedResponse()
    response.ParseFromString(binary_data)
    return response


__all__ = [
    "pb",
    "decode_feed_response",
]

