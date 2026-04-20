# Getting Started

## What You Need

- Windows is the primary evidenced operator workflow in this repo.
- Python `3.10+` is required by `pyproject.toml`.
- For the complete desktop runtime, prefer `requirements.txt` over the lighter packaging dependency set.
- Broker credentials are optional for paper mode but required for real broker sessions.

## Install
-
```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For Coinbase Advanced Trade or Coinbase futures sessions, keep `PyJWT` installed in the same environment. The repo dependency sets already include it, but stripped local environments can still miss it if dependencies were installed selectively.

Optional docs tooling:

```powershell
python -m pip install mkdocs mkdocs-material
```

## Launch

```powershell
python main.py
```

This starts the PySide6 desktop application from the repository root bootstrap and builds the Qt event loop through `qasync`.
The wrapper then hands off to the real desktop entry point at `src/main.py`.

## Docker Quick Start

Build the local app image:

```powershell
docker compose build app
```

Validate the compose stack:

```powershell
docker compose config
```

Start the browser profile:

```powershell
docker compose --profile browser up -d app-http
```

Start the headless profile:

```powershell
docker compose --profile headless up -d postgres app-headless
```

## First Session Checklist

1. Choose the broker type and exchange in the dashboard.
2. Select the session mode.
3. Enter credentials only for the broker you actually plan to use.
4. Start with `paper`, `practice`, or `sandbox`.
5. Verify balances, symbols, candles, and orderbook updates.
6. Open `Settings` and `Risk` separately and confirm strategy, risk profile, integrations, and language preferences.
7. Open `Trade Checklist` and `System Health` before placing risk.
8. Only after the manual path is stable should you consider AI trading or any live mode.

## Session Modes

- `paper`: local simulation path through `PaperBroker`
- `practice` or `sandbox`: broker-side non-production path where the adapter supports it
- `live`: real broker endpoints and real order routing

## Recommended Safe Validation Path

1. Connect a paper or practice account.
2. Open a chart and confirm candle updates.
3. Open another chart or a detached chart window and confirm it refreshes too.
4. Place a tiny manual order from the trade ticket and confirm the preflight summary looks sensible.
5. Confirm the `Trade Log`, `Open Orders`, and `Positions` views update.
6. Check `System Status`, `Behavior Guard`, and `Performance`.
7. Validate Telegram notifications or screenshot capture if you plan to use them.
8. Enable AI trading only after the manual flow and data quality look correct.

## First Integrations Pass

After the broker session is stable, this is the safest order:

1. Create an OpenAI API key at `https://platform.openai.com/api-keys` and paste it into `Settings -> Integrations -> OpenAI API key`.
2. Use `Test OpenAI` and confirm Sopotek Pilot can answer a simple question.
3. Create a Telegram bot with `@BotFather` using `/newbot`, then copy the bot token into `Settings -> Integrations -> Telegram bot token`.
4. Message the bot once, open `https://api.telegram.org/bot<token>/getUpdates`, and copy `message.chat.id` into `Settings -> Integrations -> Telegram chat ID`.
5. Enable Telegram and send `/help`.
6. Open `Sopotek Pilot` and ask for a short account summary.
7. Try one screenshot flow from the toolbar or Telegram.
8. Only then test AI trading toggles or remote trading commands.

## First Useful Windows To Open

- `Tools -> Trade Checklist`
- `Tools -> Recommendations`
- `Tools -> System Health`
- `Tools -> Closed Journal`
- `Tools -> Position Analysis`
- `Tools -> Sopotek Pilot`

## Core Commands

Run the full test suite:

```powershell
python -m pytest src\tests -q
```

Run docs locally:

```powershell
python -m mkdocs serve -f docs\mkdocs.yml
```

Build docs:

```powershell
python -m mkdocs build -f docs\mkdocs.yml
```
