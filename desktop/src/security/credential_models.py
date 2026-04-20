from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Credential(BaseModel):
    exchange: str
    api_key: Optional[str] = None
    secret: Optional[str] = None
    passphrase: Optional[str] = None
    account_id: Optional[str] = None
    password: Optional[str] = None

    @staticmethod
    def _text(value) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def from_broker_config(cls, broker_config: dict | None):
        broker = dict(broker_config or {})
        exchange = cls._text(broker.get("exchange"))
        if not exchange:
            raise ValueError("Credential exchange is required")

        credential = cls(
            exchange=exchange,
            api_key=cls._text(broker.get("api_key")),
            secret=cls._text(broker.get("secret")),
            passphrase=cls._text(broker.get("passphrase")),
            account_id=cls._text(broker.get("account_id")),
            password=cls._text(broker.get("password")) or cls._text(broker.get("passphrase")),
        )
        credential.validate_for_exchange()
        return credential

    def validate_for_exchange(self):
        exchange = str(self.exchange or "").strip().lower()
        if exchange == "paper":
            return
        if exchange == "stellar":
            if not self.api_key:
                raise ValueError("Stellar credentials require a public key")
            return
        if exchange == "oanda":
            if not self.account_id:
                raise ValueError("Oanda credentials require an account ID")
            if not (self.api_key or self.secret):
                raise ValueError("Oanda credentials require an API key")
            return
        if not self.api_key:
            raise ValueError(f"{self.exchange} credentials require an API key")
        if not self.secret:
            raise ValueError(f"{self.exchange} credentials require a secret")

