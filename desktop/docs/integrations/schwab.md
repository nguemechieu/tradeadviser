# Charles Schwab Integration

## Overview

Sopotek implements Charles Schwab as a dedicated broker package under `src/broker/schwab/`.
It is intentionally separate from:

- CCXT-style exchange adapters
- Coinbase-style API key integrations
- IBKR transport families

That separation matters because Schwab uses OAuth 2.0 authorization code flow with a registered callback URL instead of exchange-style API keys and secrets.

## Architecture

The Schwab integration is split into clear modules:

- `broker.py`: top-level broker facade that fits Sopotek's canonical broker contract
- `auth.py`: OAuth 2.0 authorization code flow, browser handoff, token exchange, refresh handling
- `client.py`: async REST client with bearer injection, refresh-on-401, retries, and typed failures
- `config.py`: typed Schwab config model and environment parsing
- `models.py`: normalized Schwab account, balance, position, quote, order, and token models
- `mapper.py`: raw Schwab payload to canonical Sopotek model mapping
- `token_store.py`: encrypted token persistence using the reusable OAuth token store
- `validators.py`: config validation
- `streaming.py`: placeholder for future Schwab streaming support

Reusable OAuth infrastructure for future brokers lives in `src/core/oauth/`:

- `local_callback_server.py`
- `models.py`
- `session.py`
- `token_store.py`

This keeps callback handling, token lifecycle management, and encrypted storage reusable for later OAuth-based brokers.

## Why Schwab Is Different

Schwab is not treated like a generic API-key broker because:

- authentication is browser-based OAuth 2.0 authorization code flow
- a registered `redirect_uri` is required
- session continuity depends on token refresh rather than static credentials
- account routing uses account number plus account hash workflows

Sopotek therefore keeps raw Schwab JSON behind a typed client and mapper boundary so UI, strategy, risk, and reporting layers remain broker-agnostic.

## Dashboard Setup

When `schwab` is selected in the dashboard:

- the App Key / Client ID field is shown
- the Redirect URI field is shown
- a Schwab environment selector appears
- the Client Secret field remains available for app setups that require it
- the final account field can pin a discovered account hash

The connect button changes to `Sign In With Schwab`.

## Required Developer Portal Setup

Before using the integration:

1. Register a Schwab developer app.
2. Configure the app callback URL / `redirect_uri` in the Schwab Developer Portal.
3. Use the same callback URL in Sopotek.
4. Choose `Sandbox` or `Production` in the dashboard.

Recommended local callback URI:

- `http://127.0.0.1:8182/callback`

If the local callback cannot be received, Sopotek falls back to manual redirect URL or code entry.

## Login Flow

The runtime flow is:

1. Dashboard builds a standard `BrokerConfig`.
2. `SessionManager` creates a trading session.
3. `SchwabBroker.connect()` opens the client and restores or refreshes tokens if possible.
4. If no valid session exists, Sopotek opens the Schwab authorization page in the browser.
5. Sopotek captures the callback through the reusable localhost callback server or manual fallback.
6. Tokens are exchanged, encrypted, and persisted.
7. Account discovery runs before the terminal session finishes initialization.

Trading session initialization does not complete until OAuth succeeds.

## Tokens And Secure Storage

Schwab tokens are stored through the reusable encrypted OAuth token store:

- storage file: `oauth_tokens.json`
- token payloads: encrypted with `EncryptionManager`
- no access token or refresh token is written in plaintext

Stored metadata includes:

- access token
- refresh token
- access-token expiry
- refresh-token expiry when available
- token type
- environment
- provider metadata

## Supported Workflows

Implemented now:

- OAuth browser sign-in
- localhost callback capture
- manual OAuth fallback
- encrypted token persistence
- refresh-token session renewal
- account discovery
- balances
- positions
- quotes
- historical bar retrieval for charting
- order listing
- order placement and cancellation through canonical order payloads
- option-chain retrieval

## Sandbox vs Production

Use `Sandbox` when validating:

- OAuth credentials
- callback URL handling
- basic API connectivity
- read-only broker flows

Use `Production` for live accounts and live order workflows.

## Troubleshooting

### Browser sign-in completes but Sopotek does not continue

Check:

- the registered callback URL exactly matches the dashboard value
- the local callback host and port are reachable
- another process is not already using the callback port

If needed, use the manual redirect fallback dialog.

### Session expires repeatedly

Check:

- the app key and optional client secret are correct
- the saved redirect URI still matches the developer app
- the stored refresh token has not been invalidated

If refresh fails, Sopotek will fall back to a full OAuth re-login.

### Quotes or history return no data

Check:

- the symbol is valid for the Schwab market-data endpoints
- the account has market-data entitlements where applicable
- the selected environment matches the available account and app setup

## Future Extensions

Planned follow-up work:

- Schwab streaming/event channel support
- richer historical-bar parameter tuning
- deeper order-status and fill tracking
- advanced option and multi-leg order workflows
- more reusable OAuth broker abstractions for additional brokers

## Official References

- Authenticate with OAuth: https://developer.schwab.com/user-guides/get-started/authenticate-with-oauth
- App callback URL requirements: https://developer.schwab.com/user-guides/apis-and-apps/app-callback-url-requirements
- Sandbox testing: https://developer.schwab.com/user-guides/apis-and-apps/test-in-sandbox
- Refresh token guidance: https://developer.schwab.com/user-guides/apis-and-apps/oauth-restart-vs-refresh-token
