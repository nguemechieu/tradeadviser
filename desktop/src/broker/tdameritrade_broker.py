"""Backward-compatible import path for the dedicated Schwab broker integration."""

from broker.schwab.broker import SchwabBroker

TDAmeritradeBroker = SchwabBroker

__all__ = ["SchwabBroker", "TDAmeritradeBroker"]
