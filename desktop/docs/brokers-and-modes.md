# Brokers And Modes

## Broker Adapters In This Repo

### CCXT Broker
- file: `src/broker/ccxt_broker.py`
- role: generic crypto exchange adapter
- supports market data, order submission, order queries, balances, and open orders where the underlying exchange supports them
- now also carries venue preference handling such as `auto`, `spot`, or `derivative` when available on the venue
- Coinbase is now treated as venue-aware rather than permanently spot-only, but stock and option paths remain intentionally disabled until a dedicated broker implementation exists
- Coinbase futures are reached through this crypto adapter path by selecting `Exchange = coinbase` and `Venue = derivative`
- Coinbase derivative mode now defaults to the futures contract path and reads CFM futures balances and positions directly when the bundled CCXT version lacks native futures account coverage
- Native Coinbase futures contract IDs such as `SLP-20DEC30-CDE` and `BTC-USD-20241227` are preserved through symbol lists, chart loading, and order submission in derivative mode
- Coinbase private REST and futures signing use JWT-based auth, so `PyJWT` must be available in the active runtime environment even if you only installed a subset of optional packages
- unsupported or stale symbols are skipped more defensively so background ticker, order book, and recent-trades tasks fail closed instead of flooding the UI with `BadSymbol` errors
- larger OHLCV requests can be backfilled in chunks on exchanges that return too little history for a single request

### Oanda Broker
- file: `src/broker/oanda_broker.py`
- role: forex adapter
- modes: `practice` and `live`
- market data currently uses polling in this application
- position/account data is normalized for the position analysis window
- rejected orders such as insufficient-margin responses are surfaced back into the app flow
- manual FX order sizing now uses available account balance, free margin, and equity safeguards before submission instead of requiring spot-style quote inventory
- empty latest-candle responses now retry against an explicit recent time window before the adapter gives up
- forex candle source can be aligned to `Bid`, `Mid`, or `Ask`, with midpoint fallback used when a requested bid or ask series comes back empty

### Alpaca Broker
- file: `src/broker/alpaca_broker.py`
- role: stock broker adapter
- modes: `paper` and `live`
- typically relevant for stock-oriented balances, positions, and order management

### Paper Broker
- file: `src/broker/paper_broker.py`
- role: local simulated execution path
- uses market data while simulating order handling locally
- best starting point when validating UI, charts, and risk controls

### Stellar Broker
- file: `src/broker/stellar_broker.py`
- role: Stellar offer and market-data adapter
- modes: sandbox-like and live public network behavior based on config
- has its own market-watch differences in the UI

## Broker Selection Flow

`src/broker/broker_factory.py` maps:

- `crypto` -> `CCXTBroker`
- `forex` -> `OandaBroker`
- `stocks` -> `AlpacaBroker`
- `paper` -> `PaperBroker`
- exchange `stellar` -> `StellarBroker`

## Mode Guidance

### Use Paper When
- testing a new symbol list
- validating UI state updates
- testing strategy parameters
- validating screenshots, Telegram, or Sopotek Pilot flows
- checking order-state transitions without risking capital

### Use Practice Or Sandbox When
- validating real broker authentication
- validating symbol permissions and price precision
- validating venue-specific order rules
- confirming broker-side order, position, and open-order tracking

### Use Live Only When
- balances and permissions are confirmed
- the symbol is already validated in paper or practice
- manual order flow has been tested
- risk settings and behavior guard limits are reviewed
- kill switch and recovery behavior are understood

## Order Tracking Behavior

The execution layer can track submitted orders after the initial response. When the broker supports `fetch_order()`, the app can update transitions such as:

- `submitted`
- `open`
- `partially_filled`
- `filled`
- `canceled`
- `rejected`

## Broker-Aware Formatting

Manual trading now uses broker and symbol metadata where available to normalize:

- amount precision
- minimum order size
- entry price precision
- stop-loss precision
- take-profit precision
- balance, margin, and equity-aware live size caps before submission
- one smaller retry after insufficient-funds or insufficient-margin rejections on manual orders when a fresh safe size can be derived

This matters especially when switching between forex, crypto, and stock-style brokers.

## Broker Capability Awareness

The UI now leans toward broker-aware behavior. In practice this matters for:

- spot vs derivative venue selection
- orderbook availability
- symbol formatting and precision
- open-order visibility
- position/account metric labels in position analysis
- whether balances, equity, and positions should come from the broker account snapshot instead of local portfolio estimates

## Market Data Safety Notes

- the controller now sanitizes malformed OHLCV rows before caching or drawing them
- the app no longer fabricates long synthetic candle runs from a single live tick when history is missing
- chart requests return honest `no data` states when the broker has no usable candles, instead of silently drawing bad data

## Operational Caution

Validate these items per broker before trusting live routing:

1. authentication
2. symbol format
3. minimum size and precision
4. available balance or margin
   the app now uses this during preflight sizing, but broker-side limits still remain authoritative
5. order type support
6. open-order query support
7. cancel-order support
8. screenshot and chart workflows for the symbols you actually trade
