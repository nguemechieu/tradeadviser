from dataclasses import dataclass, field

import pandas as pd

from quant.feature_pipeline import FeaturePipeline, FeaturePipelineConfig


@dataclass
class MLDataset:
    frame: pd.DataFrame
    feature_columns: list[str]
    target_column: str
    metadata: dict = field(default_factory=dict)

    @property
    def empty(self):
        return self.frame is None or self.frame.empty

    def features(self):
        if self.empty:
            return pd.DataFrame(columns=self.feature_columns)
        return self.frame[self.feature_columns].copy()

    def labels(self):
        if self.empty:
            return pd.Series(dtype=int)
        return self.frame[self.target_column].astype(int).copy()

    def train_test_split(self, test_size=0.25):
        if self.empty:
            return self.frame.copy(), self.frame.copy()
        total = len(self.frame)
        split_index = max(1, min(total - 1, int(round(total * (1.0 - float(test_size))))))
        return self.frame.iloc[:split_index].copy(), self.frame.iloc[split_index:].copy()

    def to_sequence_dataset(self, sequence_length=4):
        if self.empty:
            return MLDataset(pd.DataFrame(), [], self.target_column, metadata=dict(self.metadata or {}))

        sequence_length = max(2, int(sequence_length))
        rows = []
        index_labels = list(self.frame.index)
        for end in range(sequence_length - 1, len(self.frame)):
            window = self.frame.iloc[end - sequence_length + 1 : end + 1]
            if len(window) < sequence_length:
                continue
            flattened = {}
            for step_idx, (_, row) in enumerate(window.iterrows()):
                suffix = f"_t-{sequence_length - step_idx - 1}"
                for column in self.feature_columns:
                    flattened[f"{column}{suffix}"] = row[column]
            latest_row = self.frame.iloc[end]
            flattened[self.target_column] = int(latest_row[self.target_column])
            flattened["timestamp"] = latest_row.get("timestamp")
            flattened["regime"] = latest_row.get("regime")
            flattened["feature_version"] = latest_row.get("feature_version")
            rows.append(flattened)

        sequence_frame = pd.DataFrame(rows)
        sequence_features = [
            column
            for column in sequence_frame.columns
            if column not in {self.target_column, "timestamp", "regime", "feature_version"}
        ]
        metadata = dict(self.metadata or {})
        metadata["sequence_length"] = sequence_length
        metadata["samples"] = len(sequence_frame)
        return MLDataset(sequence_frame, sequence_features, self.target_column, metadata=metadata)


class MLDatasetBuilder:
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
    ]

    def __init__(self, feature_pipeline=None):
        self.feature_pipeline = feature_pipeline or FeaturePipeline()

    def build_from_candles(
        self,
        candles,
        horizon=3,
        return_threshold=0.0015,
        feature_columns=None,
        config=None,
        symbol=None,
        timeframe="1h",
    ):
        features = self.feature_pipeline.compute(candles, config or FeaturePipelineConfig())
        if features is None or features.empty:
            return MLDataset(pd.DataFrame(), [], "target", metadata={"symbol": symbol, "timeframe": timeframe})

        frame = features.copy()
        horizon_steps = max(1, int(horizon))
        threshold = abs(float(return_threshold or 0.0))
        frame["future_return"] = (frame["close"].shift(-horizon_steps) / frame["close"]) - 1.0
        frame["target"] = (frame["future_return"] > threshold).astype(int)
        frame["future_move_abs"] = frame["future_return"].abs()
        if threshold > 0:
            frame = frame.loc[frame["future_move_abs"] >= threshold].copy()
        frame.dropna(inplace=True)

        selected = [
            column
            for column in (feature_columns or self.DEFAULT_FEATURE_COLUMNS)
            if column in frame.columns
        ]
        if not selected:
            return MLDataset(pd.DataFrame(), [], "target", metadata={"symbol": symbol, "timeframe": timeframe})

        dataset_frame = frame[selected + ["target", "future_return", "regime", "feature_version", "timestamp"]].copy()
        metadata = {
            "symbol": symbol,
            "timeframe": timeframe,
            "horizon": horizon_steps,
            "return_threshold": threshold,
            "samples": len(dataset_frame),
            "feature_version": str(dataset_frame["feature_version"].iloc[-1]) if not dataset_frame.empty else FeaturePipeline.FEATURE_VERSION,
        }
        return MLDataset(dataset_frame, selected, "target", metadata=metadata)
