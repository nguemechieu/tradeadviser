from quant.feature_pipeline import FeaturePipeline, FeaturePipelineConfig
from quant.signal_schema import SignalDecision


def _sample_candles(count=30):
    base = 1700000000000
    candles = []
    close = 100.0
    for index in range(count):
        open_ = close
        close = close + (0.4 if index % 3 else 0.9)
        high = max(open_, close) + 0.5
        low = min(open_, close) - 0.5
        volume = 100 + (index * 3)
        candles.append([base + index * 3600000, open_, high, low, close, volume])
    return candles


def test_feature_pipeline_generates_quant_features():
    pipeline = FeaturePipeline()

    df = pipeline.compute(_sample_candles(), FeaturePipelineConfig(rsi_period=5, ema_fast=4, ema_slow=8, atr_period=4))

    assert not df.empty
    assert {"return_1", "return_5", "regime", "feature_version", "macd_hist", "volume_ratio"}.issubset(df.columns)
    assert df.iloc[-1]["feature_version"] == "quant-v1"


def test_signal_decision_to_dict_preserves_schema():
    signal = SignalDecision(
        side="buy",
        amount=1.5,
        confidence=0.72,
        reason="Quant feature stack aligned",
        price=101.25,
        regime="trending_up",
        metadata={"model_name": "ensemble_v1"},
    ).to_dict()

    assert signal["side"] == "buy"
    assert signal["amount"] == 1.5
    assert signal["confidence"] == 0.72
    assert signal["regime"] == "trending_up"
    assert signal["feature_version"] == "quant-v1"
    assert signal["model_name"] == "ensemble_v1"
