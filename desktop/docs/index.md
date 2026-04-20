# Documentation Home

Sopotek Quant System is a desktop trading workstation for broker connectivity, charting, manual and AI-assisted execution, analytics, journaling, and operational control.

## Start Here

- [Getting Started](getting-started.md)
- [Full App Guide](FULL_APP_GUIDE.md)
- [Release Notes](release-notes.md)
- [Adaptive Runtime Guide](adaptive-runtime.md)
- [Agent Network](agent-network.md)
- [UI Workspace Guide](ui-workspace.md)
- [Brokers And Modes](brokers-and-modes.md)
- [Integrations](integrations.md)
- [Contributing Guide](contributing.md)
- [Troubleshooting](troubleshooting.md)

## What This Documentation Covers

- how to install and launch the desktop application
- how dashboard and terminal workflows fit together
- what the broker adapters and session modes do
- how strategies, AI trading scope, and risk controls behave
- how the adaptive runtime layer handles investor profiles, market hours, profit protection, alerting, and automated journaling
- how Telegram, OpenAI, speech, screenshots, and remote chart commands work
- how journaling, trade review, checklists, and post-trade review fit into the workflow
- how to run tests, build docs, and operate the repo locally
- how the current reliability updates affect signal handling, Coinbase auth, and Docker startup

## Quick Facts

- Main UI entry point: `src/frontend/ui/app_controller.py`
- Main terminal workspace: `src/frontend/ui/terminal.py`
- Chart engine: `src/frontend/ui/chart/chart_widget.py`
- Trading engine: `src/core/sopotek_trading.py`
- Adaptive runtime: `src/sopotek/core/orchestrator.py`
- Execution flow: `src/execution/execution_manager.py`
- Broker adapters: `src/broker/`
- Telegram integration: `src/integrations/telegram_service.py`
- Voice and speech support: `src/integrations/voice_service.py`

## Recommended First Run

1. Install dependencies from `requirements.txt`.
2. Launch with `python main.py`.
3. Use `paper`, `practice`, or `sandbox` first.
4. Confirm balances, candles, charts, and open orders.
5. Test one small manual order.
6. Review `Trade Checklist`, `Closed Journal`, and `System Health` before trusting live workflows.

## High-Value Windows To Know

- `System Health`: broker and data-path checks after login
- `Position Analysis`: broker-aware account and position summary
- `Trade Checklist`: pre-trade and post-trade discipline form
- `Closed Journal` and `Journal Review`: history, notes, and weekly/monthly review
- `Sopotek Pilot`: app-aware assistant with voice, screenshots, and command control
