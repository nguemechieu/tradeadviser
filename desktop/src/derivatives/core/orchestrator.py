from __future__ import annotations

import importlib
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

from derivatives.core.config import BrokerConfig, DerivativesSystemConfig
from derivatives.core.event_bus import EventBus
from derivatives.core.symbols import SymbolRegistry
from derivatives.data.live_cache.cache import LiveMarketCache
from derivatives.engine.backtest_engine import BacktestEngine
from derivatives.engine.execution_engine import ExecutionEngine
from derivatives.engine.market_data_engine import MarketDataEngine
from derivatives.engine.portfolio_engine import PortfolioEngine
from derivatives.engine.risk_engine import RiskEngine
from derivatives.engine.strategy_engine import StrategyEngine
from derivatives.ml.inference_engine import DerivativesInferenceEngine
from derivatives.ml.training_pipeline.trainer import DerivativesTrainingPipeline


class _PaperController:
    def __init__(self, broker_cfg: BrokerConfig, *, starting_equity: float) -> None:
        runtime_broker = SimpleNamespace(
            exchange=broker_cfg.exchange or "paper",
            type=broker_cfg.type,
            account_id=broker_cfg.account_id,
            options=dict(broker_cfg.options or {}),
            params=dict(broker_cfg.params or {}),
        )
        self.config = SimpleNamespace(broker=runtime_broker)
        self.paper_balance = float(starting_equity)
        self.initial_balance = float(starting_equity)
        self.mode = "paper"
        self.params = dict(broker_cfg.params or {})
        self.symbols = list(broker_cfg.symbols or [])
        self.exchange = broker_cfg.exchange or "paper"
        self.paper_data_exchange = self.params.get("paper_data_exchange") or self.exchange


class DerivativesOrchestrator:
    DEFAULT_BROKER_TARGETS = {
        "coinbase": "broker.coinbase_futures.client:CoinbaseFuturesBroker",
        "coinbase_futures": "broker.coinbase_futures.client:CoinbaseFuturesBroker",
        "binance": "broker.binance_futures.client:BinanceFuturesBroker",
        "binance_futures": "broker.binance_futures.client:BinanceFuturesBroker",
        "bybit": "broker.bybit.client:BybitBroker",
        "ibkr": "broker.ibkr_broker:IBKRBroker",
        "interactivebrokers": "broker.ibkr_broker:IBKRBroker",
        "tradovate": "broker.tradovate_broker:TradovateBroker",
        "paper": "broker.paper_broker:PaperBroker",
    }

    def __init__(self, config: DerivativesSystemConfig | dict[str, Any] | None = None, *, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("DerivativesOrchestrator")
        self.config = config if isinstance(config, DerivativesSystemConfig) else DerivativesSystemConfig.model_validate(config or {})
        self.bus = EventBus(logger=logging.getLogger("DerivativesEventBus"))
        self.cache = LiveMarketCache(window_size=int(self.config.engine.history_window))
        self.symbol_registry = SymbolRegistry()
        self.inference_engine = DerivativesInferenceEngine(self.config.ml)
        self.training_pipeline = DerivativesTrainingPipeline(self.config.ml)
        self.backtest_engine = BacktestEngine(starting_equity=self.config.starting_equity, config=self.config.engine)
        self.brokers: dict[str, Any] = {}
        self.market_data_engine: MarketDataEngine | None = None
        self.strategy_engine: StrategyEngine | None = None
        self.risk_engine: RiskEngine | None = None
        self.execution_engine: ExecutionEngine | None = None
        self.portfolio_engine: PortfolioEngine | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self._load_brokers()
        self._build_engines()
        self._load_ml_bundle_if_available()
        self.strategy_engine.load_plugins()
        self.bus.run_in_background()
        await self.market_data_engine.start(symbols=self.config.strategy.symbols or None)
        self._started = True
        self.logger.info("derivatives_orchestrator_started brokers=%s", list(self.brokers))

    async def stop(self) -> None:
        if not self._started:
            return
        if self.market_data_engine is not None:
            await self.market_data_engine.stop()
        for broker_key, broker in list(self.brokers.items()):
            try:
                await broker.close()
            except Exception:
                self.logger.exception("broker_close_failed broker=%s", broker_key)
        await self.bus.shutdown()
        self._started = False
        self.logger.info("derivatives_orchestrator_stopped")

    async def train_models(self, data: Any, *, output_dir: str | None = None) -> dict[str, Any]:
        frame = self._combine_training_data(data)
        return self.training_pipeline.train(frame, output_dir=output_dir)

    def load_models(self, model_path: str | None = None) -> DerivativesInferenceEngine:
        self.inference_engine.load(model_path)
        return self.inference_engine

    def run_backtest(self, strategy_name: str, data: Any, *, symbol: str):
        if self.strategy_engine is None:
            self._build_engines()
            self.strategy_engine.load_plugins()
        strategy = next(
            (item for item in self.strategy_engine.strategies if item.name == strategy_name or item.__class__.__name__ == strategy_name),
            None,
        )
        if strategy is None:
            raise KeyError(f"Unknown strategy: {strategy_name}")
        return self.backtest_engine.run(strategy, data, symbol=symbol)

    async def publish(self, topic: str, data: Any, *, source: str = "orchestrator") -> None:
        await self.bus.publish(topic, data, source=source)

    async def _load_brokers(self) -> None:
        if self.brokers:
            return
        for broker_cfg in self.config.brokers:
            broker = self._instantiate_broker(broker_cfg)
            if hasattr(broker, "priority"):
                broker.priority = broker_cfg.priority
            else:
                setattr(broker, "priority", broker_cfg.priority)
            await broker.connect()
            broker_key = self._broker_key(broker_cfg)
            self.brokers[broker_key] = broker

    def _build_engines(self) -> None:
        if self.market_data_engine is not None:
            return
        self.market_data_engine = MarketDataEngine(
            self.bus,
            self.cache,
            self.symbol_registry,
            self.brokers,
            config=self.config.engine,
        )
        self.strategy_engine = StrategyEngine(
            self.bus,
            self.cache,
            config=self.config.strategy,
            inference_engine=self.inference_engine,
        )
        self.portfolio_engine = PortfolioEngine(
            self.bus,
            self.cache,
            starting_equity=self.config.starting_equity,
            base_currency=self.config.base_currency,
        )
        self.risk_engine = RiskEngine(
            self.bus,
            self.cache,
            config=self.config.risk,
            starting_equity=self.config.starting_equity,
        )
        self.execution_engine = ExecutionEngine(
            self.bus,
            self.cache,
            self.symbol_registry,
            self.brokers,
            config=self.config.engine,
        )

    def _load_ml_bundle_if_available(self) -> None:
        bundle_path = Path(self.config.ml.model_dir) / "derivatives_model_bundle.joblib"
        if bundle_path.exists():
            try:
                self.inference_engine.load(bundle_path)
            except Exception:
                self.logger.exception("ml_bundle_load_failed path=%s", bundle_path)

    def _instantiate_broker(self, broker_cfg: BrokerConfig) -> Any:
        target = broker_cfg.broker_class or self._resolve_broker_target(broker_cfg)
        module_name, class_name = target.split(":", 1)
        broker_class = getattr(importlib.import_module(module_name), class_name)
        if class_name == "PaperBroker":
            controller = _PaperController(broker_cfg, starting_equity=self.config.starting_equity)
            return broker_class(controller)
        runtime_config = self._runtime_broker_config(broker_cfg)
        return broker_class(runtime_config)

    def _resolve_broker_target(self, broker_cfg: BrokerConfig) -> str:
        exchange = str(broker_cfg.exchange or "").strip().lower()
        broker_type = str(broker_cfg.type or "").strip().lower()
        if exchange in self.DEFAULT_BROKER_TARGETS:
            return self.DEFAULT_BROKER_TARGETS[exchange]
        if broker_type == "paper":
            return self.DEFAULT_BROKER_TARGETS["paper"]
        if broker_type in {"future", "futures", "derivative", "derivatives"}:
            return self.DEFAULT_BROKER_TARGETS.get(exchange, "broker.ibkr_broker:IBKRBroker")
        raise ValueError(f"Unsupported broker configuration: exchange={broker_cfg.exchange} type={broker_cfg.type}")

    def _runtime_broker_config(self, broker_cfg: BrokerConfig):
        return SimpleNamespace(
            exchange=broker_cfg.exchange,
            type=broker_cfg.type,
            api_key=broker_cfg.api_key,
            secret=broker_cfg.secret,
            password=broker_cfg.password,
            passphrase=broker_cfg.password,
            uid=None,
            account_id=broker_cfg.account_id,
            wallet=None,
            mode=broker_cfg.mode,
            sandbox=broker_cfg.mode in {"paper", "sandbox", "testnet"},
            timeout=int(broker_cfg.timeout_seconds * 1000),
            timeout_seconds=broker_cfg.timeout_seconds,
            max_retries=broker_cfg.max_retries,
            rate_limit_per_second=broker_cfg.rate_limit_per_second,
            options=dict(broker_cfg.options or {}),
            params={**dict(broker_cfg.params or {}), "symbols": list(broker_cfg.symbols or [])},
        )

    @staticmethod
    def _broker_key(broker_cfg: BrokerConfig) -> str:
        account = str(broker_cfg.account_id or "default").strip()
        exchange = str(broker_cfg.exchange or broker_cfg.name).strip().lower()
        return f"{broker_cfg.name}:{exchange}:{account}"

    @staticmethod
    def _combine_training_data(data: Any) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, dict):
            frames = [pd.DataFrame(value).assign(symbol=str(key)) for key, value in data.items()]
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return pd.DataFrame(data)
