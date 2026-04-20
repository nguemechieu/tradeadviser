from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant.ml_dataset import MLDataset


class PaperTradeDatasetBuilder:
    """Builds ML-ready supervised datasets from persisted paper trade records."""

    DEFAULT_FEATURE_COLUMNS = [
        "rsi",
        "ema_fast",
        "ema_slow",
        "atr",
        "volume",
        "return_1",
        "return_5",
        "volume_ratio",
        "momentum",
        "macd_line",
        "macd_signal",
        "macd_hist",
        "atr_pct",
        "trend_strength",
        "pullback_gap",
        "band_position",
        "confidence",
        "signal_is_buy",
    ]

    def __init__(self, repository=None, feature_columns=None):
        self.repository = repository
        self.feature_columns = list(feature_columns or self.DEFAULT_FEATURE_COLUMNS)

    def build_dataset(
        self,
        records=None,
        *,
        symbol=None,
        strategy_name=None,
        timeframe=None,
        exchange="paper",
        limit=5000,
    ):
        rows = list(records or [])
        if not rows and self.repository is not None:
            rows = list(
                self.repository.get_trade_records(
                    limit=limit,
                    symbol=symbol,
                    strategy_name=strategy_name,
                    timeframe=timeframe,
                    exchange=exchange,
                )
                or []
            )

        frame = self._records_to_frame(rows)
        if frame.empty:
            return MLDataset(
                pd.DataFrame(),
                [],
                "target",
                metadata={
                    "symbol": symbol,
                    "strategy_name": strategy_name,
                    "timeframe": timeframe,
                    "exchange": exchange,
                    "samples": 0,
                },
            )

        selected = [column for column in self.feature_columns if column in frame.columns]
        frame["target"] = (frame["outcome"].astype(str).str.upper() == "WIN").astype(int)
        dataset_frame = frame[
            selected
            + [
                "target",
                "timestamp",
                "symbol",
                "strategy_name",
                "timeframe",
                "market_regime",
                "volatility_regime",
                "feature_version",
                "pnl",
                "pnl_pct",
                "duration_seconds",
                "outcome",
                "entry_price",
                "exit_price",
            ]
        ].copy()

        metadata = {
            "symbol": symbol,
            "strategy_name": strategy_name,
            "timeframe": timeframe,
            "exchange": exchange,
            "samples": len(dataset_frame),
            "feature_version": str(dataset_frame["feature_version"].iloc[-1]) if not dataset_frame.empty else None,
        }
        return MLDataset(dataset_frame, selected, "target", metadata=metadata)

    def export_csv(self, path, records=None, **filters):
        dataset = self.build_dataset(records=records, **filters)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        dataset.frame.to_csv(target, index=False)
        return str(target)

    def _records_to_frame(self, rows):
        if not rows:
            return pd.DataFrame()

        normalized = []
        for row in rows:
            feature_values = self._feature_payload(getattr(row, "features_json", None))
            item = {
                "timestamp": self._datetime_value(getattr(row, "signal_timestamp", None))
                or self._datetime_value(getattr(row, "entry_timestamp", None))
                or self._datetime_value(getattr(row, "exit_timestamp", None)),
                "symbol": getattr(row, "symbol", None),
                "strategy_name": getattr(row, "strategy_name", None),
                "timeframe": getattr(row, "timeframe", None),
                "market_regime": getattr(row, "market_regime", None),
                "volatility_regime": getattr(row, "volatility_regime", None),
                "feature_version": getattr(row, "feature_version", None),
                "pnl": self._float_value(getattr(row, "pnl", None), 0.0),
                "pnl_pct": self._float_value(getattr(row, "pnl_pct", None), 0.0),
                "duration_seconds": self._float_value(getattr(row, "duration_seconds", None), 0.0),
                "outcome": str(getattr(row, "outcome", "") or "").upper() or "LOSS",
                "entry_price": self._float_value(getattr(row, "entry_price", None), 0.0),
                "exit_price": self._float_value(getattr(row, "exit_price", None), 0.0),
                "confidence": self._float_value(getattr(row, "confidence", None), 0.0),
                "signal_is_buy": 1 if str(getattr(row, "signal", "") or "").upper() == "BUY" else 0,
            }
            for column in self.feature_columns:
                if column in {"confidence", "signal_is_buy"}:
                    continue
                item[column] = self._float_value(feature_values.get(column, getattr(row, column, None)), 0.0)
            normalized.append(item)

        frame = pd.DataFrame(normalized)
        for column in self.feature_columns:
            if column not in frame.columns:
                frame[column] = 0.0
        return frame.dropna(subset=["timestamp"]).reset_index(drop=True)

    def _feature_payload(self, payload):
        if payload in (None, "", {}):
            return {}
        if isinstance(payload, dict):
            return dict(payload)
        if isinstance(payload, str):
            try:
                decoded = json.loads(payload)
                return dict(decoded) if isinstance(decoded, dict) else {}
            except Exception:
                return {}
        return {}

    def _datetime_value(self, value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        text = str(value).strip()
        return text or None

    def _float_value(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
