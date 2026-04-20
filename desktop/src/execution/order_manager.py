from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ManagedOrder:
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str = "new"
    filled_quantity: float = 0.0
    average_price: float | None = None
    metadata: dict = field(default_factory=dict)


class OrderManager:
    def __init__(self) -> None:
        self.orders: dict[str, ManagedOrder] = {}

    def register(self, order: ManagedOrder) -> ManagedOrder:
        self.orders[order.order_id] = order
        return order

    def update(self, order_id: str, *, status: str, filled_quantity: float | None = None, average_price: float | None = None) -> ManagedOrder | None:
        order = self.orders.get(str(order_id))
        if order is None:
            return None
        order.status = str(status or order.status)
        if filled_quantity is not None:
            order.filled_quantity = float(filled_quantity)
        if average_price is not None:
            order.average_price = float(average_price)
        return order
