from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class DatasetRequest:
    symbol: str
    timeframe: str = "1h"
    limit: int = 300
    exchange: str | None = None
    prefer_live: bool = True


@dataclass
class SymbolDatasetSnapshot:
    symbol: str
    timeframe: str
    exchange: str | None
    source: str
    frame: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.frame is None or self.frame.empty

    @property
    def rows(self) -> int:
        return 0 if self.empty else int(len(self.frame))

    def to_candles(self):
        if self.empty:
            return []
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        if any(column not in self.frame.columns for column in required):
            return []
        return self.frame[required].values.tolist()
