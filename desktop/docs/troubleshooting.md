# Troubleshooting

## The App Starts But I See Oanda Polling Logs

`Using polling market data for Oanda` is informational in this repo, not an error. Oanda is intentionally using polling in the current application flow.

## Oanda Says No Candles Were Returned

Check these items:
- restart the app after broker updates so the latest Oanda fallback logic is actually loaded
- confirm the symbol is one Oanda serves on the connected account and pricing division
- switch between `Bid`, `Mid`, and `Ask` candle source if you are matching another platform such as MT4
- try another timeframe to confirm whether the issue is symbol-specific or timeframe-specific
- if the chart still says `No data received.`, capture the exact symbol and timeframe because the app now treats truly empty broker responses honestly instead of inventing filler candles

## Detached Chart Opens Blank

Detached chart rendering was hardened, but if one still looks blank:

1. confirm the chart had data before detaching
2. wait briefly for fresh candle reload
3. reopen the symbol and switch timeframe
4. confirm the symbol is actually returning candles from the connected broker

## No Orderbook Or Heatmap Is Visible

Check these items:
- confirm the symbol is open in a chart
- confirm the broker supports orderbook or depth for that symbol
- wait for the orderbook refresh timer
- verify that bids and asks are actually being returned

## Recent Trades Tab Stays Empty

Check these items:
- confirm the active broker supports public `fetch_trades(symbol)` for that market
- switch to another symbol to rule out a symbol-specific broker limitation
- wait for the normal order book refresh cycle, because recent trades refresh alongside it
- confirm the connected session still has live ticker data, since the app can only synthesize a fallback feed when quote data is available

## Coinbase Says A Symbol Is Unsupported

Coinbase does not expose every pair-like symbol the rest of the app may know about.

Check these items:
- confirm the symbol exists on the connected Coinbase venue, not just on another broker
- reopen the chart with a Coinbase-native market symbol rather than a forex-style pair such as `EUR/USD`
- refresh markets after login if the symbol list may be stale
- if the symbol is unsupported, the app should now skip order book and recent-trades refreshes instead of raising repeated background task errors

## Coinbase Futures Still Look Like Spot Markets

Check these items:
- use `Broker Type = crypto`, not the IBKR-style `futures` profile
- set `Exchange = coinbase`
- set `Venue = derivative`
- reconnect after broker updates so Coinbase futures products are reloaded from the current runtime
- if you are validating credentials from the command line, use `python src/scripts/test_coinbase_credentials.py --market-type derivative`
- derivative mode should now show native contract IDs like `SLP-20DEC30-CDE` instead of spot-style aliases such as `BTC/USD:USD`
- if you still only see spot symbols, verify the connected Coinbase account actually has futures permissions on the account you are using

## Coinbase Says `jwt` Or `PyJWT` Is Missing

Check these items:
- confirm you installed the repo dependencies from `requirements.txt` in the environment that is actually launching the app
- if you installed selectively, run `python -m pip install PyJWT`
- restart the app after dependency changes so the Coinbase auth modules reload cleanly

Current behavior:
- Coinbase JWT auth is loaded lazily
- if `PyJWT` is missing, the broker should raise a targeted authentication-style error instead of crashing during import

## Depth Chart Or Market Info Looks Blank

Check these items:
- confirm the chart has received candles, because market info uses visible candle context
- confirm the order book has populated first, because depth depends on bid and ask levels
- switch chart tabs and symbols once if you recently detached or reattached the chart window

## No AI Signals Or AI Trading Looks Idle

Check these items:
- confirm AI trading is enabled
- confirm the selected scope includes the symbol you expect
- confirm the strategy has enough candle history to compute features
- check AI Signal Monitor, Recommendations, and logs for `HOLD` or filtered signals
- verify the behavior guard did not block trading

If the logs show `Raw signal: None`, that should now be interpreted as a no-entry scan result, not as a broken selector payload. In practice that means the strategy returned no trade and the app should hold rather than crashing the signal pipeline.

## SignalAgent Reports `Raw signal: None`

Check:
- whether the selected strategy actually found an entry condition on the latest candle set
- whether the symbol has enough valid history after feature sanitizing and duplicate-row cleanup
- whether the strategy was filtered to a no-entry state by venue, timeframe, or market regime

Current behavior:
- `None` from a selector is treated as `HOLD` / no entry
- the app should not treat that outcome as an invalid signal structure anymore
- only an actual selector exception should stop the signal path

## Manual Trade Ticket Values Look Wrong

Check:
- whether the broker metadata for the symbol is available yet
- whether amount precision or minimum size is stricter than expected
- whether SL and TP were auto-suggested and then manually overwritten
- whether you are switching between brokers with different lot or precision rules
- for Oanda or leveraged FX, whether the app reduced the size from available balance, margin, or equity before submission

## Live Trade Says Quote Data Is Stale

Check:
- whether the broker is currently returning fresh ticker data for the symbol
- whether the symbol has only an old cached quote and needs a fresh fetch
- whether the market is open and the broker is still publishing prices for that instrument
- if the ticket includes a manual entry price, retry once after a fresh quote arrives because live preflight will re-check freshness before submission

## Order Was Rejected

Common reasons include:
- insufficient funds or margin
- broker minimum size or precision mismatch
- invalid order type or unsupported venue path
- behavior guard block
- live safety lock or kill switch state

If the rejection is a manual insufficient-funds, insufficient-margin, or buying-power case, the app now tries to recompute a smaller safe size from the latest balance or equity snapshot and retries once automatically. If the order still rejects, inspect:

- broker minimum size and size increment rules
- instrument availability or session restrictions
- stop-loss, take-profit, or entry precision
- broker-side account permissions or leverage restrictions

## Telegram Is Not Responding

Check:
- Telegram enabled in settings
- bot token and chat ID configured
- if you do not know the token yet, create the bot with `@BotFather` and `/newbot`
- if you do not know the chat ID yet, message the bot once and inspect `https://api.telegram.org/bot<token>/getUpdates` for `message.chat.id`
- the bot is messaging the expected chat
- network access is available
- use `/help` or `/commands` to restore the keyboard

## OpenAI Or Voice Reply Is Not Working

Check:
- OpenAI API key set in Settings -> Integrations
- if you do not have a key yet, create one at `https://platform.openai.com/api-keys`
- OpenAI model set correctly
- if using OpenAI speech, speech provider is set to `OpenAI`
- if using Google recognition, optional recognition packages are installed
- for Windows speech, test another installed voice if the current one sounds poor or fails
- if using OpenAI speech, confirm the OpenAI key works from `Settings -> Integrations -> Test OpenAI`

## DNS / Network Errors During Login

If you see DNS lookup failures or `Cannot connect to host` errors:

- check internet connectivity
- check VPN, proxy, or firewall behavior
- confirm the broker host resolves from the machine
- retry after validating Windows DNS configuration

## Chart Shows Loading Forever Or No Data Received

Check:
- whether the broker is returning any candles at all for that symbol and timeframe
- whether the chart asked for more history than the venue actually keeps for that market
- whether the symbol was loaded from another broker session and is stale for the current broker
- whether the shorter-history notice says the broker returned only part of the requested window, which is a real data limitation rather than a drawing bug
- whether malformed rows were dropped during sanitizing, which can happen if the venue sends duplicate timestamps or invalid OHLC values

## qasync Timer KeyError Or Async UI Noise

The repo includes hardening for known qasync timer cleanup races, but if you still see repeated async tracebacks, restart the app and capture the first traceback after restart. That is usually the useful one.

## Trade Log, Open Orders, Or Positions Look Wrong

Check:
- whether the broker supports the relevant fetch path
- whether source data is still pending or open instead of terminal
- whether the session is paper, practice, or live
- whether the journal or analytics window is showing merged local plus broker history rather than only one source

## Chart Trading Or Trade-Level Sync Feels Broken

Check:
- whether the manual trade ticket is still open for that symbol
- whether the chart was detached and then reattached while the ticket was active
- whether entry, SL, and TP values were normalized to broker precision after editing
- whether the symbol in the ticket matches the symbol in the active chart
