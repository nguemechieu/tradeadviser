class TickerStream:

    def __init__(self):
        self.tickers = {}

    # ====================================
    # UPDATE TICKER
    # ====================================

    def update(self, symbol, ticker):
        self.tickers[symbol] = ticker

    # ====================================
    # GET TICKER
    # ====================================

    def get(self, symbol):
        return self.tickers.get(symbol)
