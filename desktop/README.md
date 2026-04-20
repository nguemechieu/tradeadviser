# Sopotek Quant System
[//]:#
<p align="center">
  <img
    alt="Sopotek Quant System logo"
    src="https://raw.githubusercontent.com/nguemechieu/sopotek_quant_system/master/src/assets/logo.png"
    width="170"
    height="170"
  >
</p>

<p align="center">
  <a href="https://github.com/nguemechieu/sopotek_quant_system/actions/workflows/python-package-conda.yml">
    <img alt="CI" src="https://github.com/nguemechieu/sopotek_quant_system/actions/workflows/python-package-conda.yml/badge.svg?branch=master">
  </a>
  <a href="https://github.com/nguemechieu/sopotek_quant_system/actions/workflows/ci.yml">
    <img alt="Code Quality" src="https://github.com/nguemechieu/sopotek_quant_system/actions/workflows/ci.yml/badge.svg?branch=master">
  </a>
  <a href="https://pypi.org/project/sopotek-quant-system/">
    <img alt="Python versions" src="https://img.shields.io/pypi/pyversions/sopotek-quant-system">
  </a>
  <a href="https://pypi.org/project/sopotek_quant_system/">
    <img alt="PyPI version" src="https://img.shields.io/pypi/v/sopotek-quant-system">
  </a>
  <a href="https://pypi.org/project/sopotek-quant-system/">
    <img alt="PyPI format" src="https://img.shields.io/pypi/format/sopotek-quant-system">
  </a>
  <a href="https://github.com/nguemechieu/sopotek_quant_system/issues">
    <img alt="Support" src="https://img.shields.io/badge/support-GitHub%20Issues-1f6feb">
  </a>
</p>
[//]:#
Sopotek Quant System is a next-generation trading workstation engineered by Sopotek Corporation to bridge the gap between retail platforms and institutional trading systems.

The platform combines real-time market connectivity, AI-driven decision support, execution infrastructure, and risk-aware automation into a single desktop environment.

With integrated backtesting, multi-asset support, broker-aware order routing, and intelligent workflow automation, Sopotek helps traders scale from discretionary execution to disciplined, AI-assisted operations.

| Branch | Version | Status |
| --- | --- | --- |
| `master` | `1.0.0` | [CI](https://github.com/nguemechieu/sopotek_quant_system/actions/workflows/python-package-conda.yml) |
| `dev` | rolling | [Code Quality](https://github.com/nguemechieu/sopotek_quant_system/actions/workflows/ci.yml) |

| Platform | Python | Delivery |
| --- | --- | --- |
| Windows (x86_64) | `3.10+` | Native PySide6 desktop application |
| Linux (x86_64) | `3.10+` | Docker, browser, and headless runtime profiles |
| macOS | `3.10+` | Source-based install and development workflow |

Docs: [Project documentation](docs/index.md)
Website: [GitHub repository](https://github.com/nguemechieu/sopotek_quant_system)
Support: [GitHub issues](https://github.com/nguemechieu/sopotek_quant_system/issues)

## Version And Status

- Package version: `1.0.0`
- Company: `Sopotek Corporation`
- Product state: first publishable desktop release with a menu-driven Telegram remote console
- Safety posture: live-capable, but still best validated through `paper`, `practice`, or `sandbox` sessions before any meaningful live capital use


## Preview

![Sopotek Quant System dashboard preview](https://raw.githubusercontent.com/nguemechieu/sopotek_quant_system/master/Sopotek_Screenshot_20260414_163616.png)
![Sopotek Quant System terminal preview](https://raw.githubusercontent.com/nguemechieu/sopotek_quant_system/master/Sopotek_Screenshot_20260414_164810.png)
## What The App Includes

- Dashboard for broker selection, mode, credentials, strategy choice, licensing, and launch control
- Terminal workspace with chart tabs, detachable charts, tiled/cascaded layouts, and layout restore
- MT4/MT5-style chart handling including candlesticks, indicators, orderbook heatmap, depth chart, market info, Fibonacci, and chart trading interactions
- Manual trade ticket with broker-aware formatting, suggested SL/TP, chart-linked entry, take-profit levels, and live preflight sizing from balance, margin, or equity
- Derivatives-ready broker layer for options and futures, including normalized instruments, multi-leg option structures, contract metadata, and broker-routed execution
- AI trading controls, AI signal monitor, recommendations, Sopotek Pilot, news overlays, and Telegram command handling
- Open orders, positions, trade log, closed journal, trade review, position analysis, performance analytics, system health tools, and Coinbase-style recent market trades in the Order Book dock
- Risk and behavior protection including risk profiles, a dedicated `Risk` menu, behavior guard, kill switch, drawdown-aware restrictions, and session health status
- Backtesting, strategy optimization, journaling, trade checklist workflow, and local persistence through SQLite and QSettings, including date-range selection, animated in-progress equity graphing, and user-selected report export folders

## Adaptive Runtime Stack

The current Sopotek runtime also includes an event-driven AI supervision layer for live and paper sessions:

- `TraderAgent` acts as a profile-aware digital trader that aggregates `Trend`, `Mean Reversion`, `Breakout`, and `ML` signals, applies investor profile constraints, and produces a final `BUY`, `SELL`, `HOLD`, or `SKIP` decision with confidence and reasoning
- `MarketHoursEngine` blocks trading outside supported crypto, forex, stock, and futures windows, including NYSE holiday awareness and forex session/liquidity classification
- `ProfitProtectionEngine` manages open positions with trailing stops, break-even promotion, partial profit taking, time-based exits, volatility exits, and ML-guided reduce or exit decisions
- `TradeOutcomeTrainingPipeline` plus the `sopotek.ml` modules provide feature engineering, dataset building, training, inference, model registry support, and retraining hooks for self-improving trade filters
- `RegimeEngine`, order-book intelligence, and `ReasoningAgent` add market-regime classification, bid or ask imbalance features, liquidity context, and explainable signal narratives
- `TradeJournalAIEngine` automatically reviews closed trades and summarizes why trades lost, what worked, and what to improve next
- `AlertingEngine` extends Telegram-oriented operations with normalized email and push alerts, while `MobileDashboardService` writes mobile-friendly runtime snapshots to disk
- `FeatureStore` persists live runtime outputs such as feature vectors, model scores, reasoning, alerts, trader decisions, and trade-journal streams under `data/feature_store`

### Runtime Outputs

- `data/feature_store/*.jsonl` captures feature vectors, model scores, regimes, reasoning decisions, trader decisions, alerts, mobile dashboard updates, and trade-journal events
- `data/mobile_dashboard/snapshot.json` and `data/mobile_dashboard/summary.json` expose a mobile-friendly view of equity, positions, decisions, executions, alerts, and the latest trade-journal summary
- SQLite-backed quant persistence stores trade feedback, journal entries, journal summaries, and related model artifacts for later review and retraining

## Key Workflows

### Operator Workflow
1. Launch from the dashboard.
2. Select broker, mode, and strategy.
3. Open one or more charts.
4. Use the chart tabs to review `Candlestick`, `Depth Chart`, and `Market Info`, then inspect `Order Book` and `Recent Trades`.
5. Use the `Trade Checklist` and `Trade Recommendations` windows before placing risk.
6. Place a manual order or enable AI trading only after confirming status, balances, and data quality.
7. Monitor `Trade Log`, `Open Orders`, `Positions`, `System Status`, `Behavior Guard`, and `Performance`.
8. Review trades later in `Closed Journal`, `Trade Review`, and `Journal Review`.

### Remote Workflow
- Receive Telegram notifications for trade activity.
- Use the menu-driven Telegram console with `Overview`, `Portfolio`, `Market Intel`, `Performance`, `Workspace`, and `Controls` panels.
- Keep using slash commands when needed for compatibility, including status, balances, screenshots, chart captures, recommendations, and position analysis.
- Ask Sopotek Pilot questions inside the app or through Telegram.
- Runtime translation now reaches dynamic summaries and rich-text detail views in addition to static labels, so translated sessions stay consistent behind the scenes.

### Suggested First Validation Path
1. Launch in `paper`, `practice`, or `sandbox`.
2. Open one symbol and confirm candles, ticker, order book, recent trades, and depth behavior.
3. Place one very small manual order.
4. Confirm `Trade Log`, `Open Orders`, `Positions`, and `Closed Journal` update in a consistent way.
5. Test `Sopotek Pilot`, Telegram, and screenshots only after the broker session is healthy.
6. Enable AI trading only after manual execution and review workflows are behaving as expected.

### Backtesting Workflow
1. Open `Strategy Tester` from the terminal workspace.
2. Pick the symbol, strategy, timeframe, and the exact `Start Date` / `End Date` you want to test.
3. Start the run and watch the graph tab for the animated live-progress curve while the backtest is executing.
4. Review `Results`, `Graph`, `Report`, and `Journal` after completion.
5. Use `Generate Report` to choose the destination folder for the exported PDF and spreadsheet files.

## Architecture At A Glance

```mermaid
flowchart LR
    D["Dashboard"] --> C["AppController"]
    T["Terminal"] --> C
    C --> B["BrokerFactory / Broker Adapters"]
    C --> TS["SopotekTrading"]
    TS --> SR["StrategyRegistry / Strategy Engine"]
    TS --> EX["ExecutionManager / OrderRouter"]
    EX --> DB["TradeRepository / SQLite"]
    B --> MD["Ticker / Candle / Orderbook / Position Data"]
    MD --> BUF["Buffers + Repositories"]
    BUF --> T
    C --> TG["TelegramService"]
    C --> NS["NewsService"]
    C --> VS["Voice + OpenAI Speech / Chat"]
```

## Supported Modes And Brokers

### Modes
- `paper`: local simulation path
- `practice` or `sandbox`: broker-side test environments where supported
- `live`: real broker execution

### Broker Families
- `crypto` through `CCXTBroker`
- `forex` through `OandaBroker`
- `stocks` through `AlpacaBroker`
- `options` through `TDAmeritradeBroker` for Schwab-backed option routing
- `futures` and broader `derivatives` through `IBKRBroker`
- `futures` through `AMPFuturesBroker`
- `futures` through `TradovateBroker`
- `paper` through `PaperBroker`
- `stellar` through `StellarBroker`

### Coinbase Futures Path
- Coinbase futures run through the `crypto` broker family, not the IBKR-style `futures` adapter path.
- Use `Broker Type = crypto`, `Exchange = coinbase`, and `Venue = derivative`.
- Sopotek now treats that path as Coinbase futures by default and hydrates futures products from the Advanced Trade product feed instead of falling back to spot-only parsing.
- Futures balances and positions now use Coinbase's direct CFM account endpoints when the connected Coinbase session is in derivative mode.
- Derivative watchlists, chart requests, and order preflight now preserve native Coinbase futures contract IDs such as `SLP-20DEC30-CDE`.

### Derivatives Layer
- Common broker contract now includes `connect()`, `disconnect()`, `get_account_info()`, `get_positions()`, `place_order()`, `cancel_order()`, and `stream_market_data()`.
- Instrument modeling now supports `stock`, `option`, `future`, `forex`, and `crypto` with expiry, strike, option right, contract size, and multiplier metadata.
- `OptionsEngine` adds normalized option-chain access, Black-Scholes Greeks, and multi-leg builders for spreads, straddles, and iron condors.
- `FuturesEngine` adds normalized contract metadata, rollover checks, margin estimation, leverage tracking, and liquidation-threshold helpers.
- `ExecutionManager` and `OrderRouter` now preserve derivative-specific payloads such as instrument metadata, multi-leg orders, bracket instructions, and broker hints.
- `RiskEngine` now tracks derivatives-specific controls including margin usage, futures liquidation proximity, gamma exposure, and theta decay.

## Recent Reliability Updates

- Broker-backed balances, equity, and positions are favored over local fallbacks when the connected adapter can provide them directly.
- Strategy selectors that return `None` are now treated as `HOLD` / no-entry outcomes instead of invalid signal payloads, so `SignalAgent` can keep the pipeline healthy when a scan produces no trade.
- Coinbase runtime now treats venue selection more explicitly, keeping `spot` and `derivative` paths distinct while leaving stocks and options disabled there until a dedicated adapter path is added.
- Coinbase futures products are now reclassified from the raw Advanced Trade product payload so derivative mode exposes native contract symbols such as `SLP-20DEC30-CDE` and `BTC-USD-20241227` instead of silently falling back to spot-only markets.
- Coinbase derivative mode now defaults to the futures contract path and can pull CFM futures balances plus open positions directly when the pinned CCXT build does not expose those endpoints natively.
- Coinbase JWT signing now loads `PyJWT` lazily and reports a targeted dependency error if the active environment is missing JWT support, instead of crashing at import time.
- Coinbase history loading now backfills candle requests in chunks, skips unsupported stale symbols safely, and avoids fabricating duplicate synthetic candles when real history is missing.
- Oanda history loading now retries empty latest-candle responses with an explicit recent time window and can fall back to midpoint candles when bid or ask candles come back empty.
- Charts now show a visible loading state, a `No data received.` background message for empty responses, and shorter-history notices when the broker returns fewer candles than requested.
- Malformed OHLCV rows are sanitized before they are cached or drawn so bad timestamps, duplicate rows, `NaN`, `inf`, and invalid high or low bounds do not corrupt the chart.
- Manual live orders now size from the latest available balance, free margin, or equity snapshot before submission, especially on leveraged FX paths such as Oanda.
- If a broker still rejects a manual order for insufficient funds, margin, or buying power, the app retries once with a smaller balance-sized amount and records the reason in the order feedback.
- `Settings` and `Risk` are separate top-level menu entries in the terminal so general preferences and risk controls are easier to reach independently.

## Recommended Local Setup

### 1. Create A Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you plan to use Coinbase Advanced Trade or Coinbase futures from a local source environment, keep `PyJWT` installed in that environment. It is already included by `requirements.txt`, `pyproject.toml`, and the Docker image build.

### 2. Launch The Desktop App
```powershell
python main.py
```

The repository root `main.py` is the recommended launcher from the workspace root.
It bootstraps the desktop app and delegates to the real entry point at `src/main.py`.

### 3. Start Safely
1. Open the dashboard.
2. Choose broker type, exchange, and mode.
3. Start with `paper`, `practice`, or `sandbox`.
4. Confirm symbols, candles, balances, positions, and open orders.
5. Test the manual order flow before enabling AI trading.
6. Validate Telegram or OpenAI integration only after the core trading path is stable.
7. Use `live` only when the same workflow is already behaving correctly in a non-production session.

### 4. Integration Credentials
1. Create an OpenAI API key at `https://platform.openai.com/api-keys`, paste it into `Settings -> Integrations`, and run `Test OpenAI`.
2. Create a Telegram bot with `@BotFather` using `/newbot`, paste the bot token into `Settings -> Integrations`, then message the bot once.
3. Open `https://api.telegram.org/bot<token>/getUpdates`, copy `message.chat.id`, and paste it into `Settings -> Integrations -> Telegram chat ID`.
4. Use `/help` in Telegram for the built-in command list and setup reminders after the bot is connected.

## Documentation Map

- [Getting Started](docs/getting-started.md)
- [Full App Guide](docs/FULL_APP_GUIDE.md)
- [Release Notes](docs/release-notes.md)
- [Adaptive Runtime Guide](docs/adaptive-runtime.md)
- [Architecture](docs/architecture.md)
- [Strategies](docs/strategy_docs.md)
- [Brokers And Modes](docs/brokers-and-modes.md)
- [Derivatives Guide](docs/derivatives.md)
- [UI Workspace Guide](docs/ui-workspace.md)
- [Integrations](docs/integrations.md)
- [Internal API Notes](docs/api.md)
- [Refactor Roadmap](docs/refactor-roadmap.md)
- [Testing And Operations](docs/testing-and-operations.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributing Guide](docs/contributing.md)
- [Development Notes](docs/development.md)

## Built-In Command Surfaces

### Telegram
The bot can handle:

- status, balances, positions, and open orders
- screenshots and chart screenshots
- recommendation and performance summaries
- menu-driven inline navigation and confirmation-gated remote controls
- plain-text Sopotek Pilot conversations in addition to slash commands

### Sopotek Pilot
The in-app assistant can:

- answer questions about balances, positions, performance, journal state, and recommendations
- open windows such as `Settings`, `Position Analysis`, `Closed Journal`, and `Performance`
- manage Telegram state
- place, cancel, or close trades through confirmation-gated commands
- listen and speak when voice support is configured

## Testing

Run the full suite:

```powershell
python -m pytest src\tests -q
```

Run a focused subset:

```powershell
python -m pytest src\tests\test_execution.py src\tests\test_other_broker_adapters.py src\tests\test_storage_runtime.py -q
```

Run the suite with coverage output:

```powershell
python -m pytest src\tests -q --cov=src --cov-branch --cov-report=term-missing:skip-covered --cov-report=xml --cov-report=html
```

## Packaging And Docs

Build package artifacts:

```powershell
python -m build
```

Build documentation site:

```powershell
python -m mkdocs build -f docs\mkdocs.yml
```

Serve docs locally:

```powershell
python -m mkdocs serve -f docs\mkdocs.yml
```

## Docker

Build the container image:

```powershell
docker compose build app
```

Validate the compose stack:

```powershell
docker compose config
```

Run the local PostgreSQL-backed stack:

```powershell
docker compose up -d postgres app
```

Run the headless profile:

```powershell
docker compose --profile headless up app-headless
```

Run the browser profile:

```powershell
docker compose --profile browser up -d app-http
```

Then open the browser UI:

```text
http://localhost:6080/
```

The launcher page embeds noVNC, keeps the desktop at `1600x900`, and adds a fullscreen launch button for the browser session. You can still open the raw client directly at `http://localhost:6080/vnc.html?autoconnect=1&reconnect=1&resize=off&show_dot=1` if you prefer.

The browser profile defaults `NOVNC_RESIZE_MODE` to `off` so your browser scrollbars can reach the full virtual desktop. Set `NOVNC_RESIZE_MODE=scale` before launch if you prefer the UI to shrink to fit the browser window instead.

To enable TLS for the browser desktop, set `NOVNC_TLS_ENABLED=1` before launching the browser profile. The startup script will generate a self-signed certificate automatically when no cert/key pair exists yet and will serve the UI over `https://localhost:6080/`.

Compose defaults the app to the local `postgres` service using a SQLAlchemy URL such as `postgresql+psycopg://sopotek:sopotek_local@postgres:5432/sopotek_trading`. Override `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `POSTGRES_PORT` in your shell or `.env` before launch to change the local container defaults or the host port mapping. If you want Sopotek to connect to an external PostgreSQL instance instead, set `SOPOTEK_DATABASE_URL` directly, for example `postgresql+psycopg://user:secret@db-host:5432/sopotek_trading`.

Those `POSTGRES_*` values only initialize the bundled PostgreSQL container the first time the `postgres_data` volume is created. If you later change the credentials and start seeing authentication failures from the app container, the existing volume still contains the older PostgreSQL credentials. Reuse the original credentials if you need the saved local data, or recreate the local volume for a fresh dev database:

```powershell
docker compose down -v
docker compose up -d postgres app
```

## CI And Release Workflows

- `CI`: runs flake8, full pytest coverage, package build validation, and Docker image smoke checks on pull requests and pushes to `master`.
- `Publish Docker Image`: builds and pushes multi-arch images to GitHub Container Registry for `master` and version tags.
- `Publish Python Package`: builds and validates wheel and sdist artifacts, then publishes them to PyPI on GitHub releases or manual dispatch.

## Storage And Runtime Files

- Local Docker database: PostgreSQL persisted in the `postgres_data` volume
- Local non-Docker fallback database: `data/sopotek_trading.db`
- Logs: `logs/` and `src/logs/`
- Generated screenshots: `output/screenshots/`
- Detached chart layouts and most operator preferences: persisted through `QSettings`
- Generated reports and artifacts: `src/reports/`, `output/`, and other runtime output folders depending on workflow

## Safety Notes

- The application can route live orders when the broker session is configured for live execution.
- Behavior guard, risk profiles, and the kill switch are protection layers, not guarantees of profitability.
- Rejected broker orders, including low-margin or insufficient-funds cases, are surfaced back into the UI and logging paths.
- Manual order review can reduce requested size before submission when balances, margin, or equity do not support the full amount, and the operator sees the sizing reason in the feedback path.
- Always validate symbol precision, size rules, and venue permissions with the actual broker before risking live capital.

## License

`Proprietary - Sopotek Corporation` as declared in [pyproject.toml](pyproject.toml).
