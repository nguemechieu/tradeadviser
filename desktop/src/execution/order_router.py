from __future__ import annotations

from collections.abc import Iterable, Mapping

from execution.smart_execution import SmartExecution
from models.instrument import Instrument
from models.order import Order


class OrderRouter:
    def __init__(self, broker):
        self.broker = broker
        self._brokers = self._normalize_brokers(broker)
        self._executors = {name: SmartExecution(instance) for name, instance in self._brokers.items()}
        self._default_executor_key = next(iter(self._executors), None)

    def _normalize_brokers(self, broker) -> dict[str, object]:
        if isinstance(broker, Mapping):
            return {str(name).strip().lower(): instance for name, instance in broker.items()}
        if isinstance(broker, Iterable) and not isinstance(broker, (str, bytes)):
            normalized = {}
            for instance in broker:
                name = str(getattr(instance, "exchange_name", instance.__class__.__name__)).strip().lower()
                normalized[name] = instance
            return normalized
        name = str(getattr(broker, "exchange_name", broker.__class__.__name__)).strip().lower()
        return {name: broker}

    def register_broker(self, name, broker):
        normalized_name = str(name or getattr(broker, "exchange_name", broker.__class__.__name__)).strip().lower()
        self._brokers[normalized_name] = broker
        self._executors[normalized_name] = SmartExecution(broker)
        if self._default_executor_key is None:
            self._default_executor_key = normalized_name

    @property
    def smart_execution(self) -> SmartExecution | None:
        if self._default_executor_key is None:
            return None
        return self._executors.get(self._default_executor_key)

    def _select_broker(self, order_payload: Mapping[str, object]):
        broker_name = str(order_payload.get("broker") or "").strip().lower()
        if broker_name and broker_name in self._brokers:
            return self._brokers[broker_name]

        instrument_payload = order_payload.get("instrument")
        instrument_type = str(order_payload.get("instrument_type") or "").strip().lower()
        if instrument_payload:
            instrument = Instrument.from_mapping(instrument_payload) if not isinstance(instrument_payload, Instrument) else instrument_payload
            broker_hint = str(instrument.broker_hint or "").strip().lower()
            if broker_hint and broker_hint in self._brokers:
                return self._brokers[broker_hint]
            instrument_type = instrument.type.value

        if instrument_type:
            for candidate in self._brokers.values():
                if hasattr(candidate, "supports_instrument_type") and candidate.supports_instrument_type(instrument_type):
                    return candidate

        return next(iter(self._brokers.values()))

    async def route(self, order):
        order_payload = Order.from_mapping(order).to_dict() if not isinstance(order, Mapping) else dict(order)
        selected_broker = self._select_broker(order_payload)
        executor_key = str(getattr(selected_broker, "exchange_name", selected_broker.__class__.__name__)).strip().lower()
        executor = self._executors.get(executor_key)
        if executor is None:
            executor = SmartExecution(selected_broker)
            self._executors[executor_key] = executor
        order_payload.setdefault("broker", executor_key)
        return await executor.execute(order_payload)
