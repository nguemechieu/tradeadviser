from strategy.strategy import Strategy


class StrategyRegistry:

    def __init__(self):
        self.strategies = {}
        self._definitions = {}
        self.active_name = None
        self.default_strategy = Strategy()
        self._register_builtin_strategies()

    def _register_builtin_strategies(self):
        for definition in Strategy.STRATEGY_CATALOG:
            name = str(definition.get("name") or "").strip()
            if not name:
                continue
            self._definitions.setdefault(name, dict(definition))
            if self.active_name is None:
                self.active_name = name

    def _instantiate_strategy(self, name):
        normalized = Strategy.normalize_strategy_name(name)
        definition = self._definitions.get(normalized)
        if definition is None:
            return None

        strategy = Strategy(strategy_name=normalized)
        params = dict(definition.get("params") or {})
        if params:
            strategy.apply_parameters(**params)
        self.strategies[normalized] = strategy
        return strategy

    # ===============================
    # REGISTER
    # ===============================

    def register(self, name, strategy):
        normalized = Strategy.normalize_strategy_name(name)
        self._definitions[normalized] = Strategy.strategy_definition(normalized)
        self.strategies[normalized] = strategy
        if self.active_name is None:
            self.active_name = normalized

    # ===============================
    # GET STRATEGY
    # ===============================

    def get(self, name):
        normalized = Strategy.normalize_strategy_name(name)
        strategy = self.strategies.get(normalized)
        if strategy:
            return strategy
        return self._instantiate_strategy(normalized)

    # ===============================
    # LIST STRATEGIES
    # ===============================

    def list(self):
        return list(self._definitions.keys())

    def set_active(self, name):
        normalized = Strategy.normalize_strategy_name(name)
        if normalized in self._definitions or normalized in self.strategies:
            self.active_name = normalized

    def configure(self, strategy_name=None, params=None):
        target_name = Strategy.normalize_strategy_name(strategy_name or self.active_name)
        self.set_active(target_name)
        target = self._resolve_strategy(target_name)
        if hasattr(target, "set_strategy_name"):
            target.set_strategy_name(target_name)
        if isinstance(params, dict) and hasattr(target, "apply_parameters"):
            target.apply_parameters(**params)
        return target

    def _resolve_strategy(self, strategy_name=None):
        normalized = Strategy.normalize_strategy_name(strategy_name) if strategy_name else None
        if normalized:
            selected = self.get(normalized)
            if selected is not self:
                return selected

        if self.active_name:
            selected = self.get(self.active_name)
            if selected is not self:
                return selected

        if self._definitions:
            first_name = next(iter(self._definitions.keys()))
            first = self.get(first_name)
            if first is not self:
                return first

        return self.default_strategy

    def generate_ai_signal(self, candles, strategy_name=None):
        strategy = self._resolve_strategy(strategy_name)

        if hasattr(strategy, "generate_ai_signal"):
            signal = strategy.generate_ai_signal(candles)
            if signal:
                return signal

        if hasattr(strategy, "generate_signal"):
            return strategy.generate_signal(candles)

        return None

    def generate_signal(self, candles, strategy_name=None):
        # Prefer AI path when available; fallback to classical rule-based signal.
        return self.generate_ai_signal(candles, strategy_name=strategy_name)
