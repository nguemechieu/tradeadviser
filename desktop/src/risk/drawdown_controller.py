from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DrawdownStatus:
    equity: float
    peak_equity: float
    drawdown_pct: float
    breached: bool


class DrawdownController:
    def __init__(self, max_drawdown: float = 0.10) -> None:
        self.max_drawdown = max(0.0, float(max_drawdown or 0.10))
        self.peak_equity = 0.0

    def evaluate(self, equity: float) -> DrawdownStatus:
        value = max(0.0, float(equity or 0.0))
        self.peak_equity = max(self.peak_equity, value)
        drawdown = 0.0 if self.peak_equity <= 0 else max(0.0, (self.peak_equity - value) / self.peak_equity)
        return DrawdownStatus(
            equity=value,
            peak_equity=self.peak_equity,
            drawdown_pct=drawdown,
            breached=drawdown >= self.max_drawdown,
        )
