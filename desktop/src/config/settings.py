import os
import yaml
from dotenv import load_dotenv

load_dotenv()


class Settings:

    def __init__(self):
        self.root = os.path.dirname(__file__)

        self.exchanges = self._load_yaml("exchanges.yaml")
        self.strategies = self._load_yaml("strategies.yaml")
        self.risk = self._load_yaml("risk.yaml")

        self.api_keys = {
            "binance_key": os.getenv("BINANCE_API_KEY"),
            "binance_secret": os.getenv("BINANCE_SECRET"),
            "alpaca_key": os.getenv("ALPACA_API_KEY"),
            "alpaca_secret": os.getenv("ALPACA_SECRET"),
            "coinbase_key": os.getenv("COINBASE_API_KEY"),
            "coinbase_secret": os.getenv("COINBASE_SECRET")
        }

    # ====================================
    # LOAD YAML
    # ====================================

    def _load_yaml(self, file):
        path = os.path.join(self.root, file)

        with open(path, "r") as f:
            return yaml.safe_load(f)


settings = Settings()
