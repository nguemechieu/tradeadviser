from __future__ import annotations

"""
InvestPro Backtest Simulator

A lightweight broker-like simulator for strategy testing.

Features:
- Long and short positions
- Cash/equity tracking
- Commission in basis points
- Slippage in basis points
- Position sizing by amount, notional, percent of equity, or all-in
- Stop-loss / take-profit simulation
- Partial close support
- Realized/unrealized PnL
- Trade history
- Equity curve
- Drawdown tracking
- Performance-ready closed-trade records

This simulator is intentionally simple and deterministic. It is not a full
exchange matching engine.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


EPSILON = 1e-12


@dataclass(slots=True)
class SimPosition:
    symbol: str
    side: str = ""  # "long" or "short"
    qty: float = 0.0
    entry_price: float = 0.0
    entry_commission: float = 0.0
    entry_slippage: float = 0.0
    opened_at: Any = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return abs(self.qty) > EPSILON and self.entry_price > 0

    @property
    def signed_qty(self) -> float:
        if self.side == "short":
            return -abs(self.qty)
        return abs(self.qty)


@dataclass(slots=True)
class SimTrade:
    timestamp: Any
    symbol: str
    side: str
    type: str
    price: float
    amount: float
    pnl: float
    equity: float
    balance: float
    reason: str = ""
    commission: float = 0.0
    slippage_cost: float = 0.0
    market_price: float = 0.0
    strategy_name: str = "unknown"
    order_id: str = ""
    trade_id: str = ""
    status: str = "filled"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "side": self.side,
            "type": self.type,
            "price": self.price,
            "amount": self.amount,
            "pnl": self.pnl,
            "equity": self.equity,
            "balance": self.balance,
            "reason": self.reason,
            "commission": self.commission,
            "slippage_cost": self.slippage_cost,
            "market_price": self.market_price,
            "strategy_name": self.strategy_name,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "status": self.status,
            "metadata": self.metadata,
        }


def _candle_value(candle: Any, key: str, default: Any = None) -> Any:
    if hasattr(candle, "get"):
        value = candle.get(key, default)
        if value is not None:
            return value

    try:
        return candle[key]
    except Exception:
        return default


def _normalize_side(side: Any) -> str:
    value = str(side or "").strip().lower()

    if value in {"buy", "long"}:
        return "buy"

    if value in {"sell", "short"}:
        return "sell"

    return value


class Simulator:
    """Simple backtest execution simulator."""

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        commission_bps: float = 0.0,
        slippage_bps: float = 0.0,
        *,
        allow_short: bool = True,
        allow_fractional: bool = True,
        max_leverage: float = 1.0,
        min_cash: float = 0.0,
    ) -> None:
        self.initial_balance = self._safe_float(initial_balance, 10_000.0)
        self.balance = self.initial_balance

        self.commission_bps = self._safe_float(commission_bps, 0.0)
        self.slippage_bps = self._safe_float(slippage_bps, 0.0)

        self.allow_short = bool(allow_short)
        self.allow_fractional = bool(allow_fractional)
        self.max_leverage = max(1.0, self._safe_float(max_leverage, 1.0))
        self.min_cash = max(0.0, self._safe_float(min_cash, 0.0))

        self.position = SimPosition(symbol="")
        self.trades: list[dict[str, Any]] = []
        self.closed_trades: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, Any]] = []

        self.realized_pnl = 0.0
        self.total_commission = 0.0
        self.total_slippage_cost = 0.0
        self.peak_equity = self.initial_balance
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0

    # ------------------------------------------------------------------
    # Compatibility properties
    # ------------------------------------------------------------------

    @property
    def position_qty(self) -> float:
        return abs(self.position.qty) if self.position.is_open else 0.0

    @position_qty.setter
    def position_qty(self, value: float) -> None:
        self.position.qty = abs(self._safe_float(value, 0.0))

    @property
    def entry_price(self) -> Optional[float]:
        return self.position.entry_price if self.position.is_open else None

    @entry_price.setter
    def entry_price(self, value: Optional[float]) -> None:
        self.position.entry_price = self._safe_float(value, 0.0)

    @property
    def symbol(self) -> Optional[str]:
        return self.position.symbol or None

    @symbol.setter
    def symbol(self, value: Optional[str]) -> None:
        self.position.symbol = str(value or "")

    @property
    def entry_commission(self) -> float:
        return self.position.entry_commission

    @entry_commission.setter
    def entry_commission(self, value: float) -> None:
        self.position.entry_commission = self._safe_float(value, 0.0)

    @property
    def entry_slippage(self) -> float:
        return self.position.entry_slippage

    @entry_slippage.setter
    def entry_slippage(self, value: float) -> None:
        self.position.entry_slippage = self._safe_float(value, 0.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.balance = self.initial_balance
        self.position = SimPosition(symbol="")
        self.trades.clear()
        self.closed_trades.clear()
        self.equity_curve.clear()
        self.realized_pnl = 0.0
        self.total_commission = 0.0
        self.total_slippage_cost = 0.0
        self.peak_equity = self.initial_balance
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0

    def current_equity(self, market_price: Optional[float] = None) -> float:
        if not self.position.is_open:
            return self.balance

        price = self._safe_float(market_price, self.position.entry_price)

        if price <= 0:
            price = self.position.entry_price

        return self.balance + self._position_market_value(price)

    def unrealized_pnl(self, market_price: Optional[float] = None) -> float:
        if not self.position.is_open:
            return 0.0

        price = self._safe_float(market_price, self.position.entry_price)

        if self.position.side == "long":
            return (price - self.position.entry_price) * self.position.qty

        if self.position.side == "short":
            return (self.position.entry_price - price) * self.position.qty

        return 0.0

    def execute(self, signal: dict[str, Any], candle: Any, symbol: str = "BACKTEST") -> Optional[dict[str, Any]]:
        """Execute a signal against the candle close price.

        Supported signal examples:

        Long entry:
            {"side": "buy", "amount": 1}

        Long exit:
            {"side": "sell", "amount": 1}

        Short entry:
            {"side": "sell", "amount": 1, "short": True}

        Short cover:
            {"side": "buy", "amount": 1}

        Percent sizing:
            {"side": "buy", "size_pct": 0.25}

        Notional sizing:
            {"side": "buy", "notional": 1000}

        Risk protection:
            {"side": "buy", "amount": 1, "stop_loss": 95, "take_profit": 110}
        """
        if not isinstance(signal, dict):
            return None

        market_price = self._safe_float(
            _candle_value(candle, "close", 0.0), 0.0)
        timestamp = _candle_value(candle, "timestamp", self._utc_now())

        if market_price <= 0:
            return None

        self.mark_to_market(candle, symbol=symbol)

        side = _normalize_side(signal.get("side"))
        if side not in {"buy", "sell"}:
            return None

        if not self.position.is_open:
            if side == "buy":
                return self._open_position(
                    side="long",
                    signal=signal,
                    market_price=market_price,
                    timestamp=timestamp,
                    symbol=symbol,
                )

            if side == "sell":
                if not self.allow_short and not bool(signal.get("short")):
                    return None

                return self._open_position(
                    side="short",
                    signal=signal,
                    market_price=market_price,
                    timestamp=timestamp,
                    symbol=symbol,
                )

        # Existing position.
        if self.position.side == "long":
            if side == "sell":
                return self._close_position(
                    signal=signal,
                    market_price=market_price,
                    timestamp=timestamp,
                    symbol=symbol,
                    reason=str(signal.get("reason") or "exit"),
                )

            # Ignore buy while already long.
            return None

        if self.position.side == "short":
            if side == "buy":
                return self._close_position(
                    signal=signal,
                    market_price=market_price,
                    timestamp=timestamp,
                    symbol=symbol,
                    reason=str(signal.get("reason") or "cover"),
                )

            # Ignore sell while already short.
            return None

        return None

    def mark_to_market(self, candle: Any, symbol: str = "BACKTEST") -> Optional[dict[str, Any]]:
        """Update equity curve and process stop-loss/take-profit triggers."""
        market_price = self._safe_float(
            _candle_value(candle, "close", 0.0), 0.0)
        timestamp = _candle_value(candle, "timestamp", self._utc_now())

        if market_price <= 0:
            return None

        stop_result = self._check_stops(candle, symbol=symbol)
        equity = self.current_equity(market_price)

        self._record_equity(timestamp, equity, market_price)

        return stop_result

    def close_open_position(
        self,
        candle: Any,
        symbol: str = "BACKTEST",
        reason: str = "end_of_test",
    ) -> Optional[dict[str, Any]]:
        if not self.position.is_open:
            return None

        side = "sell" if self.position.side == "long" else "buy"

        return self.execute(
            {
                "side": side,
                "amount": self.position.qty,
                "reason": reason,
            },
            candle,
            symbol=symbol,
        )

    def summary(self, market_price: Optional[float] = None) -> dict[str, Any]:
        equity = self.current_equity(market_price)

        wins = sum(1 for trade in self.closed_trades if self._safe_float(
            trade.get("pnl"), 0.0) > 0)
        losses = sum(1 for trade in self.closed_trades if self._safe_float(
            trade.get("pnl"), 0.0) < 0)
        total = len(self.closed_trades)

        gross_profit = sum(
            self._safe_float(trade.get("pnl"), 0.0)
            for trade in self.closed_trades
            if self._safe_float(trade.get("pnl"), 0.0) > 0
        )
        gross_loss = sum(
            self._safe_float(trade.get("pnl"), 0.0)
            for trade in self.closed_trades
            if self._safe_float(trade.get("pnl"), 0.0) < 0
        )

        profit_factor = 0.0
        if abs(gross_loss) > EPSILON:
            profit_factor = gross_profit / abs(gross_loss)
        elif gross_profit > 0:
            profit_factor = float("inf")

        return {
            "initial_balance": self.initial_balance,
            "balance": self.balance,
            "equity": equity,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl(market_price),
            "total_return": (equity - self.initial_balance) / max(abs(self.initial_balance), EPSILON),
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / max(1, total),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "total_commission": self.total_commission,
            "total_slippage_cost": self.total_slippage_cost,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "open_position": self.position_to_dict(),
            "equity_curve": list(self.equity_curve),
        }

    def position_to_dict(self) -> dict[str, Any]:
        if not self.position.is_open:
            return {
                "symbol": "",
                "side": "",
                "qty": 0.0,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
            }

        return {
            "symbol": self.position.symbol,
            "side": self.position.side,
            "qty": self.position.qty,
            "entry_price": self.position.entry_price,
            "entry_commission": self.position.entry_commission,
            "entry_slippage": self.position.entry_slippage,
            "stop_loss": self.position.stop_loss,
            "take_profit": self.position.take_profit,
            "strategy_name": self.position.strategy_name,
            "opened_at": self.position.opened_at,
            "metadata": dict(self.position.metadata),
        }

    # ------------------------------------------------------------------
    # Position open/close
    # ------------------------------------------------------------------

    def _open_position(
        self,
        *,
        side: str,
        signal: dict[str, Any],
        market_price: float,
        timestamp: Any,
        symbol: str,
    ) -> Optional[dict[str, Any]]:
        execution_side = "buy" if side == "long" else "sell"
        price = self._execution_price(market_price, execution_side)

        if price <= 0:
            return None

        amount = self._resolve_amount(signal, price)
        amount = self._normalize_amount(amount)

        if amount <= 0:
            return None

        notional = amount * price
        commission = self._commission_cost(notional)

        if side == "long":
            required_cash = notional + commission + self.min_cash
            if required_cash > self.balance:
                affordable_amount = max((self.balance - self.min_cash) / max(
                    price * (1.0 + self.commission_bps / 10000.0), EPSILON), 0.0)
                amount = self._normalize_amount(min(amount, affordable_amount))
                if amount <= 0:
                    return None
                notional = amount * price
                commission = self._commission_cost(notional)

            self.balance -= notional + commission

        elif side == "short":
            if not self.allow_short:
                return None

            # Simple margin model:
            # Reserve initial margin = notional / leverage.
            margin_required = (notional / self.max_leverage) + \
                commission + self.min_cash
            if margin_required > self.balance:
                affordable_amount = max(
                    ((self.balance - self.min_cash) * self.max_leverage)
                    / max(price * (1.0 + self.commission_bps / 10000.0), EPSILON),
                    0.0,
                )
                amount = self._normalize_amount(min(amount, affordable_amount))
                if amount <= 0:
                    return None
                notional = amount * price
                commission = self._commission_cost(notional)

            # In this simplified model, short sale proceeds are credited to cash,
            # but equity is still corrected by negative position market value.
            self.balance += notional - commission

        slippage_cost = abs(price - market_price) * amount
        self.total_commission += commission
        self.total_slippage_cost += slippage_cost

        self.position = SimPosition(
            symbol=str(symbol or "BACKTEST"),
            side=side,
            qty=amount,
            entry_price=price,
            entry_commission=commission,
            entry_slippage=slippage_cost,
            opened_at=timestamp,
            stop_loss=self._optional_float(signal.get("stop_loss")),
            take_profit=self._optional_float(signal.get("take_profit")),
            strategy_name=str(signal.get("strategy_name")
                              or signal.get("strategy") or "unknown"),
            metadata=dict(signal.get("metadata") or {}),
        )

        trade = SimTrade(
            timestamp=timestamp,
            symbol=symbol,
            side="BUY" if side == "long" else "SELL",
            type="ENTRY",
            price=price,
            amount=amount,
            pnl=0.0,
            equity=self.current_equity(price),
            balance=self.balance,
            reason=str(signal.get("reason") or "entry"),
            commission=commission,
            slippage_cost=slippage_cost,
            market_price=market_price,
            strategy_name=self.position.strategy_name,
            order_id=str(signal.get("order_id") or ""),
            trade_id=str(signal.get("trade_id") or ""),
            status="filled",
            metadata={
                "position_side": side,
                "stop_loss": self.position.stop_loss,
                "take_profit": self.position.take_profit,
            },
        ).to_dict()

        self.trades.append(trade)
        self._record_equity(
            timestamp, self.current_equity(price), market_price)

        return trade

    def _close_position(
        self,
        *,
        signal: dict[str, Any],
        market_price: float,
        timestamp: Any,
        symbol: str,
        reason: str,
    ) -> Optional[dict[str, Any]]:
        if not self.position.is_open:
            return None

        execution_side = "sell" if self.position.side == "long" else "buy"
        price = self._execution_price(market_price, execution_side)

        if price <= 0:
            return None

        requested_amount = self._resolve_amount(
            signal, price, default=self.position.qty)
        amount = self._normalize_amount(
            min(abs(requested_amount), self.position.qty))

        if amount <= 0:
            return None

        notional = amount * price
        commission = self._commission_cost(notional)
        slippage_cost = abs(price - market_price) * amount

        entry_price = self.position.entry_price
        entry_commission_alloc = self.position.entry_commission * \
            (amount / max(self.position.qty, EPSILON))
        entry_slippage_alloc = self.position.entry_slippage * \
            (amount / max(self.position.qty, EPSILON))

        if self.position.side == "long":
            gross_pnl = (price - entry_price) * amount
            self.balance += notional - commission

        else:
            gross_pnl = (entry_price - price) * amount
            # Buying back short shares reduces cash.
            self.balance -= notional + commission

        pnl = gross_pnl - commission - entry_commission_alloc

        self.realized_pnl += pnl
        self.total_commission += commission
        self.total_slippage_cost += slippage_cost

        self.position.qty -= amount
        remaining_ratio = self.position.qty / \
            max(self.position.qty + amount, EPSILON)

        if self.position.qty <= EPSILON:
            self.position = SimPosition(symbol="")
        else:
            self.position.entry_commission *= remaining_ratio
            self.position.entry_slippage *= remaining_ratio

        trade = SimTrade(
            timestamp=timestamp,
            symbol=symbol,
            side="SELL" if execution_side == "sell" else "BUY",
            type="EXIT",
            price=price,
            amount=amount,
            pnl=pnl,
            equity=self.current_equity(price),
            balance=self.balance,
            reason=reason,
            commission=commission + entry_commission_alloc,
            slippage_cost=slippage_cost + entry_slippage_alloc,
            market_price=market_price,
            strategy_name=str(signal.get("strategy_name")
                              or signal.get("strategy") or "unknown"),
            order_id=str(signal.get("order_id") or ""),
            trade_id=str(signal.get("trade_id") or ""),
            status="closed" if not self.position.is_open else "partially_closed",
            metadata={
                "gross_pnl": gross_pnl,
                "entry_price": entry_price,
                "position_side": "long" if execution_side == "sell" else "short",
            },
        ).to_dict()

        self.trades.append(trade)
        self.closed_trades.append(trade)
        self._record_equity(
            timestamp, self.current_equity(price), market_price)

        return trade

    # ------------------------------------------------------------------
    # Stops / take profit
    # ------------------------------------------------------------------

    def _check_stops(self, candle: Any, symbol: str = "BACKTEST") -> Optional[dict[str, Any]]:
        if not self.position.is_open:
            return None

        high = self._safe_float(_candle_value(candle, "high", None), 0.0)
        low = self._safe_float(_candle_value(candle, "low", None), 0.0)
        close = self._safe_float(
            _candle_value(candle, "close", None), 0.0)
        timestamp = _candle_value(candle, "timestamp", self._utc_now())

        if close <= 0:
            return None

        if high <= 0:
            high = close
        if low <= 0:
            low = close

        stop_loss = self.position.stop_loss
        take_profit = self.position.take_profit

        trigger_price = None
        trigger_reason = ""

        if self.position.side == "long":
            # Conservative order: assume stop-loss can hit before take-profit
            # if both are touched in same candle.
            if stop_loss is not None and low <= stop_loss:
                trigger_price = stop_loss
                trigger_reason = "stop_loss"
            elif take_profit is not None and high >= take_profit:
                trigger_price = take_profit
                trigger_reason = "take_profit"

        elif self.position.side == "short":
            if stop_loss is not None and high >= stop_loss:
                trigger_price = stop_loss
                trigger_reason = "stop_loss"
            elif take_profit is not None and low <= take_profit:
                trigger_price = take_profit
                trigger_reason = "take_profit"

        if trigger_price is None:
            return None

        side = "sell" if self.position.side == "long" else "buy"

        return self.execute(
            {
                "side": side,
                "amount": self.position.qty,
                "reason": trigger_reason,
            },
            {
                "timestamp": timestamp,
                "close": trigger_price,
                "high": high,
                "low": low,
            },
            symbol=symbol,
        )

    # ------------------------------------------------------------------
    # Math / execution helpers
    # ------------------------------------------------------------------

    def _position_market_value(self, price: float) -> float:
        if not self.position.is_open:
            return 0.0

        if self.position.side == "long":
            return self.position.qty * price

        if self.position.side == "short":
            return -self.position.qty * price

        return 0.0

    def _execution_price(self, market_price: float, side: str) -> float:
        price = self._safe_float(market_price, 0.0)

        if price <= 0:
            return 0.0

        adjustment = self.slippage_bps / 10000.0
        normalized = str(side or "").lower()

        if normalized == "buy":
            return price * (1.0 + adjustment)

        if normalized == "sell":
            return price * (1.0 - adjustment)

        return price

    def _commission_cost(self, notional: float) -> float:
        notional_value = self._safe_float(notional, 0.0)

        if notional_value <= 0:
            return 0.0

        return notional_value * (self.commission_bps / 10000.0)

    def _resolve_amount(
        self,
        signal: dict[str, Any],
        price: float,
        *,
        default: Optional[float] = None,
    ) -> float:
        if not isinstance(signal, dict):
            return 0.0

        direct_amount = self._optional_float(signal.get(
            "amount", signal.get("size", signal.get("quantity"))))
        if direct_amount is not None and direct_amount > 0:
            return direct_amount

        notional = self._optional_float(signal.get(
            "notional", signal.get("value", signal.get("cost"))))
        if notional is not None and notional > 0 and price > 0:
            return notional / price

        size_pct = self._optional_float(
            signal.get("size_pct", signal.get(
                "percent", signal.get("equity_pct")))
        )
        if size_pct is not None and size_pct > 0 and price > 0:
            pct = size_pct / 100.0 if size_pct > 1.0 else size_pct
            equity = self.current_equity(price)
            return (equity * pct) / price

        if bool(signal.get("all_in")) and price > 0:
            equity = self.current_equity(price)
            return equity / price

        return self._safe_float(default, 0.0)

    def _normalize_amount(self, amount: float) -> float:
        amount = abs(self._safe_float(amount, 0.0))

        if amount <= EPSILON:
            return 0.0

        if self.allow_fractional:
            return amount

        return math.floor(amount)

    def _record_equity(self, timestamp: Any, equity: float, market_price: float) -> None:
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = self.peak_equity - equity
        self.max_drawdown = max(self.max_drawdown, drawdown)

        if abs(self.peak_equity) > EPSILON:
            self.max_drawdown_pct = max(
                self.max_drawdown_pct, drawdown / abs(self.peak_equity))

        self.equity_curve.append(
            {
                "timestamp": timestamp,
                "equity": equity,
                "balance": self.balance,
                "market_price": market_price,
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": self.unrealized_pnl(market_price),
                "drawdown": drawdown,
                "drawdown_pct": drawdown / abs(self.peak_equity) if abs(self.peak_equity) > EPSILON else 0.0,
            }
        )

    # ------------------------------------------------------------------
    # Candle / parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except Exception:
            return float(default)

        if not math.isfinite(number):
            return float(default)

        return number

    def _optional_float(self, value: Any) -> Optional[float]:
        if value in (None, "", "-"):
            return None

        number = self._safe_float(value, float("nan"))

        if not math.isfinite(number):
            return None

        return number

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
