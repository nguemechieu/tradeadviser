import json
import re
from typing import Dict, Iterable, Optional, Tuple


ADVANCED_KEY_NAME_RE = re.compile(r"^organizations/[^/\s]+/apiKeys/[^/\s]+$")
UUID_KEY_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
PEM_HEADER_RE = re.compile(r"-----BEGIN [A-Z ]+-----")
PEM_FOOTER_RE = re.compile(r"-----END [A-Z ]+-----")
BASE64_BODY_RE = re.compile(r"^[A-Za-z0-9+/=]+$")

API_KEY_FIELDS = (
    "apiKeyName",
    "api_key_name",
    "apiKeyId",
    "api_key_id",
    "keyId",
    "key_id",
    "apikey",
    "api_key",
    "name",
    "key_name",
    "key",
    "id",
)
SECRET_FIELDS = ("privateKey", "private_key", "privatePem", "private_pem", "secret")
PASSWORD_FIELDS = ("passphrase", "password")


def strip_wrapped_quotes(value) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _normalize_field_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())


def _iter_mapping_items(mapping: dict) -> Iterable[Tuple[str, object]]:
    for key, value in (mapping or {}).items():
        yield str(key), value
        if isinstance(value, dict):
            yield from _iter_mapping_items(value)


def _extract_fields_from_mapping(mapping: dict) -> Dict[str, str]:
    flattened: Dict[str, str] = {}
    for key, value in _iter_mapping_items(mapping):
        if isinstance(value, (str, int, float)):
            normalized_name = _normalize_field_name(key)
            text = strip_wrapped_quotes(value)
            if normalized_name and text:
                flattened.setdefault(normalized_name, text)

    resolved: Dict[str, str] = {}
    for target, field_names in (
        ("api_key", API_KEY_FIELDS),
        ("secret", SECRET_FIELDS),
        ("password", PASSWORD_FIELDS),
    ):
        for field_name in field_names:
            candidate = flattened.get(_normalize_field_name(field_name))
            if candidate:
                resolved[target] = candidate
                break
    return resolved


def _extract_fields_from_text(text: str) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    patterns = (
        ("api_key", API_KEY_FIELDS),
        ("secret", SECRET_FIELDS),
        ("password", PASSWORD_FIELDS),
    )
    for target, field_names in patterns:
        for field_name in field_names:
            match = re.search(
                rf'"{re.escape(field_name)}"\s*:\s*"(?P<value>(?:\\.|[^"])*)"',
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match:
                resolved[target] = strip_wrapped_quotes(match.group("value"))
                break
    return resolved


def _parse_coinbase_payloads(*values) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    for raw_value in values:
        text = strip_wrapped_quotes(raw_value)
        if not text:
            continue

        try:
            payload = json.loads(text)
        except Exception:
            payload = None

        if isinstance(payload, dict):
            for key, value in _extract_fields_from_mapping(payload).items():
                resolved.setdefault(key, value)

        for key, value in _extract_fields_from_text(text).items():
            resolved.setdefault(key, value)

        if "api_key" not in resolved and looks_like_coinbase_api_key(text):
            resolved["api_key"] = text
        if "secret" not in resolved and (
            "-----BEGIN" in text
            or "\\n" in text
            or ("\n" in text and "PRIVATE KEY" in text)
            or looks_like_coinbase_private_key_body(text)
        ):
            resolved["secret"] = text
    return resolved


def looks_like_coinbase_api_key(value) -> bool:
    text = strip_wrapped_quotes(value)
    return bool(text) and (
        ADVANCED_KEY_NAME_RE.fullmatch(text) is not None or UUID_KEY_ID_RE.fullmatch(text) is not None
    )


def looks_like_coinbase_private_key_body(value) -> bool:
    text = strip_wrapped_quotes(value)
    if not text:
        return False
    condensed = re.sub(r"\s+", "", text)
    return len(condensed) >= 48 and BASE64_BODY_RE.fullmatch(condensed) is not None


def normalize_coinbase_api_key(api_key, secret=None, password=None) -> Optional[str]:
    parsed = _parse_coinbase_payloads(api_key, secret, password)
    normalized = strip_wrapped_quotes(parsed.get("api_key") or api_key)
    return normalized or None


def normalize_coinbase_secret(api_key, secret=None, password=None) -> Optional[str]:
    parsed = _parse_coinbase_payloads(api_key, secret, password)
    normalized = strip_wrapped_quotes(parsed.get("secret") or secret)
    if not normalized:
        return None

    if "\\n" in normalized:
        normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").strip()

    header_match = PEM_HEADER_RE.search(normalized)
    footer_match = PEM_FOOTER_RE.search(normalized)
    if header_match and footer_match and header_match.start() < footer_match.start():
        header = header_match.group(0)
        footer = footer_match.group(0)
        middle_raw = normalized[header_match.end():footer_match.start()]
        body_lines = [line.strip() for line in middle_raw.splitlines() if line.strip()]
        if body_lines:
            middle = (
                "\n".join(body_lines)
                if ("\n" in middle_raw or "\r" in middle_raw)
                else re.sub(r"\s+", "", "".join(body_lines))
            )
            return f"{header}\n{middle}\n{footer}\n"
        return f"{header}\n{footer}\n"

    condensed = re.sub(r"\s+", "", normalized)
    if looks_like_coinbase_private_key_body(condensed):
        return f"-----BEGIN EC PRIVATE KEY-----\n{condensed}\n-----END EC PRIVATE KEY-----\n"

    return normalized


def normalize_coinbase_credentials(api_key, secret=None, password=None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    parsed = _parse_coinbase_payloads(api_key, secret, password)
    normalized_api = normalize_coinbase_api_key(api_key, secret, password)
    normalized_secret = normalize_coinbase_secret(api_key, secret, password)
    normalized_password = strip_wrapped_quotes(parsed.get("password") or password) or None
    return normalized_api, normalized_secret, normalized_password


def coinbase_validation_error(api_key, secret, password=None) -> Optional[str]:
    normalized_api, normalized_secret, normalized_password = normalize_coinbase_credentials(api_key, secret, password)

    if normalized_password:
        return (
            "Coinbase in Sopotek does not use the passphrase field. "
            "Paste the key name or key id in the first field, or paste the full Coinbase key JSON."
        )

    if not normalized_api:
        return (
            "Coinbase credentials are missing the key identifier. Paste either the "
            "Advanced Trade key name, the newer key id, or the full Coinbase key JSON."
        )

    if not looks_like_coinbase_api_key(normalized_api):
        return (
            "Coinbase key format is not recognized. Use either organizations/.../apiKeys/... "
            "or the newer UUID-style key id from Coinbase."
        )

    if not normalized_secret:
        return (
            "Coinbase private key is missing. Paste the privateKey value or the full Coinbase key JSON."
        )

    header_match = PEM_HEADER_RE.search(normalized_secret)
    footer_match = PEM_FOOTER_RE.search(normalized_secret)
    if header_match is None or footer_match is None or header_match.start() >= footer_match.start():
        return (
            "Coinbase private key is malformed. Paste the full privateKey value, or the full Coinbase key JSON."
        )

    body = normalized_secret[header_match.end():footer_match.start()]
    body_lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not body_lines:
        return (
            "Coinbase private key is missing its encoded body. Paste the full privateKey value from Coinbase."
        )

    if len("".join(body_lines)) < 32:
        return (
            "Coinbase private key looks truncated. Paste the complete privateKey value, not a shortened snippet."
        )

    return None
