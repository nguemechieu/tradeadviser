# Interactive Brokers Integration

## Overview

Sopotek implements Interactive Brokers as its own broker family under `src/broker/ibkr/`.
This keeps IBKR separate from:

- CCXT-style exchange adapters
- Coinbase-style HTTP integrations
- Schwab-style brokerage OAuth flows

That separation matters because IBKR exposes two distinct API families:

- Web API / Client Portal API: HTTP endpoints plus websocket-driven session and market-data workflows
- TWS API: a socket and callback model that runs through Trader Workstation or IB Gateway

Sopotek normalizes both transports behind the same canonical broker interface while keeping the transport-specific code isolated.

## Architecture

The integration follows this split:

- `family.py`: shared IBKR family base that normalizes transport outputs into canonical Sopotek broker payloads
- `broker.py`: top-level `IBKRBroker` facade that selects transport mode
- `config.py`: typed config models for shared, Web API, and TWS settings
- `models.py`: normalized IBKR session, account, balance, position, quote, contract, and order models
- `mapper.py`: raw IBKR payload to canonical Sopotek model mapping
- `validators.py`: transport-specific config validation
- `registry.py`: transport selection and adapter construction
- `webapi/`: Client Portal REST, auth, session, websocket, and broker adapter
- `tws/`: TWS session, runtime adapter boundary, contracts, wrappers, and broker adapter

The dashboard remains the entry point. It chooses the broker family, selects the IBKR mode, and passes a broker-agnostic `BrokerConfig` into the existing session/controller path.

## Why IBKR Is Its Own Broker Family

IBKR is not modeled as a generic exchange because:

- contract resolution is central to IBKR workflows
- the Web API and TWS API use different transports and session semantics
- account, order, and market-data flows are broker-centric rather than exchange-centric
- future extensions for options, futures, scanners, and advanced order types depend on IBKR-specific primitives

Sopotek therefore keeps raw IBKR payloads behind typed mappers and exposes canonical broker methods to the rest of the app.
Both transports now share the same family-level canonicalization layer before strategy, risk, portfolio, UI, and reporting code consume the data.

## Modes

### Web API

Choose Web API when you want:

- REST-style connectivity
- Client Portal Gateway compatibility
- simpler account, positions, quote, and historical-bar retrieval
- websocket expansion later for streaming and event-driven updates

Current implementation covers:

- session bootstrap and auth-status refresh
- account discovery
- account balances
- positions
- quotes via contract resolution plus snapshot requests
- historical bars for charting
- order listing
- normalized order placement and cancellation path

### TWS / IB Gateway

Choose TWS when you want:

- a path aligned with Trader Workstation or IB Gateway
- the socket/callback model needed for deeper IBKR-native execution later
- a clean seam for an `ibapi`-backed runtime adapter

Current implementation covers:

- typed host, port, and client-id configuration
- connection lifecycle and session state
- account summary retrieval through an injected runtime adapter
- positions retrieval through an injected runtime adapter
- quote and historical-bar scaffolding
- normalized order and cancel scaffolding

## Current TWS Status

The TWS architecture is production-oriented, but the default runtime adapter is intentionally a placeholder.

This is deliberate:

- Sopotek must not fake a successful live TWS connection
- a real TWS runtime depends on an installed and compatible IB API client plus a running TWS or IB Gateway process
- the placeholder adapter raises a configuration error instead of pretending to be connected

The remaining transport TODO is to replace the default adapter in `src/broker/ibkr/tws/wrappers.py` with an `ibapi`-backed implementation.

## Dashboard Setup

Interactive Brokers now appears in the dashboard broker selector.

When `Interactive Brokers` is selected:

- a connection mode picker appears
- mode-specific fields are shown
- irrelevant Coinbase or Schwab-style fields are not reused blindly

### Web API fields

- Base URL
- Session Token
- WebSocket URL
- Account ID / Profile
- Environment

Default base URL:

- `https://127.0.0.1:5000/v1/api`

### TWS fields

- Host
- Port
- Client ID
- Account ID / Profile

Default paper/live ports:

- paper: `7497`
- live: `7496`

Default host:

- `127.0.0.1`

## Session and State Model

Both transports publish normalized session states:

- `disconnected`
- `connecting`
- `connected`
- `authenticating`
- `authenticated`
- `session_expired`
- `reconnecting`
- `degraded`

The broker adapters emit broker-state payloads to the existing event flow when possible, so the UI and session manager can report health consistently.

## Canonical Data Support

The IBKR mapper normalizes:

- accounts
- balances
- positions
- quotes
- historical bars
- order requests
- order responses
- contracts

This lets Sopotek charts, session views, and broker-agnostic workflows consume IBKR data without binding to raw IBKR payloads.

## Runtime Dependencies

### Web API

Required:

- `aiohttp`
- Client Portal Gateway or reachable IBKR Web API endpoint

### TWS

Required for live TWS mode later:

- Trader Workstation or IB Gateway
- IB API Python package or a compatible runtime adapter
- a concrete adapter implementation wired into `src/broker/ibkr/tws/wrappers.py`

## Troubleshooting

### Web API does not authenticate

Check:

- the Client Portal Gateway is running
- the base URL matches your gateway or hosted endpoint
- the session token is valid if you provide one
- SSL verification settings match your local gateway setup

### TWS mode fails immediately

Expected if no real TWS runtime adapter is installed yet.

Current behavior is explicit failure rather than a fake connected state.

### No quotes returned

Check:

- the symbol can be resolved to a valid IBKR contract
- the account has the required market-data entitlements
- the symbol and security type match the intended market

## Future Extensions

Planned extensions for the IBKR family include:

- concrete `ibapi` runtime adapter for TWS / IB Gateway
- websocket market-data streaming for Web API
- options and futures contract helpers
- advanced order types
- order-status streaming and fill updates
- scanner integration
- richer portfolio and account-summary aggregation

## Files

Core files added for this integration:

- `src/broker/ibkr/__init__.py`
- `src/broker/ibkr/broker.py`
- `src/broker/ibkr/config.py`
- `src/broker/ibkr/models.py`
- `src/broker/ibkr/exceptions.py`
- `src/broker/ibkr/mapper.py`
- `src/broker/ibkr/validators.py`
- `src/broker/ibkr/registry.py`
- `src/broker/ibkr/webapi/*`
- `src/broker/ibkr/tws/*`
- `src/tests/broker/ibkr/*`

Dashboard and compatibility updates:

- `src/frontend/ui/dashboard.py`
- `src/broker/base_broker.py`
- `src/broker/ibkr_broker.py`
- `src/sessions/trading_session.py`

## Official IBKR References

- IBKR API home: https://ibkrcampus.com/ibkr-api-page/ibkr-api-home/
- Client Portal API overview: https://ibkrcampus.com/ibkr-api-page/cpapi-v1/
- Web API reference: https://ibkrcampus.com/campus/ibkr-api-page/webapi-ref/
- TWS API docs: https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/
