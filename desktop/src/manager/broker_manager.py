import asyncio
import re


class BrokerManager:
    FOREX_QUOTES = {
        "AED", "AUD", "CAD", "CHF", "CNH", "CZK", "DKK", "EUR", "GBP", "HKD",
        "HUF", "JPY", "MXN", "NOK", "NZD", "PLN", "SEK", "SGD", "THB", "TRY",
        "USD", "ZAR",
    }
    OANDA_CFD_BASES = {
        "XAU", "XAG", "XPT", "XPD", "XCU",
        "BCO", "WTICO", "NATGAS", "SOYBN", "WHEAT", "CORN", "SUGAR",
    }

    def __init__(self):

        # Asset class brokers
        self.crypto = None
        self.forex = None
        self.stocks = None
        self.paper = None

        # Registry
        self.brokers = {}

    # ======================================================
    # REGISTER METHODS
    # ======================================================

    def register_crypto(self, broker):

        self.crypto = broker
        self.brokers["crypto"] = broker

    def register_forex(self, broker):

        self.forex = broker
        self.brokers["forex"] = broker

    def register_stocks(self, broker):

        self.stocks = broker
        self.brokers["stocks"] = broker

    def register_paper(self, broker):

        self.paper = broker
        self.brokers["paper"] = broker

    # ======================================================
    # AUTO REGISTER FROM CONFIG
    # ======================================================

    def register(self, config: dict):

        """
        Example config:

        {
            "exchange_type": "crypto",
            "crypto": BinanceBroker(...)
        }

        or

        {
            "exchange_type": "forex",
            "forex": OandaBroker(...)
        }
        """

        if not config:
            raise RuntimeError("No broker config provided")

        exchange_type = config.get("broker_type")

        if exchange_type == "crypto":

            broker = config.get("crypto")
            if broker is None:
                raise RuntimeError("Crypto  broker missing in config")

            self.register_crypto(broker)

        elif exchange_type == "forex":
            broker = config.get("forex")
            if broker is None:
                raise RuntimeError("Forex  broker missing in config")

            self.register_forex(broker)

        elif exchange_type == "stocks":
            broker = config.get("stocks")
            if broker is None:
                raise RuntimeError("Stocks  broker missing in config")

            self.register_stocks(broker)

        elif exchange_type == "paper":

            broker = config.get("paper")
            if broker is None:
                raise RuntimeError("Paper broker missing in config")
            self.register_paper(broker)

        else:
            raise RuntimeError(f"Unsupported exchange type: {exchange_type}")

    # ======================================================
    # BROKER ROUTING
    # ======================================================

    @classmethod
    def _normalize_symbol(cls, symbol: str):
        text = str(symbol or "").strip().upper()
        if cls._looks_like_native_contract_symbol(text):
            return text
        return text.replace("_", "/").replace("-", "/")

    @staticmethod
    def _looks_like_native_contract_symbol(symbol: str) -> bool:
        text = str(symbol or "").strip().upper()
        if not text or "/" in text or "_" in text:
            return False
        if "PERP" in text:
            return True
        return bool(
            re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
            or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
        )

    @classmethod
    def _looks_like_forex_symbol(cls, symbol: str):
        normalized = cls._normalize_symbol(symbol)
        if "/" not in normalized:
            return False

        base, quote_segment = normalized.split("/", 1)
        quote = quote_segment.split(":", 1)[0].strip()
        base = base.strip()
        if not base or quote not in cls.FOREX_QUOTES:
            return False
        if base in cls.FOREX_QUOTES or base in cls.OANDA_CFD_BASES:
            return True
        if any(character.isdigit() for character in base):
            return base.isalnum()
        return False

    def get_broker(self, symbol: str):

        """
        Determines which broker to use based on symbol format
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty")

        normalized_symbol = self._normalize_symbol(symbol)

        if self._looks_like_native_contract_symbol(normalized_symbol):
            if self.crypto:
                return self.crypto

        # Forex / CFDs (EUR/USD, XAU/USD, NAS100/USD)
        if "/" in normalized_symbol and self._looks_like_forex_symbol(normalized_symbol):
            if self.forex:
                return self.forex

        # Crypto (BTC/USDT)
        if "/" in normalized_symbol:
            if self.crypto:
                return self.crypto

        # Legacy Forex (EUR_USD)
        if "_" in str(symbol) or self._looks_like_forex_symbol(normalized_symbol):
            if self.forex:
                return self.forex

        # Stocks (AAPL)
        if normalized_symbol.isalpha():
            if self.stocks:
                return self.stocks

        # Fallback
        if self.paper:
            return self.paper

        raise RuntimeError(f"No broker available for symbol {symbol}")

    # ======================================================
    # CONNECT ALL BROKERS
    # ======================================================

    async def connect_all(self):

        tasks = []

        for broker in self.brokers.values():

            if broker:
                tasks.append(broker.connect())

        if tasks:
            await asyncio.gather(*tasks)

    # ======================================================
    # CLOSE ALL BROKERS
    # ======================================================

    async def close_all(self):

        tasks = []

        for broker in self.brokers.values():

            if broker:
                tasks.append(broker.close())

        if tasks:
            await asyncio.gather(*tasks)
