import pandas as pd


class TickerBuffer:

    def __init__(self, max_length=1000):
        self.max_length = max_length
        self.buffers = {}

    # ====================================
    # UPDATE BUFFER
    # ====================================

    def update(self, symbol, ticker):

        if symbol not in self.buffers:
            self.buffers[symbol] = []

        self.buffers[symbol].append(ticker)

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

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        return df

    # ====================================
    # GET LATEST
    # ====================================

    def latest(self, symbol):

        data = self.buffers.get(symbol, [])

        if not data:
            return None

        return data[-1]

    # ====================================
    # CLEAR
    # ====================================

    def clear(self, symbol=None):

        if symbol is None:
            self.buffers.clear()
            return

        self.buffers.pop(symbol, None)
