import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.core.models import Candle, TradeFeedback
from sopotek.ml import (
    DEFAULT_FEATURE_COLUMNS,
    InferenceEngine,
    RetrainingScheduler,
    TradeDatasetBuilder,
    TradeOutcomeTrainingPipeline,
    build_features,
    build_trade_dataset,
    compute_indicator_features,
)


def _candles(symbol: str = "BTC/USDT") -> list[Candle]:
    rows = []
    price = 100.0
    for index in range(40):
        open_ = price
        price = price + 0.6
        rows.append(
            Candle(
                symbol=symbol,
                timeframe="1m",
                open=open_,
                high=price + 0.3,
                low=open_ - 0.3,
                close=price,
                volume=100.0 + index * 4.0,
            )
        )
    return rows


def _feedback_rows() -> list[TradeFeedback]:
    rows = []
    for index in range(18):
        rows.append(
            TradeFeedback(
                symbol=f"WIN-{index}",
                strategy_name="trend_following",
                side="buy",
                quantity=1.0,
                entry_price=100.0,
                exit_price=103.0,
                pnl=3.0,
                success=True,
                features={
                    "rsi": 62.0 + index,
                    "ema_fast": 102.0 + index * 0.2,
                    "ema_slow": 100.5 + index * 0.1,
                    "volatility": 0.01,
                    "ema_gap": 0.025 + index * 0.001,
                    "zscore": 0.4,
                    "volume_ratio": 1.35,
                },
            )
        )
        rows.append(
            TradeFeedback(
                symbol=f"LOSS-{index}",
                strategy_name="trend_following",
                side="sell",
                quantity=1.0,
                entry_price=100.0,
                exit_price=103.0,
                pnl=-3.0,
                success=False,
                features={
                    "rsi": 32.0 - index,
                    "ema_fast": 98.0 - index * 0.2,
                    "ema_slow": 100.0 - index * 0.05,
                    "volatility": 0.05,
                    "ema_gap": -0.025 - index * 0.001,
                    "zscore": -1.8,
                    "volume_ratio": 0.8,
                },
            )
        )
    return rows


def test_feature_engineering_builds_expected_columns():
    frame = pd.DataFrame(
        {
            "open": [candle.open for candle in _candles()],
            "high": [candle.high for candle in _candles()],
            "low": [candle.low for candle in _candles()],
            "close": [candle.close for candle in _candles()],
            "volume": [candle.volume for candle in _candles()],
        }
    )

    enriched = build_features(frame, dropna=False)
    latest = compute_indicator_features(_candles())

    assert set(DEFAULT_FEATURE_COLUMNS).issubset(enriched.columns)
    assert 0.0 <= latest["rsi"] <= 100.0
    assert latest["ema_fast"] > latest["ema_slow"]
    assert latest["volatility"] >= 0.0


def test_build_trade_dataset_creates_binary_target_from_prices():
    trades = pd.DataFrame(
        [
            {"entry_price": 100.0, "exit_price": 103.0, "rsi": 60.0, "ema_fast": 101.0, "ema_slow": 99.0, "volatility": 0.01},
            {"entry_price": 100.0, "exit_price": 97.0, "rsi": 35.0, "ema_fast": 98.0, "ema_slow": 101.0, "volatility": 0.05},
        ]
    )

    dataset = build_trade_dataset(trades, feature_columns=["rsi", "ema_fast", "ema_slow", "volatility"])

    assert list(dataset.columns) == ["rsi", "ema_fast", "ema_slow", "volatility", "target"]
    assert dataset["target"].tolist() == [1, 0]


def test_trade_dataset_builder_and_pipeline_round_trip(tmp_path):
    rows = _feedback_rows()
    builder = TradeDatasetBuilder()
    dataset = builder.build_dataset(rows)
    pipeline = TradeOutcomeTrainingPipeline(model_name="unit_trade_model", model_dir=tmp_path)

    report = pipeline.fit_from_feedback(rows, model_family="tree")
    loaded = TradeOutcomeTrainingPipeline(model_name="unit_trade_model", model_dir=tmp_path).load_active()

    positive_features = rows[0].features
    negative_features = rows[1].features

    assert dataset.frame["target"].sum() == len(dataset.frame) // 2
    assert {"rsi", "ema_fast", "ema_slow", "volatility"}.issubset(set(dataset.feature_columns))
    assert report.sample_count == len(dataset.frame)
    assert report.metrics["accuracy"] >= 0.7
    assert pipeline.predict_probability(positive_features) > pipeline.predict_probability(negative_features)
    assert loaded.predict_probability(positive_features) == pytest.approx(pipeline.predict_probability(positive_features))


def test_inference_engine_threshold_and_scheduler(tmp_path):
    pipeline = TradeOutcomeTrainingPipeline(model_name="scheduler_model", model_dir=tmp_path)
    pipeline.fit_from_feedback(_feedback_rows(), model_family="tree")
    engine = InferenceEngine(pipeline.model_path, threshold=0.6)

    calls = []
    scheduler = RetrainingScheduler(lambda: calls.append("trained"), interval_hours=0.01, sleep_fn=lambda _seconds: None)
    scheduler.run_once()

    assert engine.is_ready is True
    assert engine.should_trade({"rsi": 70.0, "ema_fast": 103.0, "ema_slow": 100.0, "volatility": 0.01, "ema_gap": 0.03, "zscore": 0.5, "volume_ratio": 1.4}) is True
    assert calls == ["trained"]
