# Derivatives Guide

## Scope

Sopotek Quant System includes a derivatives-aware execution path for options and futures workflows in addition to spot-style trading.
The current repo evidence shows support focused on instrument normalization, broker-aware routing, and risk controls rather than a fully generic exchange-agnostic options UI.

## Broker Paths

- `options` routes through `TDAmeritradeBroker` for Schwab-backed option workflows
- `futures` and broader `derivatives` route through `IBKRBroker`
- `futures` can also route through `AMPFuturesBroker`
- `futures` can also route through `TradovateBroker`

## Instrument Model

The shared instrument model now covers:

- `stock`
- `option`
- `future`
- `forex`
- `crypto`

For derivatives, the model can carry metadata such as:

- expiry
- strike
- option right
- contract size
- multiplier

## Execution Support

The derivatives path is designed so order payloads can preserve contract-specific details instead of flattening everything into spot-style fields.
Repo tests and current docs show support for:

- broker-routed derivative orders
- normalized contract metadata in the order payload
- multi-leg option structures
- bracket-style instructions and broker hints where supported
- execution rules that avoid spot-inventory checks for option workflows

## Options Engine

`OptionsEngine` adds derivatives-focused utilities including:

- normalized option-chain access
- Black-Scholes Greeks
- multi-leg builders for spreads
- multi-leg builders for straddles
- multi-leg builders for iron condors

## Futures Engine

`FuturesEngine` adds futures-specific utilities including:

- normalized contract metadata
- rollover checks
- margin estimation
- leverage tracking
- liquidation-threshold helpers

## Risk Controls

The risk layer tracks derivatives-specific considerations in addition to general account risk.
Current repo evidence points to monitoring for:

- margin usage
- futures liquidation proximity
- gamma exposure
- theta decay

## Operator Notes

- validate contract specifications with the actual broker before placing live risk
- confirm expiry, strike, multiplier, and margin assumptions on the venue you plan to use
- start with `paper`, `practice`, or `sandbox` whenever the broker supports it
- test one very small order before relying on larger multi-leg or leveraged workflows
- treat broker-side validation as authoritative even when the app performs local preflight checks

## Related Docs

- [Brokers And Modes](brokers-and-modes.md)
- [Getting Started](getting-started.md)
- [Full App Guide](FULL_APP_GUIDE.md)
- [Testing And Operations](testing-and-operations.md)
