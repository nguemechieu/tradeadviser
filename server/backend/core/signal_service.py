from sqlalchemy.ext.asyncio import AsyncSession

from server.backend.agents.regime_agent import RegimeAgent
from server.backend.models.signal import Signal
from server.backend.models.user import User
from server.backend.schemas.signal import SignalCreate


async def create_signal(session: AsyncSession, user: User, payload: SignalCreate) -> Signal:
    signal = Signal(
        user_id=user.id,
        symbol=payload.symbol,
        strategy=payload.strategy,
        confidence=payload.confidence,
        timeframe=payload.timeframe,
        timestamp=payload.timestamp,
    )
    session.add(signal)
    await session.commit()
    await session.refresh(signal)

    RegimeAgent().classify({"trend_strength": float(payload.confidence)})
    return signal

