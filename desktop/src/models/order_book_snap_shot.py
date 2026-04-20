from dataclasses import dataclass, field
from typing import List, Tuple
import time


# (price, size)
OrderLevel = Tuple[float, float]


@dataclass(slots=True)
class OrderBookSnapshot:
    symbol: str

    bids: List[OrderLevel]  # sorted DESC (highest price first)
    asks: List[OrderLevel]  # sorted ASC (lowest price first)

    timestamp: float = field(default_factory=lambda: time.time())

    # =========================
    # Top of Book
    # =========================
    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0

    @property
    def spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.best_ask - self.best_bid

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.best_bid + self.best_ask) / 2

    # =========================
    # Liquidity Metrics
    # =========================
    def bid_volume(self, depth: int = 5) -> float:
        return sum(size for _, size in self.bids[:depth])

    def ask_volume(self, depth: int = 5) -> float:
        return sum(size for _, size in self.asks[:depth])

    def imbalance(self, depth: int = 5) -> float:
        bid_vol = self.bid_volume(depth)
        ask_vol = self.ask_volume(depth)
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total

    # =========================
    # Validation
    # =========================
    def is_valid(self) -> bool:
        if not self.bids or not self.asks:
            return False

        # bids descending, asks ascending
        bids_sorted = all(self.bids[i][0] >= self.bids[i+1][0] for i in range(len(self.bids)-1))
        asks_sorted = all(self.asks[i][0] <= self.asks[i+1][0] for i in range(len(self.asks)-1))

        return bids_sorted and asks_sorted and self.best_bid <= self.best_ask

    # =========================
    # Serialization
    # =========================
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bids": self.bids,
            "asks": self.asks,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrderBookSnapshot":
        return cls(
            symbol=data["symbol"],
            bids=[(float(p), float(s)) for p, s in data["bids"]],
            asks=[(float(p), float(s)) for p, s in data["asks"]],
            timestamp=float(data.get("timestamp", time.time())),
        )