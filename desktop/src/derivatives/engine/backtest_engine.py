from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from typing import Any

import pandas as pd

from derivatives.core.config import EngineConfig
from derivatives.core.models import BacktestMetrics
from derivatives.engine.strategies import BaseStrategy
from derivatives.ml.feature_engineering.features import build_feature_frame


@dataclass(slots=True)
class _BacktestPosition:
    side: str
    size: float
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None


class BacktestEngine:
    def __init__(
        self,
        *,
        starting_equity: float = 100000.0,
        config: EngineConfig | None = None,
    ) -> None:
        self.starting_equity = float(starting_equity or 100000.0)
        self.config = config or EngineConfig()

    def run(self, strategy: BaseStrategy, data: Any, *, symbol: str) -> BacktestMetrics:
        frame = build_feature_frame(pd.DataFrame(data))
        if frame.empty:
            return BacktestMetrics(0, 0.0, 0.0, 0.0, self.starting_equity, [self.starting_equity])

        equity = self.starting_equity
        equity_curve = [equity]
        trades = 0
        wins = 0
        position: _BacktestPosition | None = None
        realized_returns: list[float] = []
        commission_rate = float(self.config.commission_bps) / 10_000.0
        slippage_rate = float(self.config.slippage_bps) / 10_000.0

        for index, row in frame.iterrows():
            price = float(row["close"])
            features = {column: float(row.get(column, 0.0) or 0.0) for column in frame.columns}
            history = frame.loc[:index, "close"].astype(float).tolist()

            if position is not None:
                hit_stop = position.stop_loss is not None and (
                    (position.side == "buy" and price <= position.stop_loss)
                    or (position.side == "sell" and price >= position.stop_loss)
                )
                hit_target = position.take_profit is not None and (
                    (position.side == "buy" and price >= position.take_profit)
                    or (position.side == "sell" and price <= position.take_profit)
                )
                if hit_stop or hit_target:
                    pnl = self._close_position(position, exit_price=price, commission_rate=commission_rate, slippage_rate=slippage_rate)
                    equity += pnl
                    trades += 1
                    wins += int(pnl > 0)
                    realized_returns.append(pnl / max(equity - pnl, 1.0))
                    position = None

            signal = strategy.evaluate(
                symbol=symbol,
                price=price,
                features=features,
                history=history,
                route=None,
                now=datetime.now(timezone.utc),
            )
            if signal is None:
                equity_curve.append(equity + (self._mark_to_market(position, price) if position else 0.0))
                continue

            if position is not None and signal.side != position.side:
                pnl = self._close_position(position, exit_price=price, commission_rate=commission_rate, slippage_rate=slippage_rate)
                equity += pnl
                trades += 1
                wins += int(pnl > 0)
                realized_returns.append(pnl / max(equity - pnl, 1.0))
                position = None

            if position is None and signal.size > 0:
                fill_price = price * (1.0 + slippage_rate if signal.side == "buy" else 1.0 - slippage_rate)
                position = _BacktestPosition(
                    side=signal.side,
                    size=float(signal.size),
                    entry_price=fill_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                )
                equity -= abs(fill_price * signal.size) * commission_rate

            equity_curve.append(equity + (self._mark_to_market(position, price) if position else 0.0))

        if position is not None:
            final_price = float(frame.iloc[-1]["close"])
            pnl = self._close_position(position, exit_price=final_price, commission_rate=commission_rate, slippage_rate=slippage_rate)
            equity += pnl
            trades += 1
            wins += int(pnl > 0)
            realized_returns.append(pnl / max(equity - pnl, 1.0))
            equity_curve[-1] = equity

        max_drawdown = self._max_drawdown(equity_curve)
        sharpe = self._sharpe(realized_returns)
        win_rate = wins / trades if trades else 0.0
        return BacktestMetrics(
            total_trades=trades,
            win_rate=win_rate,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            ending_equity=equity,
            equity_curve=equity_curve,
            metadata={"strategy": strategy.name, "symbol": symbol},
        )

    @staticmethod
    def _mark_to_market(position: _BacktestPosition | None, price: float) -> float:
        if position is None:
            return 0.0
        direction = 1.0 if position.side == "buy" else -1.0
        return (price - position.entry_price) * position.size * direction

    @staticmethod
    def _close_position(position: _BacktestPosition, *, exit_price: float, commission_rate: float, slippage_rate: float) -> float:
        adjusted_exit = exit_price * (1.0 - slippage_rate if position.side == "buy" else 1.0 + slippage_rate)
        direction = 1.0 if position.side == "buy" else -1.0
        gross = (adjusted_exit - position.entry_price) * position.size * direction
        fees = (abs(position.entry_price) + abs(adjusted_exit)) * position.size * commission_rate
        return gross - fees

    @staticmethod
    def _max_drawdown(curve: list[float]) -> float:
        peak = curve[0] if curve else 0.0
        max_drawdown = 0.0
        for value in curve:
            peak = max(peak, value)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - value) / peak)
        return max_drawdown

    @staticmethod
    def _sharpe(returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        series = pd.Series(returns, dtype=float)
        std = float(series.std(ddof=0) or 0.0)
        if std <= 1e-12:
            return 0.0
        return float(series.mean() / std * sqrt(252.0))
