# App UML Overview

This page captures the current high-level structure of the Sopotek Quant System desktop application from the codebase as of April 5, 2026.

## UML Class Diagram

```mermaid
classDiagram
direction LR

class RootMain {
  +runpy.run_path()
}

class DesktopEntrypoint {
  +main(argv)
  +_configure_qt_platform()
  +_load_app_controller()
}

class AppController {
  +broker
  +symbols
  +session_manager
  +terminal
  +dashboard
  +configure_storage_database()
  +set_market_trade_preference()
  +get_active_autotrade_symbols()
  +_start_market_stream()
}

class Terminal {
  +charts and docks
  +manual trade tools
  +workspace actions
}

class Dashboard {
  +login and setup
  +status views
}

class SessionManager {
  +create_session()
  +activate_session()
  +start_session()
  +stop_session()
  +aggregate_portfolio()
}

class TradingSession {
  +initialize()
  +start_trading()
  +stop_trading()
  +snapshot()
  +route_price()
}

class SessionControllerProxy {
  +current_account_label()
  +get_active_autotrade_symbols()
  +is_symbol_enabled_for_autotrade()
}

class BrokerFactory {
  +create(config)
}

class BrokerAdapter {
  +fetch_symbols()
  +fetch_ohlcv()
  +fetch_balance()
  +create_order()
}

class SopotekTrading {
  +start()
  +run()
  +process_symbol()
  +review_signal()
  +execute_review()
}

class MultiSymbolOrchestrator {
  +start(symbols)
  +shutdown()
}

class SymbolWorker {
  +run()
}

class QuantDataHub
class StrategyRegistry
class SignalEngine
class EventBus
class ExecutionManager
class OrderRouter
class TraderBehaviorGuard
class MarketDataRepository
class TradeRepository
class TradeAuditRepository
class EquitySnapshotRepository
class AgentDecisionRepository
class DatabaseModule {
  +configure_database()
  +init_database()
}
class TickerBuffer
class CandleBuffer
class OrderBookBuffer
class TickerStream
class TelegramService
class NewsService
class VoiceService
class LicenseManager

RootMain --> DesktopEntrypoint : delegates startup
DesktopEntrypoint --> AppController : instantiates

AppController *-- Terminal
AppController *-- Dashboard
AppController *-- SessionManager
AppController ..> BrokerFactory : creates broker
BrokerFactory --> BrokerAdapter : returns

SessionManager *-- TradingSession
TradingSession *-- SessionControllerProxy
TradingSession *-- SopotekTrading
TradingSession --> BrokerAdapter : owns session broker
SessionControllerProxy ..> AppController : forwards controller behavior

SopotekTrading *-- MultiSymbolOrchestrator
MultiSymbolOrchestrator *-- SymbolWorker
SopotekTrading o-- QuantDataHub
SopotekTrading o-- StrategyRegistry
SopotekTrading o-- SignalEngine
SopotekTrading o-- ExecutionManager
SopotekTrading o-- EventBus
SopotekTrading o-- TraderBehaviorGuard

ExecutionManager --> OrderRouter
OrderRouter --> BrokerAdapter

AppController ..> DatabaseModule : initializes storage
AppController ..> MarketDataRepository
AppController ..> TradeRepository
AppController ..> TradeAuditRepository
AppController ..> EquitySnapshotRepository
AppController ..> AgentDecisionRepository

AppController o-- TickerBuffer
AppController o-- CandleBuffer
AppController o-- OrderBookBuffer
AppController o-- TickerStream

AppController ..> TelegramService
AppController ..> NewsService
AppController ..> VoiceService
AppController ..> LicenseManager

Terminal ..> AppController : commands and signal subscriptions
Dashboard ..> AppController : setup and connection flow
QuantDataHub ..> BrokerAdapter : fetches candles and market data
TradeRepository ..> DatabaseModule
MarketDataRepository ..> DatabaseModule
TradeAuditRepository ..> DatabaseModule
EquitySnapshotRepository ..> DatabaseModule
AgentDecisionRepository ..> DatabaseModule
```

## UML Trading Sequence

```mermaid
sequenceDiagram
    actor User
    participant Terminal
    participant AppController
    participant SessionManager
    participant TradingSession
    participant SopotekTrading
    participant Orchestrator as MultiSymbolOrchestrator
    participant Worker as SymbolWorker
    participant DataHub as QuantDataHub
    participant Signal as SignalEngine
    participant Exec as ExecutionManager
    participant Router as OrderRouter
    participant Broker as BrokerAdapter
    participant Storage as Repositories

    User->>Terminal: Click "Start Trading"
    Terminal->>AppController: request start
    AppController->>SessionManager: start_session(active_session_id)
    SessionManager->>TradingSession: start_trading()
    TradingSession->>SopotekTrading: start()
    SopotekTrading->>Orchestrator: start(symbols)

    loop one worker per symbol
        Orchestrator->>Worker: run()
        Worker->>SopotekTrading: process_symbol(symbol)
        SopotekTrading->>DataHub: get_symbol_dataset(symbol, timeframe, limit)
        DataHub->>Broker: fetch_ohlcv / market data
        Broker-->>DataHub: candles and quote context
        DataHub-->>SopotekTrading: normalized dataset
        SopotekTrading->>Signal: generate_signal()
        Signal-->>SopotekTrading: candidate trade signal
        SopotekTrading->>Exec: execute(signal)
        Exec->>Router: route order
        Router->>Broker: create_order()
        Broker-->>Router: order result
        Router-->>Exec: normalized execution result
        Exec->>Storage: persist trade and audit state
        SopotekTrading-->>AppController: publish runtime updates
        AppController-->>Terminal: refresh charts, positions, orders, AI monitor
    end
```

## Notes

- The diagram is intentionally high-level and focuses on the main desktop runtime path.
- Broker adapters include crypto, forex, stocks, paper, options, futures, and stellar implementations selected through `BrokerFactory`.
- The session layer isolates per-broker runtime state while still reusing `AppController` behavior through `SessionControllerProxy`.
