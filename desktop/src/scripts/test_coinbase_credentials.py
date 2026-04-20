import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from broker.ccxt_broker import CCXTBroker
from broker.coinbase_credentials import coinbase_validation_error, normalize_coinbase_credentials
from broker.coinbase_jwt_auth import masked_coinbase_key_id



ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_STATUS_SYMBOLS = (
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "BTC/USDC",
    "ETH/USDC",
)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Test Coinbase credentials using Sopotek's runtime Coinbase broker path."
    )
    parser.add_argument("--api-key", help="Coinbase key name or key id.")
    parser.add_argument(
        "--secret",
        help="Coinbase private key PEM, private key body, or full Coinbase key JSON.",
    )
    parser.add_argument(
        "--json-file",
        help="Path to a Coinbase key JSON file. Its contents can include id/privateKey.",
    )
    parser.add_argument(
        "--symbol",
        help="Optional symbol to test ticker access with, for example BTC/USD.",
    )
    parser.add_argument(
        "--market-type",
        choices=("auto", "spot", "derivative"),
        default="auto",
        help="Venue preference to test. Use derivative for Coinbase futures.",
    )
    parser.add_argument(
        "--derivative-subtype",
        choices=("future", "swap"),
        default="future",
        help="Contract subtype used when --market-type derivative is selected.",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Enable broker sandbox mode if your Coinbase configuration supports it.",
    )
    parser.add_argument(
        "--show-normalized",
        action="store_true",
        help="Print the normalized key id/name and private key summary before connecting.",
    )
    return parser.parse_args()


def _read_text_file(path_text):
    if not path_text:
        return ""
    path = Path(path_text).expanduser()
    return path.read_text(encoding="utf-8")


def _resolve_raw_inputs(args):
    raw_api = args.api_key or os.getenv("COINBASE_API_KEY", "")
    raw_secret = args.secret or os.getenv("COINBASE_API_SECRET", "")

    env_json = os.getenv("COINBASE_KEY_JSON", "")
    env_file = os.getenv("COINBASE_KEY_FILE", "")
    file_payload = _read_text_file(args.json_file or env_file)

    if not raw_api and env_json:
        raw_api = env_json
    if not raw_secret and file_payload:
        raw_secret = file_payload
    elif not raw_secret and env_json:
        raw_secret = env_json

    return raw_api, raw_secret


def _mask_value(value, keep_start=6, keep_end=4):
    text = str(value or "").strip()
    if len(text) <= keep_start + keep_end + 3:
        return text
    return f"{text[:keep_start]}...{text[-keep_end:]}"


def _looks_like_native_contract_symbol(symbol):
    text = str(symbol or "").strip().upper()
    if not text or "/" in text or "_" in text:
        return False
    if "PERP" in text:
        return True
    return bool(
        re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
        or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
    )


def _normalize_symbol(symbol):
    text = str(symbol or "").strip().upper()
    if _looks_like_native_contract_symbol(text):
        return text
    return text.replace("_", "/").replace("-", "/")


def _pick_symbol(symbols, requested_symbol=None):
    if requested_symbol:
        requested = _normalize_symbol(requested_symbol)
        normalized = {_normalize_symbol(item): item for item in (symbols or [])}
        exact = normalized.get(requested)
        if exact:
            return exact
        if ":" not in requested:
            for symbol in symbols or []:
                candidate = _normalize_symbol(symbol)
                if candidate.startswith(f"{requested}:"):
                    return symbol
        return requested_symbol
    normalized = {_normalize_symbol(item): item for item in (symbols or [])}
    for candidate in DEFAULT_STATUS_SYMBOLS:
        match = normalized.get(candidate.upper())
        if match:
            return match
    return symbols[0] if symbols else None


def _print_json(title, payload):
    print(title)
    print(json.dumps(payload, indent=2, default=str))
    print()


async def _run_connection_test(api_key, secret, sandbox=False, symbol=None, market_type="auto", derivative_subtype="future"):
    options = {"market_type": str(market_type or "auto").strip().lower() or "auto"}
    if options["market_type"] == "derivative":
        options["defaultSubType"] = str(derivative_subtype or "future").strip().lower() or "future"

    config = SimpleNamespace(
        exchange="coinbase",
        api_key=api_key,
        secret=secret,
        password=None,
        uid=None,
        account_id=None,
        wallet=None,
        mode="paper" if sandbox else "live",
        sandbox=bool(sandbox),
        timeout=30000,
        options=options,
        params={},
    )

    broker = CCXTBroker(config)
    try:
        await broker.connect()

        status = await broker.fetch_status()
        symbols = await broker.fetch_symbols()
        chosen_symbol = _pick_symbol(symbols, requested_symbol=symbol)
        balance = await broker.fetch_balance()
        ticker = await broker.fetch_ticker(chosen_symbol) if chosen_symbol else None

        return {
            "status": status,
            "symbols_loaded": len(symbols or []),
            "sample_symbols": list(symbols[:10] if symbols else []),
            "tested_symbol": chosen_symbol,
            "ticker": ticker,
            "balance": balance,
        }
    finally:
        try:
            await broker.close()
        except Exception:
            pass


def main():
    args = _parse_args()
    raw_api, raw_secret = _resolve_raw_inputs(args)

    if not raw_api and not raw_secret:
        raise SystemExit(
            "No Coinbase credentials were provided. Use --api-key/--secret, --json-file, "
            "or the COINBASE_API_KEY / COINBASE_API_SECRET / COINBASE_KEY_JSON / COINBASE_KEY_FILE environment variables."
        )

    normalized_api, normalized_secret, _normalized_password = normalize_coinbase_credentials(
        raw_api,
        raw_secret,
        None,
    )
    validation_error = coinbase_validation_error(raw_api, raw_secret, password=None)
    if validation_error:
        raise SystemExit(f"Credential validation failed: {validation_error}")

    if args.show_normalized:
        normalized_summary = {
            "api_key": normalized_api,
            "api_key_masked": _mask_value(normalized_api),
            "secret_header": normalized_secret.splitlines()[0] if normalized_secret else None,
            "secret_length": len(normalized_secret or ""),
            "key_identifier_kind": (
                "advanced-trade-key-name"
                if "/" in str(normalized_api or "")
                else "uuid-style-key-id"
            ),
        }
        _print_json("Normalized Coinbase Credentials", normalized_summary)

    try:
        result = asyncio.run(
            _run_connection_test(
                api_key=normalized_api,
                secret=normalized_secret,
                sandbox=args.sandbox,
                symbol=args.symbol,
                market_type=args.market_type,
                derivative_subtype=args.derivative_subtype,
            )
        )
    except Exception as exc:
        detail = str(exc)
        if "401" in detail and "Unauthorized" in detail:
            detail = (
                f"{detail}\n"
                f"Normalized key: {masked_coinbase_key_id(normalized_api)}\n"
                "Coinbase accepted the request path but rejected the credentials. "
                "Double-check that the key has Coinbase Advanced Trade brokerage permissions, "
                "was created with the ECDSA/ES256 algorithm, and if your downloaded JSON includes a "
                "\"name\" field prefer pasting the full JSON bundle rather than only the UUID id."
            )
        raise SystemExit(f"Coinbase connection test failed: {detail}") from exc

    print("Coinbase connection test passed.\n")
    _print_json("Coinbase Test Result", result)


if __name__ == "__main__":
    main()
