from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.backend.models.trade import Trade
from server.app.backend.schemas.performance import PerformanceResponse, StrategyPerformance


class LearningEngine:
    @staticmethod
    def _adjustment_for_metrics(*, win_rate: float, avg_pnl: float) -> str:
        if win_rate >= 0.6 and avg_pnl > 0:
            return "Increase capital allocation gradually."
        if win_rate < 0.45 or avg_pnl < 0:
            return "Reduce exposure and review entry filters."
        return "Maintain current risk settings."

    @staticmethod
    def _to_float(value: Decimal | float | int | None) -> float:
        if value is None:
            return 0.0
        return float(value)

    @classmethod
    async def compute_user_performance(
        cls,
        session: AsyncSession,
        user_id: str,
    ) -> PerformanceResponse:
        summary_stmt = select(
            func.count(Trade.id),
            func.coalesce(func.sum(Trade.pnl), 0),
            func.coalesce(func.avg(case((Trade.pnl > 0, 1.0), else_=0.0)), 0.0),
        ).where(Trade.user_id == user_id)
        total_trades, total_pnl, win_rate = (await session.execute(summary_stmt)).one()

        strategy_stmt = (
            select(
                Trade.strategy,
                func.count(Trade.id),
                func.coalesce(func.sum(Trade.pnl), 0),
                func.coalesce(func.avg(Trade.pnl), 0),
                func.coalesce(func.avg(case((Trade.pnl > 0, 1.0), else_=0.0)), 0.0),
            )
            .where(Trade.user_id == user_id)
            .group_by(Trade.strategy)
            .order_by(Trade.strategy)
        )
        rows = (await session.execute(strategy_stmt)).all()

        strategy_stats: dict[str, StrategyPerformance] = {}
        for strategy, trade_count, pnl, avg_pnl, strategy_win_rate in rows:
            strategy_stats[str(strategy)] = StrategyPerformance(
                total_trades=int(trade_count or 0),
                pnl=cls._to_float(pnl),
                avg_pnl=cls._to_float(avg_pnl),
                win_rate=round(cls._to_float(strategy_win_rate), 4),
                adjustment=cls._adjustment_for_metrics(
                    win_rate=cls._to_float(strategy_win_rate),
                    avg_pnl=cls._to_float(avg_pnl),
                ),
            )

        return PerformanceResponse(
            total_trades=int(total_trades or 0),
            pnl=cls._to_float(total_pnl),
            win_rate=round(cls._to_float(win_rate), 4),
            strategy_stats=strategy_stats,
        )

