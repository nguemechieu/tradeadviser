import inspect

from agents.base_agent import BaseAgent


class SignalAgent(BaseAgent):
    """Select, normalize, and qualify trade signals for a given symbol. Orchestrates signal
    generation, optional news bias adjustments, and final filtering before passing signals
    further down the decision pipeline.

    The agent delegates raw signal selection to an injected selector callable, enriches and
    clamps the signal, and optionally records candidate signals instead of producing a final
    decision. It can also integrate a display builder, publisher, and memory/event bus to log
    or broadcast signal-related activity across the system.
    Parameters:
        selector: Callable that takes (symbol, candles, dataset) and returns a tuple of
            (signal_dict, assigned_strategies). The signal_dict should contain keys like
            'side', 'confidence', 'strategy_name', etc. Assigned_strategies can be any metadata
            about which strategies are relevant to this signal.
        name: Optional name for the agent instance (default: "SignalAgent").
        display_builder: Optional callable to build a display representation of the signal.
        publisher: Optional callable to publish the signal to an external system.
        news_bias_applier: Optional callable that takes (symbol, signal) and returns either
            a modified signal dict or a boolean indicating whether to reduce confidence.
        memory: Optional memory store for recording agent decisions.
        event_bus: Optional event bus for publishing events related to signal processing.
        candidate_mode: If True, the agent will store signals as candidates instead of final decisions.
    """ 

    def __init__(
            self,
            selector,
            name=None,
            display_builder=None,
            publisher=None,
            news_bias_applier=None,
            memory=None,
            event_bus=None,
            candidate_mode=False,
    ):
        super().__init__(name or "SignalAgent", memory=memory, event_bus=event_bus)
        self.selector = selector
        self.display_builder = display_builder
        self.publisher = publisher
        self.news_bias_applier = news_bias_applier
        self.candidate_mode = bool(candidate_mode)

    def _assigned_strategy_rows(self, assigned_strategies):
        if isinstance(assigned_strategies, (list, tuple)):
            return list(assigned_strategies)
        return []

    def _remember_hold(self, symbol, decision_id, reason, timeframe):
        self.remember(
            "hold",
            {
                "reason": reason,
                "timeframe": timeframe,
            },
            symbol=symbol,
            decision_id=decision_id,
        )

    # =========================
    # 🔧 Normalize Signal
    # =========================
    def _normalize_signal(self, signal, timeframe):
        if not isinstance(signal, dict):
            return None

        side = str(signal.get("side") or "").lower()
        confidence = float(signal.get("confidence", 0.0) or 0.0)

        if side not in ("buy", "sell"):
            return None

        normalized = dict(signal)
        normalized["side"] = side
        normalized["confidence"] = max(0.0, min(confidence, 1.0))
        normalized["strategy_name"] = signal.get("strategy_name", "unknown")
        normalized["timeframe"] = signal.get("timeframe") or timeframe
        normalized["reason"] = signal.get("reason", "")
        normalized["adaptive_weight"] = float(signal.get("adaptive_weight", 1.0) or 1.0)
        normalized["adaptive_score"] = float(signal.get("adaptive_score", confidence) or confidence)
        if "symbol" in normalized:
            normalized["symbol"] = str(normalized.get("symbol") or "").strip().upper()
        return normalized

    # =========================
    # 🚀 Main Processing
    # =========================
    async def process(self, context):
        working = dict(context or {})

        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")
        candles = working.get("candles") or []
        dataset = working.get("dataset")
        timeframe = working.get("timeframe")

        print(f"\n📡 SignalAgent → {symbol}")

        # =========================
        # STEP 1 — SELECT SIGNAL
        # =========================
        try:
            selection = self.selector(symbol, candles, dataset)

            if inspect.isawaitable(selection):
                selection = await selection

        except Exception as e:
            print(f"❌ Selector failed for {symbol}: {e}")
            working["signal"] = None
            working["halt_pipeline"] = True
            return working

        # =========================
        # SAFE UNPACK
        # =========================
        if not selection or not isinstance(selection, (list, tuple)) or len(selection) != 2:
            print(f"❌ Invalid selector output for {symbol}: {selection}")
            working["signal"] = None
            working["halt_pipeline"] = True
            return working

        signal, assigned_strategies = selection
        assigned_rows = self._assigned_strategy_rows(assigned_strategies)
        working["assigned_strategies"] = assigned_rows

        if signal is None:
            print(f"⏸️ No entry signal for {symbol}; holding")
            hold_reason = "No entry signal on the latest scan."
            working["signal"] = None
            working["signal_hold_reason"] = hold_reason
            if not self.candidate_mode:
                working["hold"] = True
            self._remember_hold(symbol, decision_id, hold_reason, timeframe)
            return working

        print(f"📊 Raw signal: {signal}")

        # =========================
        # STEP 2 — NORMALIZE
        # =========================
        signal = self._normalize_signal(signal, timeframe)

        if signal is None:
            print(f"❌ Invalid signal structure for {symbol}")
            working["signal"] = None
            working["halt_pipeline"] = True
            return working

        # =========================
        # STEP 3 — NEWS BIAS (SOFT)
        # =========================
        if callable(self.news_bias_applier):
            try:
                bias_result = self.news_bias_applier(symbol, signal)

                if inspect.isawaitable(bias_result):
                    bias_result = await bias_result

                if isinstance(bias_result, dict):
                    signal = self._normalize_signal(bias_result, timeframe) or signal
                elif not bias_result:
                    print(f"⚠️ News bias → reducing confidence")
                    signal["confidence"] = max(0.1, signal["confidence"] * 0.5)
                    signal["bias_adjusted"] = True

            except Exception as e:
                print(f"⚠️ News bias error (ignored): {e}")

        # =========================
        # STEP 4 — QUALITY SCORE
        # =========================
        signal["quality"] = (
                signal["confidence"] * signal.get("adaptive_weight", 1.0)
        )

        print(f"⚡ Normalized signal: {signal}")

        # =========================
        # STEP 5 — MIN SIGNAL FILTER
        # =========================
        if signal["confidence"] < 0.2:
            print(f"❌ Signal too weak for {symbol}")
            working["signal"] = None
            working["halt_pipeline"] = True
            return working

        # =========================
        # STEP 6 — ASSIGN STRATEGIES
        # =========================
        working["assigned_strategies"] = assigned_rows

        # =========================
        # STEP 7 — CANDIDATE MODE
        # =========================
        if self.candidate_mode:
            working.setdefault("signal_candidates", []).append(
                {
                    "agent_name": self.name,
                    "signal": signal,
                    "assigned_strategies": working["assigned_strategies"],
                    "timeframe": timeframe,
                }
            )

            print(f"🧠 Candidate added: {signal}")

            self.remember(
                "candidate",
                {
                    "side": signal["side"],
                    "confidence": signal["confidence"],
                    "quality": signal["quality"],
                },
                symbol=symbol,
                decision_id=decision_id,
            )

            return working

        # =========================
        # STEP 8 — FINAL SIGNAL
        # =========================
        working["signal"] = signal

        print(f"🚀 FINAL SIGNAL: {signal}")

        self.remember(
            "selected",
            {
                "side": signal["side"],
                "confidence": signal["confidence"],
                "quality": signal["quality"],
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        return working
