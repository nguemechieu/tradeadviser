from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from paper_learning.models import PaperSignalSnapshot, coerce_datetime, coerce_float, normalize_side
from quant.feature_pipeline import FeaturePipeline
from quant.ml_dataset import MLDatasetBuilder


class PaperTradeFeatureExtractor:
    """Produces training-consistent feature snapshots from live signal context."""

    DEFAULT_FEATURE_COLUMNS = list(MLDatasetBuilder.DEFAULT_FEATURE_COLUMNS)

    def __init__(self, feature_pipeline=None, feature_columns=None):
        self.feature_pipeline = feature_pipeline or FeaturePipeline()
        self.feature_columns = list(feature_columns or self.DEFAULT_FEATURE_COLUMNS)

    def build_signal_snapshot(self, context):
        working = dict(context or {})
        signal = dict(working.get("signal") or {})
        side = normalize_side(signal.get("side") or signal.get("signal"))
        if side is None:
            return None

        decision_id = str(signal.get("decision_id") or working.get("decision_id") or uuid4().hex).strip() or uuid4().hex
        symbol = str(signal.get("symbol") or working.get("symbol") or "").strip().upper()
        if not symbol:
            return None

        feature_frame = self._resolve_feature_frame(working)
        feature_values, feature_version, feature_timestamp, row_regime = self._latest_feature_values(feature_frame)
        regime_snapshot = dict(working.get("regime_snapshot") or {})
        signal_timestamp = coerce_datetime(
            signal.get("timestamp") or working.get("timestamp") or feature_timestamp,
            datetime.now(timezone.utc),
        )

        return PaperSignalSnapshot(
            decision_id=decision_id,
            symbol=symbol,
            signal=side,
            timeframe=str(signal.get("timeframe") or working.get("timeframe") or "1h").strip() or "1h",
            strategy_name=str(signal.get("strategy_name") or "").strip() or None,
            source=str(signal.get("source") or working.get("source") or "bot").strip().lower() or "bot",
            exchange=str(working.get("exchange") or signal.get("exchange") or "paper").strip().lower() or "paper",
            confidence=coerce_float(signal.get("confidence"), None),
            signal_price=coerce_float(signal.get("price"), None),
            signal_timestamp=signal_timestamp,
            feature_values=feature_values,
            feature_version=feature_version,
            market_regime=str(
                regime_snapshot.get("regime")
                or row_regime
                or signal.get("regime")
                or "unknown"
            ).strip()
            or "unknown",
            volatility_regime=str(
                regime_snapshot.get("volatility")
                or self._volatility_label(feature_values.get("atr_pct"))
                or "unknown"
            ).strip()
            or "unknown",
            regime_snapshot=regime_snapshot,
            metadata={
                "reason": str(signal.get("reason") or "").strip() or None,
                "signal_price": coerce_float(signal.get("price"), None),
                "signal_source_agent": str(signal.get("signal_source_agent") or "").strip() or None,
                "consensus_status": str(signal.get("consensus_status") or "").strip() or None,
            },
        )

    def _resolve_feature_frame(self, context):
        frames = []
        features = context.get("features")
        if isinstance(features, pd.DataFrame) and not features.empty:
            frames.append(features)

        dataset = context.get("dataset")
        dataset_frame = getattr(dataset, "frame", None)
        if isinstance(dataset_frame, pd.DataFrame) and not dataset_frame.empty:
            frames.append(dataset_frame)

        for frame in frames:
            normalized = self._ensure_feature_frame(frame)
            if normalized is not None and not normalized.empty:
                return normalized

        candles = list(context.get("candles") or [])
        if not candles and dataset is not None and hasattr(dataset, "to_candles"):
            try:
                candles = dataset.to_candles()
            except Exception:
                candles = []
        if not candles:
            return pd.DataFrame()
        return self.feature_pipeline.compute(candles)

    def _ensure_feature_frame(self, frame):
        if frame is None or getattr(frame, "empty", True):
            return pd.DataFrame()
        columns = {str(column) for column in getattr(frame, "columns", [])}
        if any(column in columns for column in self.feature_columns):
            return frame.copy()
        return self.feature_pipeline.compute(frame)

    def _latest_feature_values(self, frame):
        if frame is None or getattr(frame, "empty", True):
            return {}, self.feature_pipeline.FEATURE_VERSION, datetime.now(timezone.utc), None
        row = frame.iloc[-1]
        feature_values = {}
        for column in self.feature_columns:
            feature_values[column] = coerce_float(row.get(column), 0.0) or 0.0
        feature_version = str(row.get("feature_version") or self.feature_pipeline.FEATURE_VERSION).strip() or self.feature_pipeline.FEATURE_VERSION
        timestamp = coerce_datetime(row.get("timestamp"), datetime.now(timezone.utc))
        regime = str(row.get("regime") or "").strip() or None
        return feature_values, feature_version, timestamp, regime

    def _volatility_label(self, atr_pct):
        value = coerce_float(atr_pct, 0.0) or 0.0
        if value >= 0.03:
            return "high"
        return "medium" if value >= 0.015 else "low"
