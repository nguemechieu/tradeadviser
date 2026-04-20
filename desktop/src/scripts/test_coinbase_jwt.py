import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen



API_KEY = os.getenv("COINBASE_API_KEY", "").strip()
API_SECRET = os.getenv("COINBASE_API_SECRET", "")
REQUEST_METHOD = os.getenv("COINBASE_REQUEST_METHOD", "GET").upper().strip() or "GET"
REQUEST_PATH = os.getenv("COINBASE_REQUEST_PATH", "/api/v3/brokerage/accounts").strip() or "/api/v3/brokerage/accounts"
API_BASE_URL = os.getenv("COINBASE_API_BASE_URL", "https://api.coinbase.com").strip().rstrip("/") or "https://api.coinbase.com"
PRINT_JWT = str(os.getenv("COINBASE_PRINT_JWT", "false")).strip().lower() in {"1", "true", "yes", "on"}


def _validate_inputs():
    if not API_KEY.startswith("organizations/"):
        raise SystemExit(
            "Invalid COINBASE_API_KEY. Expected Coinbase Advanced Trade key name like "
            "`organizations/.../apiKeys/...`."
        )
    if "-----BEGIN" not in API_SECRET or "-----END" not in API_SECRET:
        raise SystemExit(
            "Invalid COINBASE_API_SECRET. Expected the full private key PEM including BEGIN/END lines."
        )
    if not REQUEST_PATH.startswith("/"):
        raise SystemExit("COINBASE_REQUEST_PATH must start with `/`.")
    if REQUEST_METHOD != "GET":
        raise SystemExit("This test script currently supports GET requests only.")


def build_jwt():
    jwt_uri = jwt_generator.format_jwt_uri(REQUEST_METHOD, REQUEST_PATH)
    return jwt_generator.build_rest_jwt(jwt_uri, API_KEY, API_SECRET)


def call_coinbase(jwt_token):
    url = f"{API_BASE_URL}{REQUEST_PATH}"
    request = Request(
        url,
        method=REQUEST_METHOD,
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "User-Agent": "Sopotek-Coinbase-Tester/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return response.status, body


def main():
    _validate_inputs()
    jwt_token = build_jwt()

    if PRINT_JWT:
        print("JWT:")
        print(jwt_token)
        print()

    try:
        status, body = call_coinbase(jwt_token)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} {exc.reason}")
        print(error_body)
        raise SystemExit(1) from exc
    except URLError as exc:
        print(f"Network error: {exc}")
        raise SystemExit(1) from exc

    print(f"HTTP {status}")
    try:
        payload = json.loads(body)
        print(json.dumps(payload, indent=2))
    except Exception:
        print(body)


if __name__ == "__main__":
    main()
