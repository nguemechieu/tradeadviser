from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

from sopotek.apps.desktop.src.controllers.session_controller import SessionController
from sopotek.shared.contracts.base import ApiResponseEnvelope
from sopotek.shared.contracts.session import BrokerSessionSummary, SessionState
from sopotek.shared.enums.common import BrokerKind, SessionStatus
from sopotek.shared.events.base import ServerEventEnvelope


class _FakeApiClient:
    def __init__(self) -> None:
        self.auth_token = None
        self.closed = False

    async def login(self, request):
        session = SessionState(
            session_id="sess_123",
            status=SessionStatus.AUTHENTICATED,
            user=BrokerSessionSummary(
                user_id=request.username,
                account_id="acct_demo",
                broker=BrokerKind.PAPER,
            ),
            access_token="token_abc",
            refresh_token="refresh_xyz",
        )
        return ApiResponseEnvelope[SessionState].success_envelope(data=session, message="ok")

    async def resume_session(self, session_id):
        session = SessionState(
            session_id=session_id,
            status=SessionStatus.ACTIVE,
            user=BrokerSessionSummary(
                user_id="operator",
                account_id="acct_demo",
                broker=BrokerKind.PAPER,
            ),
            access_token="token_resume",
        )
        return ApiResponseEnvelope[SessionState].success_envelope(data=session, message="ok")

    def set_auth_token(self, token):
        self.auth_token = token

    async def close(self):
        self.closed = True


class _FakeWsClient:
    def __init__(self) -> None:
        self.auth_token = None
        self.bound_handler = None
        self.started_with = None
        self.stopped = False

    def set_auth_token(self, token):
        self.auth_token = token

    def bind_handler(self, handler):
        self.bound_handler = handler

    async def start(self, session_id):
        self.started_with = session_id

    async def stop(self):
        self.stopped = True


def test_session_controller_login_sets_tokens_and_starts_stream():
    async def runner():
        api_client = _FakeApiClient()
        ws_client = _FakeWsClient()
        captured = []

        async def on_event(event):
            captured.append(event.event_type)

        controller = SessionController(
            api_client=api_client,
            ws_client=ws_client,
            event_callback=on_event,
        )

        session = await controller.login("operator@sopotek.test", "demo-password")

        assert session.session_id == "sess_123"
        assert api_client.auth_token == "token_abc"
        assert ws_client.auth_token == "token_abc"
        assert ws_client.started_with == "sess_123"
        assert ws_client.bound_handler is not None

        await controller.handle_server_event(
            ServerEventEnvelope[dict](
                event_type="session.validated",
                sequence=1,
                payload={"session_id": "sess_123"},
            )
        )

        assert controller.degraded is False
        assert captured == ["session.validated"]

    asyncio.run(runner())


def test_session_controller_close_clears_runtime_state():
    async def runner():
        api_client = _FakeApiClient()
        ws_client = _FakeWsClient()
        controller = SessionController(api_client=api_client, ws_client=ws_client)
        controller.session_state = SessionState(
            session_id="sess_456",
            status=SessionStatus.ACTIVE,
            user=BrokerSessionSummary(
                user_id="operator",
                account_id="acct_demo",
                broker=BrokerKind.PAPER,
            ),
            access_token="token_456",
        )
        controller.degraded = True

        await controller.close()

        assert controller.session_state is None
        assert controller.degraded is False
        assert api_client.closed is True
        assert ws_client.stopped is True

    asyncio.run(runner())

if __name__ == "__main__":
    test_session_controller_login_sets_tokens_and_starts_stream()
    test_session_controller_close_clears_runtime_state()
