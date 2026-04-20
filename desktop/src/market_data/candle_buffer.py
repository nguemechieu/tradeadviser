import pandas as pd


class CandleBuffer:

    def __init__(self, max_length=1000):

        self.max_length = max_length
        self.buffers = {}

    # ====================================
    # UPDATE BUFFER
    # ====================================

    def update(self, symbol, candle):

        if symbol not in self.buffers:
            self.buffers[symbol] = []

        self.buffers[symbol].append(candle)

        if len(self.buffers[symbol]) > self.max_length:
            self.buffers[symbol].pop(0)

    # ====================================
    # GET DATAFRAME
    # ====================================

    def get(self, symbol):

        data = self.buffers.get(symbol, [])

        if not data:
            return None

        df = pd.DataFrame(data)
        ts = df["timestamp"]
        if pd.api.types.is_numeric_dtype(ts):
            numeric_ts = pd.to_numeric(ts, errors="coerce")
            median = numeric_ts.abs().median()
            unit = "ms" if pd.notna(median) and median > 1e11 else "s"
            df["timestamp"] = pd.to_datetime(numeric_ts, unit=unit, errors="coerce", utc=True)
        else:
            df["timestamp"] = pd.to_datetime(ts, errors="coerce", utc=True)

        return df

    def latest(self, symbol):

        data = self.buffers.get(symbol, [])

        if not data:
            return None

        return data[-1]
