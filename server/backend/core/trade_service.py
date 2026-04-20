from sqlalchemy.ext.asyncio import AsyncSession

from server.backend.agents.feedback_agent import FeedbackAgent
from server.backend.core.learning_engine import LearningEngine
from server.backend.models.trade import Trade
from server.backend.models.user import User
from server.backend.schemas.trade import TradeCreate


async def create_trade(session: AsyncSession, user: User, payload: TradeCreate) -> Trade:
    trade = Trade(
        user_id=user.id,
        symbol=payload.symbol,
        side=payload.side,
        amount=payload.amount,
        pnl=payload.pnl,
        strategy=payload.strategy,
        timestamp=payload.timestamp,
    )
    session.add(trade)
    await session.commit()
    await session.refresh(trade)

    FeedbackAgent().process(trade)
    await LearningEngine.compute_user_performance(session, user.id)
    return trade

