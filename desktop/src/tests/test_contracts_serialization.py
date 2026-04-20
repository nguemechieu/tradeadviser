from __future__ import annotations

from contracts.base import CommandEnvelope, EnvelopeHeaders, EventEnvelope, ProducerIdentity, ResponseEnvelope, RuntimeContext
from contracts.decision import DecisionAction, DecisionReason, TradeIntent
from contracts.enums import EnvironmentName, MessageTopic, ProducerRole, ReportKind, SessionMode, SessionRole, SessionState, TradeSide, VenueKind
from contracts.learning import LearningOutcome, TradeOutcome
from contracts.market import MarketEventName, MarketTick
from contracts.portfolio import PortfolioSnapshot
from contracts.reporting import ReportSection, ReportSummary
from contracts.risk import EvaluateRiskCommand, RiskCheckRequest, RiskLimits
from contracts.session import DeviceContext, SessionSnapshot, UserIdentity


def _context(topic: MessageTopic) -> EnvelopeHeaders:
    return EnvelopeHeaders(
        context=RuntimeContext(
            environment=EnvironmentName.TEST,
            producer=ProducerIdentity(
                name="contracts-test",
                role=ProducerRole.SERVICE,
                version="1.0.0",
            ),
            tenant_id="tenant-1",
            user_id="user-1",
            account_id="account-1",
            session_id="session-1",
            request_id="request-1",
            trace_id="trace-1",
        ),
        topic=topic,
    )


def test_market_event_round_trip_json() -> None:
    event = EventEnvelope[MarketTick](
        headers=_context(MessageTopic.MARKET),
        event_name=MarketEventName.MARKET_TICK_V1.value,
        payload=MarketTick(
            symbol="BTC/USD",
            venue=VenueKind.COINBASE,
            bid=84290.1,
            ask=84291.4,
            last_price=84290.8,
            spread=1.3,
            mid_price=84290.75,
        ),
    )

    encoded = event.model_dump_json()
    decoded = EventEnvelope[MarketTick].model_validate_json(encoded)

    assert decoded.event_name == MarketEventName.MARKET_TICK_V1.value
    assert decoded.payload.symbol == "BTC/USD"
    assert decoded.headers.ids.correlation_id == event.headers.ids.correlation_id
    assert decoded.headers.schema_version == "1.0.0"


def test_command_envelope_round_trip_json() -> None:
    trade_intent = TradeIntent(
        intent_id="intent-1",
        symbol="BTC/USD",
        venue=VenueKind.COINBASE,
        action=DecisionAction.BUY,
        side=TradeSide.BUY,
        confidence=0.84,
        selected_strategy="trend_following",
        supporting_strategies=["trend_following", "ml_predictor"],
        rejected_strategies=["mean_reversion"],
        timeframe="5m",
        reasons=[
            DecisionReason(
                code="ema_alignment",
                summary="Fast EMA remains above slow EMA.",
                contributor="trend_following",
            )
        ],
    )
    command = CommandEnvelope[EvaluateRiskCommand](
        headers=_context(MessageTopic.RISK),
        command_name="risk.evaluate.v1",
        payload=EvaluateRiskCommand(
            request=RiskCheckRequest(
                trade_intent=trade_intent,
                account_id="account-1",
                limits=RiskLimits(
                    limit_id="limits-1",
                    max_risk_per_trade_pct=0.01,
                    max_daily_drawdown_pct=0.03,
                    max_portfolio_drawdown_pct=0.08,
                    max_leverage=2.0,
                    max_correlated_exposure_pct=0.25,
                    max_orders_per_minute=8,
                    stale_signal_seconds=30,
                ),
            )
        ),
        reply_to="risk.responses",
    )

    decoded = CommandEnvelope[EvaluateRiskCommand].model_validate(command.model_dump())

    assert decoded.payload.request.trade_intent.selected_strategy == "trend_following"
    assert decoded.payload.request.limits.max_orders_per_minute == 8
    assert decoded.reply_to == "risk.responses"


def test_response_envelope_round_trip_json() -> None:
    response = ResponseEnvelope[ReportSummary](
        headers=_context(MessageTopic.REPORTING),
        response_name="reporting.report.generated.v1",
        success=True,
        data=ReportSummary(
            report_id="report-1",
            kind=ReportKind.DAILY,
            title="Daily Desk Summary",
            account_id="account-1",
            highlights=["Volatility expanded but risk stayed in policy."],
            sections=[
                ReportSection(
                    title="Performance",
                    summary="Net PnL finished positive.",
                    metrics={"net_pnl": 1240.5, "win_rate": 0.58},
                    items=["Trend strategies outperformed mean reversion."],
                )
            ],
        ),
    )

    encoded = response.model_dump_json()
    decoded = ResponseEnvelope[ReportSummary].model_validate_json(encoded)

    assert decoded.success is True
    assert decoded.data is not None
    assert decoded.data.kind == ReportKind.DAILY
    assert decoded.data.sections[0].metrics["net_pnl"] == 1240.5


def test_session_and_learning_models_validate_together() -> None:
    session = SessionSnapshot(
        session_id="session-1",
        state=SessionState.ACTIVE,
        mode=SessionMode.PAPER,
        user=UserIdentity(
            user_id="user-1",
            email="operator@example.com",
            roles=[SessionRole.OPERATOR],
        ),
        device=DeviceContext(
            device_id="desktop-1",
            hostname="quant-desk",
            app_version="1.0.0",
        ),
    )
    outcome = TradeOutcome(
        trade_id="trade-1",
        intent_id="intent-1",
        symbol="BTC/USD",
        strategy_name="trend_following",
        outcome=LearningOutcome.WIN,
        pnl=145.2,
        pnl_pct=0.014,
        holding_duration_seconds=1800,
    )
    portfolio = PortfolioSnapshot(
        snapshot_id="portfolio-1",
        account_id="account-1",
        base_currency="USD",
        cash=10000.0,
        equity=10145.2,
    )

    assert session.mode == SessionMode.PAPER
    assert outcome.outcome == LearningOutcome.WIN
    assert portfolio.equity > portfolio.cash
