# Internal API Notes

## Entry Point

- Application bootstrap: `src/main.py`
- Main controller: `src/frontend/ui/app_controller.py`
- Main terminal UI: `src/frontend/ui/terminal.py`

## Core Interfaces

### Broker Interface
Representative broker behaviors used across adapters include:
- `fetch_symbol()` or exchange symbol discovery
- `fetch_balance()`
- `fetch_ticker(symbol)`
- `fetch_ohlcv(symbol, timeframe, limit)`
- `fetch_orderbook(symbol)`
- `fetch_trades(symbol, limit)` for public market prints where supported
- `fetch_positions()`
- `fetch_open_orders()`
- `create_order(...)`
- `cancel_order(...)`
- `fetch_order(order_id, symbol=None)` where supported

### Execution Manager
Primary file:
- `src/execution/execution_manager.py`

Key behavior surfaces include:
- broker-aware normalization of order input
- behavior-guard interception
- order-state tracking and persistence
- source tagging such as manual, bot, and the internal `chatgpt` source used for Sopotek Pilot actions
- rejected-order normalization

### Strategy Interface
Primary files:
- `src/strategy/strategy.py`
- `src/strategy/strategy_registry.py`

The strategy layer exposes normalized strategy selection and signal reasoning behavior used by the terminal, bot, and analytics windows.

### Controller Signals
`AppController` publishes runtime signals such as:
- symbols
- candles
- equity
- trade updates
- ticker updates
- connection status
- orderbook updates
- recent public trade updates for the active symbol
- news updates
- AI signal monitor updates
- strategy debug updates
- autotrade toggle changes
- license changes

## Persistence APIs

### Database
- `src/storage/database.py`

### Trade Repository
- `src/storage/trade_repository.py`

### Market Data Repository
- `src/storage/market_data_repository.py`

These APIs back local trade history, journal data, and market-data persistence.

## Integration APIs

### Telegram
- `src/integrations/telegram_service.py`

Supports:
- bot polling
- status, balances, positions, orders, screenshots, chart screenshots
- command keyboard
- plain-text Sopotek Pilot relay and slash-command relay

### OpenAI And Voice
- OpenAI controller flow: `src/frontend/ui/app_controller.py`
- local voice integration: `src/integrations/voice_service.py`

Supports:
- runtime context chat
- Telegram question routing
- Sopotek Pilot in-app conversation
- speech recognition and spoken replies

### Review And Journal APIs
Relevant surfaces span:
- `src/storage/trade_repository.py`
- `src/frontend/ui/app_controller.py`
- `src/frontend/ui/terminal.py`

These are responsible for:
- merged closed-trade history
- journal-field persistence
- weekly and monthly review summaries
- trade-history analysis consumed by Sopotek Pilot

## Testing Surfaces

Representative tests include:
- `src/tests/test_execution.py`
- `src/tests/test_storage_runtime.py`
- `src/tests/test_other_broker_adapters.py`
- `src/tests/test_news_service.py`
- `src/tests/test_telegram_service.py`
- `src/tests/test_strategy_runtime.py`
- `src/tests/test_chart_indicators.py`
- `src/tests/test_chart_items.py`
