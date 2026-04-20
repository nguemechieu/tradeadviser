import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController
from frontend.ui.terminal import Terminal


def _controller_stub():
    controller = AppController.__new__(AppController)
    controller.voice_provider = "windows"
    controller.voice_output_provider = "openai"
    controller.voice_windows_name = "Microsoft David Desktop"
    controller.voice_openai_name = "alloy"
    controller.openai_api_key = ""
    controller.voice_service = None
    return controller


def test_market_chat_voice_output_available_falls_back_to_windows_when_openai_key_is_missing():
    controller = _controller_stub()
    controller.voice_service = SimpleNamespace(available=lambda: True, recognition_provider_available=lambda _provider: True)

    assert controller.market_chat_voice_output_available() is True

    state = controller.market_chat_voice_state()

    assert state["output_provider"] == "openai"
    assert state["effective_output_provider"] == "windows"
    assert state["output_fallback"] is True


def test_market_chat_speak_uses_windows_voice_when_openai_is_selected_without_key():
    calls = []

    async def _speak(text, voice_name=None):
        calls.append((text, voice_name))
        return {"ok": True, "message": "Reply spoken."}

    controller = _controller_stub()
    controller.voice_service = SimpleNamespace(available=lambda: True, speak=_speak)

    result = asyncio.run(controller.market_chat_speak("Pilot reply"))

    assert result["ok"] is True
    assert calls == [("Pilot reply", "Microsoft David Desktop")]


def test_market_chat_speak_falls_back_to_windows_after_openai_playback_error():
    calls = []

    async def _speak(text, voice_name=None):
        calls.append((text, voice_name))
        return {"ok": True, "message": "Reply spoken."}

    async def _openai_speak(_text, voice_name="alloy"):
        return {"ok": False, "message": f"OpenAI failed for {voice_name}"}

    controller = _controller_stub()
    controller.openai_api_key = "sk-test"
    controller.voice_service = SimpleNamespace(available=lambda: True, speak=_speak)
    controller._market_chat_speak_openai = _openai_speak

    result = asyncio.run(controller.market_chat_speak("Pilot reply"))

    assert result["ok"] is True
    assert "Used Windows speech instead" in result["message"]
    assert calls == [("Pilot reply", "Microsoft David Desktop")]


def test_market_chat_voice_state_text_mentions_windows_fallback_for_openai():
    fake = SimpleNamespace(
        controller=SimpleNamespace(
            market_chat_voice_state=lambda: {
                "provider": "windows",
                "recognition_provider": "windows",
                "output_provider": "openai",
                "effective_output_provider": "windows",
                "output_fallback": True,
                "voice_name": "Microsoft David Desktop",
                "google_available": False,
                "openai_available": False,
            }
        )
    )

    text = Terminal._market_chat_voice_state_text(fake)

    assert "OpenAI is unavailable" in text
    assert "Windows speech" in text


def test_set_market_chat_auto_speak_persists_setting_and_refreshes_status():
    writes = []
    messages = []
    window = object()
    fake = SimpleNamespace(
        settings=SimpleNamespace(setValue=lambda key, value: writes.append((key, value))),
        detached_tool_windows={"market_chatgpt": window},
        _is_qt_object_alive=lambda obj: obj is not None,
        _refresh_market_chat_window=lambda current_window=None, status_message=None: messages.append(
            (current_window, status_message)
        ),
    )

    Terminal._set_market_chat_auto_speak(fake, True, window)

    assert writes == [("market_chat/auto_speak", True)]
    assert messages == [
        (
            window,
            "Auto Speak enabled. Sopotek Pilot replies will be spoken automatically.",
        )
    ]
