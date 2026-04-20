import math

import pytest

from quant.ml_dataset import MLDatasetBuilder
from quant.ml_research import MLResearchPipeline
from quant.model_registry import ModelRegistry
from quant.signal_engine import SignalEngine
from strategy.strategy_registry import StrategyRegistry


def _sample_ml_candles():
    base = 1700000000000
    candles = []
    close = 100.0
    for index in range(180):
        drift = 0.22 if (index % 24) < 14 else -0.12
        wave = math.sin(index / 5.0) * 0.18
        close = max(20.0, close + drift + wave)
        open_ = close - (0.12 if index % 2 == 0 else -0.08)
        high = max(open_, close) + 0.35
        low = min(open_, close) - 0.35
        volume = 100 + (index % 11) * 7 + abs(wave) * 45
        candles.append([base + index * 3600000, open_, high, low, close, volume])
    return candles


def test_ml_research_pipeline_trains_registers_and_deploys():
    candles = _sample_ml_candles()
    dataset = MLDatasetBuilder().build_from_candles(
        candles,
        horizon=3,
        return_threshold=0.0005,
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert not dataset.empty
    assert len(dataset.feature_columns) >= 5

    registry = ModelRegistry()
    pipeline = MLResearchPipeline(model_registry=registry)
    result = pipeline.train_classifier(
        dataset,
        model_name="phase9_ml_model",
        experiment_name="phase9_ml_research",
    )

    assert result.model_name == "phase9_ml_model"
    assert result.metrics["train_samples"] > 0
    assert result.metrics["test_samples"] > 0
    assert registry.get("phase9_ml_model") is not None
    assert registry.get_metadata("phase9_ml_model")["model_family"] == "linear"
    assert not pipeline.experiment_tracker.to_frame().empty

    strategy_registry = StrategyRegistry()
    deployed = pipeline.deploy_to_strategy_registry(strategy_registry, "phase9_ml_model", strategy_name="ML Model")
    deployed.min_confidence = 0.0

    engine = SignalEngine(strategy_registry)
    signal = engine.generate_signal(
        candles=candles,
        strategy_name="ML Model",
        symbol="BTC/USDT",
    )

    assert signal is not None
    assert signal["side"] in {"buy", "sell"}
    assert signal["strategy_name"] == "ML Model"
    assert signal["model_name"] == "phase9_ml_model"


def test_ml_research_supports_tree_and_sequence_families_and_walk_forward():
    candles = _sample_ml_candles()
    pipeline = MLResearchPipeline()
    dataset = pipeline.build_dataset(
        candles,
        horizon=2,
        return_threshold=0.0005,
        symbol="ETH/USDT",
        timeframe="4h",
    )

    tree_result = pipeline.train_classifier(
        dataset,
        model_name="tree_family_model",
        model_family="tree",
        experiment_name="tree_family_run",
    )
    assert tree_result.dataset_metadata["model_family"] == "tree"
    assert pipeline.model_registry.get("tree_family_model") is not None

    sequence_result = pipeline.train_classifier(
        dataset,
        model_name="sequence_family_model",
        model_family="sequence",
        sequence_length=4,
        experiment_name="sequence_family_run",
    )
    assert sequence_result.dataset_metadata["model_family"] == "sequence"
    assert pipeline.model_registry.get("sequence_family_model") is not None

    walk_summary, walk_predictions = pipeline.run_walk_forward(
        dataset,
        model_family="sequence",
        sequence_length=4,
        train_size=40,
        test_size=20,
    )
    assert not walk_summary.empty
    assert not walk_predictions.empty
    assert {"accuracy", "precision", "recall"}.issubset(walk_summary.columns)


def test_ml_research_auto_research_ranks_candidates_and_picks_best_model():
    candles = _sample_ml_candles()
    pipeline = MLResearchPipeline()
    dataset = pipeline.build_dataset(
        candles,
        horizon=2,
        return_threshold=0.0005,
        symbol="SOL/USDT",
        timeframe="1h",
    )

    summary = pipeline.auto_research(
        dataset,
        model_families=["linear", "tree", "sequence"],
        sequence_length=4,
        test_size=0.25,
        train_size=40,
        test_window=20,
        model_name_prefix="auto_lab",
        candidate_sequence_lengths=[3, 4],
    )

    assert summary.best_candidate is not None
    assert len(summary.candidates) == 4
    assert not summary.leaderboard.empty
    assert summary.leaderboard.iloc[0]["model_name"] == summary.best_candidate.model_name
    assert summary.leaderboard.iloc[0]["model_family"] == summary.best_candidate.model_family
    assert summary.leaderboard.iloc[0]["selection_score"] == pytest.approx(summary.best_candidate.selection_score)
    assert {"selection_score", "walk_forward_accuracy", "test_accuracy", "model_family"}.issubset(summary.leaderboard.columns)

    candidate_names = {candidate.model_name for candidate in summary.candidates}
    assert candidate_names.issubset(set(pipeline.model_registry.list()))
    assert not summary.best_candidate.walk_summary.empty
