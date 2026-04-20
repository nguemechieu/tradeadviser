# Refactor Roadmap

This roadmap turns the current improvement themes into staged engineering work that can be shipped incrementally without freezing feature delivery.

## Goals

- Reduce change risk in the trading UI.
- Separate UI wiring from reusable services.
- Strengthen live-trading safeguards.
- Improve operator usability and supportability.

## Phase 1: Extract UI Services

Status: In progress

Scope:

- Move screenshot capture and file naming logic out of the main window classes.
- Reuse the same screenshot behavior across terminal, Telegram, and other UI entry points.
- Add focused unit tests around the extracted service behavior.

Why this first:

- It is low-risk and easy to verify.
- It creates a clean pattern for further extractions.
- It reduces duplicate logic in `Terminal` and `AppController`.

Next slices in this phase:

- Extract notification and message helpers.
- Extract export/report file helpers.
- Extract terminal dock/panel builders into dedicated modules.

## Phase 2: Break Up Terminal Workspace

Status: In progress

Scope:

- Split the monolithic terminal window into smaller modules:
  - `terminal/panels/`
  - `terminal/actions/`
  - `terminal/workspace/`
- Keep `terminal.py` as an orchestration layer instead of the implementation home for every feature.

Exit criteria:

- Position, order, AI monitor, and system status panels each live in their own module.
- Screenshot, refresh, export, and close-position actions are callable from smaller action modules.

Completed in this phase so far:

- Extracted `System Console`, `System Status`, and `AI Signal Monitor` dock builders.
- Extracted `Positions`, `Open Orders`, and `Trade Log` dock builders.
- Extracted `Orderbook`, `Strategy Scorecard`, `Strategy Debug`, and `Risk Heatmap` dock builders.
- Extracted workspace update logic for orderbook routing, strategy debug updates, scorecard population, and risk heatmap rendering.
- Extracted trading table logic for positions, open orders, and trade log normalization/population.
- Extracted performance snapshot/view-refresh logic and runtime reload helpers for positions, open orders, and persisted trades.
- Extracted manual-trade helper logic for ticket defaults, broker precision formatting, quantity normalization, and suggested trade levels.
- Extracted manual-trade ticket workflow logic for ticket refresh, prefill population, and submission handling.
- Extracted manual-trade ticket window construction and signal wiring into a dedicated panel module.
- Extracted terminal trading actions for close-all positions, cancel-all orders, trade export, and async notification dialogs.
- Extracted detached utility window actions for logs, AI monitor, text windows, and in-app documentation content.
- Extracted the strategy optimization workspace for window creation, selector sync, result rendering, and best-parameter application.
- Extracted the backtesting workspace for window creation, refresh rendering, and start/load/report controls.

## Phase 3: Live Trading Safety

Scope:

- Add stale-data guards for quotes, candles, and orderbook data.
- Add a structured pre-trade review dialog for live sessions.
- Strengthen live-mode arming and visible session state.
- Persist a fuller audit trail for submit, modify, cancel, and close actions.

Exit criteria:

- Live trading is blocked when required data is stale.
- Operators see explicit risk and venue details before order submission.
- Audit records can reconstruct who triggered what and when.

## Phase 4: Operator Workflow Improvements

Scope:

- Add a command palette for common actions.
- Add workspace presets for manual trading, AI monitoring, and review workflows.
- Add searchable and filterable tables for positions, orders, and trade history.
- Add a notification center so important events are not lost in the console feed.

## Phase 5: Diagnostics And Release Quality

Scope:

- Diagnostics export bundle for logs, config summary, and runtime health.
- Crash and startup self-check flow.
- Packaging and installer improvements for Windows distribution.
- Release checklist and smoke-test path for live-capable builds.

## Recommended Immediate Order

1. Finish screenshot service extraction and keep screenshot callers thin.
2. Extract terminal dock/panel creation into dedicated modules.
3. Add stale-data guards and a pre-trade live review dialog.
4. Add command palette and notification center.
5. Improve diagnostics and packaging.
