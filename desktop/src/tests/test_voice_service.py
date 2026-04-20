import asyncio
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.voice_service import VoiceService


class _FakeRecording:
    def flatten(self):
        return self

    def tobytes(self):
        return b"\x00\x00\x00\x00"


def _install_google_modules(monkeypatch, *, recording_error=None, recognition_error=None, recognition_text="captured text"):
    sounddevice_module = ModuleType("sounddevice")

    class PortAudioError(Exception):
        pass

    def _rec(*_args, **_kwargs):
        if recording_error == "portaudio":
            raise PortAudioError("No input device available")
        return _FakeRecording()

    sounddevice_module.PortAudioError = PortAudioError
    sounddevice_module.default = SimpleNamespace(device=[1, 3])
    sounddevice_module.rec = _rec
    sounddevice_module.wait = lambda: None

    speech_recognition_module = ModuleType("speech_recognition")

    class UnknownValueError(Exception):
        pass

    class RequestError(Exception):
        pass

    class AudioData:
        def __init__(self, data, sample_rate, sample_width):
            self.data = data
            self.sample_rate = sample_rate
            self.sample_width = sample_width

    class Recognizer:
        def recognize_google(self, _audio_data):
            if recognition_error == "unknown":
                raise UnknownValueError()
            if recognition_error == "request":
                raise RequestError("temporary outage")
            return recognition_text

    speech_recognition_module.UnknownValueError = UnknownValueError
    speech_recognition_module.RequestError = RequestError
    speech_recognition_module.AudioData = AudioData
    speech_recognition_module.Recognizer = Recognizer

    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice_module)
    monkeypatch.setitem(sys.modules, "speech_recognition", speech_recognition_module)


def test_google_listen_reports_missing_optional_packages():
    service = VoiceService()
    service._google_recognition_available = lambda: False

    result = asyncio.run(service._listen_google())

    assert result == {
        "ok": False,
        "message": "Google voice recognition requires the optional packages 'SpeechRecognition' and 'sounddevice'.",
        "text": "",
    }


def test_google_listen_reports_microphone_access_error(monkeypatch):
    service = VoiceService()
    service._google_recognition_available = lambda: True
    _install_google_modules(monkeypatch, recording_error="portaudio")

    result = asyncio.run(service._listen_google())

    assert result["ok"] is False
    assert "could not access the microphone" in result["message"]
    assert "No input device available" in result["message"]


def test_google_listen_reports_unclear_audio(monkeypatch):
    service = VoiceService()
    service._google_recognition_available = lambda: True
    _install_google_modules(monkeypatch, recognition_error="unknown")

    result = asyncio.run(service._listen_google())

    assert result == {
        "ok": False,
        "message": "Google voice recognition could not understand the audio. Please speak clearly and try again.",
        "text": "",
    }


def test_google_listen_reports_google_request_error(monkeypatch):
    service = VoiceService()
    service._google_recognition_available = lambda: True
    _install_google_modules(monkeypatch, recognition_error="request")

    result = asyncio.run(service._listen_google())

    assert result["ok"] is False
    assert "could not reach the Google speech service" in result["message"]
    assert "temporary outage" in result["message"]


def test_google_listen_returns_transcribed_text(monkeypatch):
    service = VoiceService()
    service._google_recognition_available = lambda: True
    _install_google_modules(monkeypatch, recognition_text="buy 1 contract")

    result = asyncio.run(service._listen_google())

    assert result == {
        "ok": True,
        "message": "Google voice prompt captured.",
        "text": "buy 1 contract",
    }
