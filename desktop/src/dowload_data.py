import asyncio
import os


import ccxt.async_support as ccxt
import aiohttp
import pandas as pd
DATA_DIR = "./data/raw"
os.makedirs(DATA_DIR, exist_ok=True)


# ==========================================
# UTILS
# ==========================================

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent schema across all assets."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    required = ["timestamp", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            df[col] = None

    return df[required]


async def _retry(coro, retries=3):
    for i in range(retries):
        try:
            return await coro
        except Exception as e:
            if i == retries - 1:
                raise e
            print(f"⚠️  Error: {e}. Retrying ({i + 1}/{retries})...")
            await asyncio.sleep(1)


# ==========================================
# CRYPTO (CCXT)
# ==========================================

async def download_crypto(exchange_name, symbol, timeframe="1h", limit=500):
    exchange = getattr(ccxt, exchange_name)()

    try:
        candles = await _retry(
            exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        )
    finally:
        await exchange.close()

    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = _normalize(df)

    path = f"{DATA_DIR}/crypto_{symbol.replace('/', '')}.csv"
    df.to_csv(path, index=False)

    print(f"✅ Crypto saved -> {path}")


# ==========================================
# STOCKS (ALPACA REST DIRECT)
# ==========================================

async def download_stock(symbol: str):
    key = _require_env("ALPACA_API_KEY")
    secret = _require_env("ALPACA_SECRET")

    url = "https://data.alpaca.markets/v2/stocks/bars"

    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret
    }

    params = {
        "symbols": symbol,
        "timeframe": "1Hour",
        "limit": 500
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()

    bars = data.get("bars", {}).get(symbol, [])

    df = pd.DataFrame([{
        "timestamp": b["t"],
        "open": b["o"],
        "high": b["h"],
        "low": b["l"],
        "close": b["c"],
        "volume": b["v"]
    } for b in bars])

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = _normalize(df)

    path = f"{DATA_DIR}/stock_{symbol}.csv"
    df.to_csv(path, index=False)

    print(f"✅ Stock saved -> {path}")


# ==========================================
# FOREX (OANDA)
# ==========================================

async def download_forex(symbol: str):
    token = _require_env("OANDA_TOKEN")

    url = f"https://api-fxpractice.oanda.com/v3/instruments/{symbol}/candles"

    headers = {"Authorization": f"Bearer {token}"}
    params = {"granularity": "H1", "count": 500}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()

    candles = [{
        "timestamp": c["time"],
        "open": float(c["mid"]["o"]),
        "high": float(c["mid"]["h"]),
        "low": float(c["mid"]["l"]),
        "close": float(c["mid"]["c"]),
        "volume": c["volume"]
    } for c in data.get("candles", [])]

    df = pd.DataFrame(candles)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = _normalize(df)

    path = f"{DATA_DIR}/forex_{symbol}.csv"
    df.to_csv(path, index=False)

    print(f"✅ Forex saved -> {path}")


# ==========================================
# MAIN (PARALLEL EXECUTION)
# ==========================================

async def main():
    await asyncio.gather(
        download_crypto("binanceus", "BTC/USDT"),
        download_crypto("binanceus", "XLM/USDT"),
        download_stock("AAPL"),
        download_forex("EUR_USD")
    )


if __name__ == "__main__":
    asyncio.run(main())
                      
