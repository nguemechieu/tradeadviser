class Simulator:
    def __init__(self, initial_balance=10000, commission_bps=0.0, slippage_bps=0.0):
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.commission_bps = float(commission_bps or 0.0)
        self.slippage_bps = float(slippage_bps or 0.0)
        self.position_qty = 0.0
        self.entry_price = None
        self.entry_commission = 0.0
        self.entry_slippage = 0.0
        self.symbol = None
        self.trades = []

    def _candle_value(self, candle, key, default=None):
        if hasattr(candle, "get"):
            value = candle.get(key, default)
            if value is not None:
                return value
        try:
            return candle[key]
        except Exception:
            return default

    def current_equity(self, market_price=None):
        if self.position_qty > 0 and market_price is not None and self.entry_price is not None:
            return self.balance + (self.position_qty * market_price)
        return self.balance

    def _execution_price(self, market_price, side):
        price = float(market_price or 0.0)
        if price <= 0:
            return 0.0
        adjustment = self.slippage_bps / 10000.0
        if str(side).lower() == "buy":
            return price * (1.0 + adjustment)
        if str(side).lower() == "sell":
            return price * (1.0 - adjustment)
        return price

    def _commission_cost(self, notional):
        notional_value = float(notional or 0.0)
        if notional_value <= 0:
            return 0.0
        return notional_value * (self.commission_bps / 10000.0)

    def execute(self, signal, candle, symbol="BACKTEST"):
        if not isinstance(signal, dict):
            return None

        side = str(signal.get("side", "")).lower()
        if side not in {"buy", "sell"}:
            return None

        amount = float(signal.get("amount", signal.get("size", 1)) or 0)
        if amount <= 0:
            return None

        market_price = float(self._candle_value(candle, "close", 0) or 0)
        timestamp = self._candle_value(candle, "timestamp")
        if market_price <= 0:
            return None

        if side == "buy":
            if self.position_qty > 0:
                return None

            price = self._execution_price(market_price, side)
            affordable_amount = min(amount, self.balance / price)
            if affordable_amount <= 0:
                return None

            notional = affordable_amount * price
            commission = self._commission_cost(notional)
            self.balance -= notional + commission
            self.position_qty = affordable_amount
            self.entry_price = price
            self.entry_commission = commission
            self.entry_slippage = max(0.0, price - market_price) * affordable_amount
            self.symbol = symbol

            trade = {
                "timestamp": timestamp,
                "symbol": symbol,
                "side": "BUY",
                "type": "ENTRY",
                "price": price,
                "amount": affordable_amount,
                "pnl": 0.0,
                "equity": self.current_equity(price),
                "reason": signal.get("reason", ""),
                "commission": commission,
                "slippage_cost": self.entry_slippage,
                "market_price": market_price,
            }
            self.trades.append(trade)
            return trade

        if self.position_qty <= 0:
            return None

        price = self._execution_price(market_price, side)
        amount = min(amount, self.position_qty)
        notional = amount * price
        commission = self._commission_cost(notional)
        gross_pnl = (price - float(self.entry_price or price)) * amount
        slippage_cost = max(0.0, market_price - price) * amount
        pnl = gross_pnl - commission - float(self.entry_commission or 0.0)
        self.balance += notional - commission
        self.position_qty -= amount

        trade = {
            "timestamp": timestamp,
            "symbol": symbol,
            "side": "SELL",
            "type": "EXIT",
            "price": price,
            "amount": amount,
            "pnl": pnl,
            "equity": self.current_equity(price),
            "reason": signal.get("reason", ""),
            "commission": commission + float(self.entry_commission or 0.0),
            "slippage_cost": slippage_cost + float(self.entry_slippage or 0.0),
            "market_price": market_price,
        }

        if self.position_qty <= 0:
            self.position_qty = 0.0
            self.entry_price = None
            self.entry_commission = 0.0
            self.entry_slippage = 0.0
            self.symbol = None

        self.trades.append(trade)
        return trade

    def close_open_position(self, candle, symbol="BACKTEST", reason="end_of_test"):
        if self.position_qty <= 0:
            return None

        return self.execute(
            {"side": "sell", "amount": self.position_qty, "reason": reason},
            candle,
            symbol=symbol,
        )
