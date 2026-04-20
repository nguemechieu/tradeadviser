import json
import uuid
import logging
import re
import pandas as pd
from pathlib import Path


logger = logging.getLogger(__name__)


# =========================================================
# SYMBOL UTILITIES
# =========================================================

def normalize_symbol(symbol: str):
    """
    Normalize trading pair symbol
    Example:
    BTCUSDT -> BTC/USDT
    btc-usdt -> BTC/USDT
    """

    symbol = symbol.upper()

    if (
        "PERP" in symbol
        or re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", symbol)
        or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", symbol)
    ):
        return symbol

    if "-" in symbol:
        symbol = symbol.replace("-", "/")

    if "/" not in symbol and len(symbol) > 6:
        base = symbol[:-4]
        quote = symbol[-4:]
        symbol = f"{base}/{quote}"

    return symbol


def split_symbol(symbol: str):
    """
    Split symbol into base and quote
    """

    if "/" not in symbol:
        raise ValueError("Invalid symbol format")

    return symbol.split("/")


# =========================================================
# NUMERIC UTILITIES
# =========================================================

def safe_float(value, default=0.0):

    try:
        return float(value)
    except Exception:
        return default


def safe_div(a, b):

    try:
        return a / b
    except ZeroDivisionError:
        return 0


def round_price(price, precision=2):

    return round(price, precision)


# =========================================================
# DATAFRAME VALIDATION
# =========================================================

def validate_ohlcv(df: pd.DataFrame):

    required = ["open", "high", "low", "close", "volume"]

    for col in required:

        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    return True


def ensure_timestamp(df: pd.DataFrame):

    if "timestamp" not in df.columns:
        raise ValueError("Dataframe missing timestamp column")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    return df


# =========================================================
# FILE UTILITIES
# =========================================================

def load_json(file_path):

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(file_path)

    with open(path, "r") as f:
        return json.load(f)


def save_json(file_path, data):

    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


# =========================================================
# UNIQUE ID GENERATION
# =========================================================

def generate_id():

    return str(uuid.uuid4())


# =========================================================
# LIST UTILITIES
# =========================================================

def chunk_list(data, size):

    for i in range(0, len(data), size):

        yield data[i:i + size]


# =========================================================
# LOGGING HELPERS
# =========================================================

def log_exception(e):

    logger.error(str(e), exc_info=True)


def log_info(msg):

    logger.info(msg)
