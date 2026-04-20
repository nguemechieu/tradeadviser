from datetime import datetime, timezone


class OrderBookBuffer:

    def __init__(self):
        self.books = {}

    # ====================================
    # UPDATE ORDERBOOK
    # ====================================

    def update(self, symbol, bids, asks, updated_at=None):
        self.books[symbol] = {
            "bids": bids,
            "asks": asks,
            "updated_at": updated_at or datetime.now(timezone.utc).isoformat(),
        }

    # ====================================
    # GET ORDERBOOK
    # ====================================

    def get(self, symbol):
        return self.books.get(symbol, None)
