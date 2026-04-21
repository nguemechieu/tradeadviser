from pydantic import BaseModel
from datetime import datetime
class StrategyPerformance(BaseModel):
    total_trades: int
    win_rate: float
    pnl: float
    avg_pnl: float
    adjustment: str


class PerformanceResponse(BaseModel):
    win_rate: float
    total_trades: int
    pnl: float
    strategy_stats: dict[str, StrategyPerformance]





class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float


