import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.ibkr.config import build_ibkr_config
from broker.ibkr.exceptions import IBKRConfigurationError
from broker.ibkr.models import IBKRTransport
from broker.ibkr.validators import validate_ibkr_config
from config.config import BrokerConfig


def test_build_ibkr_config_defaults_to_webapi_and_preserves_execution_mode():
    config = BrokerConfig(type="futures", exchange="ibkr", mode="live", options={"connection_mode": "webapi"})

    resolved = build_ibkr_config(config)

    assert resolved.transport is IBKRTransport.WEBAPI
    assert resolved.execution_mode == "live"
    assert resolved.webapi.base_url == "https://127.0.0.1:5000/v1/api"


def test_validate_ibkr_config_rejects_bad_webapi_base_url():
    config = BrokerConfig(type="futures", exchange="ibkr", mode="paper", options={"connection_mode": "webapi", "base_url": "not-a-url"})

    with pytest.raises(IBKRConfigurationError):
        validate_ibkr_config(build_ibkr_config(config))


def test_validate_ibkr_config_rejects_bad_tws_port_and_client_id():
    config = BrokerConfig(
        type="futures",
        exchange="ibkr",
        mode="paper",
        options={"connection_mode": "tws", "host": "127.0.0.1", "port": 70000, "client_id": -1},
    )

    with pytest.raises(IBKRConfigurationError):
        validate_ibkr_config(build_ibkr_config(config))
