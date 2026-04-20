"""Feature generation helpers for processed candle datasets."""

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator


def generate_features(input_file, output_file):
    """Build a small technical-indicator feature set from a CSV file."""

    df = pd.read_csv(filepath_or_buffer=input_file)
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
    df["ema_20"] = EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema_50"] = EMAIndicator(df["close"], window=50).ema_indicator()
    df["returns"] = df["close"].pct_change()
    df = df.dropna()
    df.to_csv(output_file, index=False)


if __name__ == "__main__":
    generate_features(
        "../data/processed/btc_1h_clean.csv",
        "../data/features/btc_features.csv",
    )
