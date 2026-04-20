import pandas as pd


class BacktestEngine:
    REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

    def __init__(self, strategy, simulator, metadata=None):
        self.strategy = strategy
        self.simulator = simulator
        self.metadata = dict(metadata or {})
        self.results = []
        self.equity_curve = []

    def _resolve_strategy(self, strategy_name=None):
        if hasattr(self.strategy, "resolve_strategy"):
            return self.strategy.resolve_strategy(strategy_name)
        return self.strategy

    def _min_history(self, strategy_name=None):
        strategy = self._resolve_strategy(strategy_name)
        periods = [
            getattr(strategy, "rsi_period", 0),
            getattr(strategy, "ema_fast", 0),
            getattr(strategy, "ema_slow", 0),
            getattr(strategy, "atr_period", 0),
            getattr(strategy, "breakout_lookback", 0),
        ]
        periods = [int(p) for p in periods if isinstance(p, (int, float)) and p]
        return max(periods or [1], default=1)

    def _normalize_frame(self, data):
        df = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame(columns=self.REQUIRED_COLUMNS)

        if list(df.columns[:6]) != self.REQUIRED_COLUMNS and df.shape[1] >= 6:
            df = df.iloc[:, :6].copy()
            df.columns = self.REQUIRED_COLUMNS

        for column in ["open", "high", "low", "close", "volume"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df.dropna(subset=["open", "high", "low", "close", "volume"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def _window_to_candles(self, frame):
        return frame[self.REQUIRED_COLUMNS].values.tolist()

    def _generate_signal(self, candles, strategy_name=None):
        if hasattr(self.strategy, "generate_signal"):
            try:
                return self.strategy.generate_signal(candles, strategy_name=strategy_name)
            except TypeError:
                return self.strategy.generate_signal(candles)
        return None

    def _precompute_feature_frame(self, df, strategy_name=None):
        strategy = self._resolve_strategy(strategy_name)
        compute_features = getattr(strategy, "compute_features", None)
        generate_from_features = getattr(strategy, "generate_signal_from_features", None)
        if not callable(compute_features) or not callable(generate_from_features):
            return None, None
        try:
            feature_frame = compute_features(df)
        except Exception:
            return None, None
        return feature_frame, generate_from_features

    def run(self, data, symbol="BACKTEST", strategy_name=None, stop_event=None, metadata=None):
        """Execute backtest on provided data using configured strategy and simulator.
        
        Args:
            data: OHLCV data for backtesting
            symbol: Trading symbol identifier
            strategy_name: Optional strategy variant name
            stop_event: Threading event to stop execution early
            metadata: Additional metadata to attach to trades
            
        Returns:
            DataFrame with backtest results
        """
        df = self._normalize_frame(data)
        self.results = []
        self.equity_curve = []
        run_metadata = dict(self.metadata)
        if isinstance(metadata, dict):
            run_metadata.update(metadata)

        if df.empty:
            return pd.DataFrame()

        warmup = self._min_history(strategy_name)
        if warmup >= len(df):
            warmup = 1
        
        feature_frame, generate_from_features = self._precompute_feature_frame(df, strategy_name=strategy_name)
        feature_state = self._init_feature_state(feature_frame)
        last_row = None
        stopped_early = False

        for end_index in range(1, len(df) + 1):
            if stop_event is not None and stop_event.is_set():
                stopped_early = True
                break

            window = df.iloc[:end_index]
            row = df.iloc[end_index - 1]
            last_row = row

            signal = self._compute_signal(window, end_index - 1, generate_from_features, 
                                         feature_frame, feature_state, warmup, strategy_name)
            
            self._record_trade(signal, row, symbol, run_metadata)
            self.equity_curve.append(self.simulator.current_equity(float(row["close"])))

        self._close_position(last_row, df, symbol, stopped_early, run_metadata)
        return pd.DataFrame(self.results)

    def _init_feature_state(self, feature_frame):
        """Initialize feature processing state."""
        return {
            "cursor": 0,
            "count": len(feature_frame) if feature_frame is not None else 0,
            "indices": list(feature_frame.index) if feature_frame is not None else []
        }

    def _compute_signal(self, window, raw_index, generate_from_features, 
                       feature_frame, feature_state, warmup, strategy_name):
        """Compute trading signal for current candle."""
        if generate_from_features is not None and feature_state["count"]:
            while (feature_state["cursor"] < feature_state["count"] and 
                   feature_state["indices"][feature_state["cursor"]] <= raw_index):
                feature_state["cursor"] += 1
            
            if feature_state["cursor"] > 0:
                return generate_from_features(
                    feature_frame.iloc[:feature_state["cursor"]],
                    strategy_name=strategy_name,
                )
        elif len(window) >= warmup:
            candles = self._window_to_candles(window)
            return self._generate_signal(candles, strategy_name=strategy_name)
        return None

    def _record_trade(self, signal, row, symbol, run_metadata):
        """Record executed trade if signal generated."""
        if trade := self.simulator.execute(signal, row, symbol=symbol):
            if run_metadata:
                trade.update(run_metadata)
            self.results.append(trade)

    def _close_position(self, last_row, df, symbol, stopped_early, run_metadata):
        """Close any open position at end of backtest."""
        close_row = last_row if last_row is not None else df.iloc[-1]
        close_reason = "stopped" if stopped_early else "end_of_test"
        if final_trade := self.simulator.close_open_position(close_row, symbol=symbol, reason=close_reason):
            if run_metadata:
                final_trade.update(run_metadata)
            self.results.append(final_trade)
            final_close = float(close_row["close"])
            if self.equity_curve:
                self.equity_curve[-1] = self.simulator.current_equity(final_close)
           
            else:
                self.equity_curve.append(self.simulator.current_equity(final_close))
