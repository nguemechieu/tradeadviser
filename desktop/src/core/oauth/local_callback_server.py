from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit


DEFAULT_SUCCESS_HTML = (
    "<html><body style='font-family:Segoe UI, sans-serif; padding: 24px;'>"
    "<h2>Authentication complete</h2>"
    "<p>You may return to Sopotek Quant System.</p>"
    "</body></html>"
)


@dataclass(slots=True)
class OAuthCallbackPayload:
    redirect_url: str
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None
    query: dict[str, str] = field(default_factory=dict)

    def validate_state(self, expected_state: str | None) -> None:
        if expected_state and str(self.state or "").strip() != str(expected_state).strip():
            raise ValueError("OAuth callback state did not match the expected value.")


def parse_oauth_callback_url(url: str) -> OAuthCallbackPayload:
    parsed = urlsplit(str(url or "").strip())
    query = {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}
    return OAuthCallbackPayload(
        redirect_url=str(url or "").strip(),
        code=query.get("code"),
        state=query.get("state"),
        error=query.get("error"),
        error_description=query.get("error_description"),
        query=query,
    )


class LocalOAuthCallbackServer:
    """Minimal localhost callback receiver for OAuth authorization-code flows."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        path: str,
        logger: logging.Logger | None = None,
        success_html: str = DEFAULT_SUCCESS_HTML,
    ) -> None:
        self.host = str(host or "127.0.0.1").strip() or "127.0.0.1"
        self.port = int(port)
        self.path = "/" + str(path or "/").lstrip("/")
        self.logger = logger or logging.getLogger("LocalOAuthCallbackServer")
        self.success_html = str(success_html or DEFAULT_SUCCESS_HTML)
        self._server: asyncio.base_events.Server | None = None
        self._callback_future: asyncio.Future[OAuthCallbackPayload] | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        loop = asyncio.get_running_loop()
        self._callback_future = loop.create_future()
        self._server = await asyncio.start_server(self._handle_client, host=self.host, port=self.port)

    async def close(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()
        future = self._callback_future
        self._callback_future = None
        if future is not None and not future.done():
            future.cancel()

    async def wait_for_callback(self, *, expected_state: str | None = None, timeout_seconds: float = 180.0) -> OAuthCallbackPayload:
        if self._server is None or self._callback_future is None:
            await self.start()
        assert self._callback_future is not None
        payload = await asyncio.wait_for(self._callback_future, timeout=max(1.0, float(timeout_seconds or 180.0)))
        payload.validate_state(expected_state)
        if payload.error:
            raise RuntimeError(str(payload.error_description or payload.error))
        if not payload.code:
            raise RuntimeError("OAuth callback did not include an authorization code.")
        return payload

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            parts = request_line.decode("utf-8", errors="ignore").strip().split()
            target = parts[1] if len(parts) >= 2 else "/"
            while True:
                line = await reader.readline()
                if not line or line in {b"\r\n", b"\n"}:
                    break

            parsed = urlsplit(target)
            if parsed.path == self.path:
                redirect_url = f"http://{self.host}:{self.port}{target}"
                payload = parse_oauth_callback_url(redirect_url)
                if self._callback_future is not None and not self._callback_future.done():
                    self._callback_future.set_result(payload)
            body = self.success_html.encode("utf-8")
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("utf-8")
                + b"Connection: close\r\n\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        except Exception:
            self.logger.debug("OAuth callback handler failed", exc_info=True)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
