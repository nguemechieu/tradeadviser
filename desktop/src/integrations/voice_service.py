from __future__ import annotations
"""
InvestPro Voice Service

Provides:
- Text-to-speech playback.
- Voice recognition / dictation.
- Windows System.Speech support through PowerShell.
- Optional pyttsx3 text-to-speech fallback.
- Optional Google speech recognition through SpeechRecognition + sounddevice.
- Optional offline recognition hook for future Vosk integration.
- Cross-platform capability detection.
- Structured result objects.
- Safe timeouts and graceful failure.

Recommended optional packages:
    pip install pyttsx3 SpeechRecognition sound device

Notes:
- Windows native speech uses PowerShell + System.Speech.
- Google recognition requires internet access.
- sound device requires a usable microphone and Port Audio support.
"""

import asyncio

import logging
import platform
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class VoiceResult:
    ok: bool
    message: str
    text: str = ""
    provider: str = ""
    stdout: str = ""
    stderr: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "text": self.text,
            "provider": self.provider,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class VoiceInfo:
    id: str
    name: str
    provider: str
    language: str = ""
    gender: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "language": self.language,
            "gender": self.gender,
            "metadata": self.metadata,
        }


class VoiceService:
    """Cross-platform voice playback and speech recognition service."""

    SUPPORTED_TTS_PROVIDERS = {"auto", "windows", "pyttsx3"}
    SUPPORTED_RECOGNITION_PROVIDERS = {"auto", "windows", "google"}

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        voice_name: str = "",
        recognition_provider: str = "auto",
        tts_provider: str = "auto",
        *,
        speech_rate: int = 0,
        volume: float = 1.0,
        powershell_timeout_seconds: float = 45.0,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.is_windows = sys.platform.startswith("win")
        self.platform = platform.system().lower()

        self.voice_name = str(voice_name or "").strip()
        self.recognition_provider = self._normalize_provider(
            recognition_provider,
            allowed=self.SUPPORTED_RECOGNITION_PROVIDERS,
            default="auto",
        )
        self.tts_provider = self._normalize_provider(
            tts_provider,
            allowed=self.SUPPORTED_TTS_PROVIDERS,
            default="auto",
        )

        self.speech_rate = int(speech_rate or 0)
        self.volume = max(0.0, min(1.0, float(volume)))
        self.powershell_timeout_seconds = max(
            5.0, float(powershell_timeout_seconds))

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Return True if any text-to-speech provider is available."""
        return self.windows_tts_available() or self.pyttsx3_available()

    def listening_available(self) -> bool:
        """Return True if any speech recognition provider is available."""
        return self.windows_recognition_available() or self.google_recognition_available()

    def windows_tts_available(self) -> bool:
        return self.is_windows and self._powershell_executable() is not None

    def windows_recognition_available(self) -> bool:
        return self.is_windows and self._powershell_executable() is not None

    def pyttsx3_available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except Exception:
            return False

    def google_recognition_available(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            import speech_recognition  # noqa: F401
            return True
        except Exception:
            return False

    def available_tts_providers(self) -> list[tuple[str, str]]:
        providers = [("auto", "Auto")]

        if self.windows_tts_available():
            providers.append(("windows", "Windows Speech"))

        if self.pyttsx3_available():
            providers.append(("pyttsx3", "pyttsx3"))

        return providers

    def available_recognition_providers(self) -> list[tuple[str, str]]:
        providers = [("auto", "Auto")]

        if self.windows_recognition_available():
            providers.append(("windows", "Windows Speech"))

        if self.google_recognition_available():
            providers.append(("google", "Google Speech Recognition"))

        return providers

    def recognition_provider_available(self, provider: str) -> bool:
        normalized = self._normalize_provider(
            provider,
            allowed=self.SUPPORTED_RECOGNITION_PROVIDERS,
            default="auto",
        )

        if normalized == "auto":
            return self.listening_available()

        if normalized == "google":
            return self.google_recognition_available()

        if normalized == "windows":
            return self.windows_recognition_available()

        return False

    def tts_provider_available(self, provider: str) -> bool:
        normalized = self._normalize_provider(
            provider,
            allowed=self.SUPPORTED_TTS_PROVIDERS,
            default="auto",
        )

        if normalized == "auto":
            return self.available()

        if normalized == "windows":
            return self.windows_tts_available()

        if normalized == "pyttsx3":
            return self.pyttsx3_available()

        return False

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def set_voice(self, voice_name: str) -> None:
        self.voice_name = str(voice_name or "").strip()

    def set_recognition_provider(self, provider: str) -> None:
        self.recognition_provider = self._normalize_provider(
            provider,
            allowed=self.SUPPORTED_RECOGNITION_PROVIDERS,
            default="auto",
        )

    def set_tts_provider(self, provider: str) -> None:
        self.tts_provider = self._normalize_provider(
            provider,
            allowed=self.SUPPORTED_TTS_PROVIDERS,
            default="auto",
        )

    def set_speech_rate(self, rate: int) -> None:
        self.speech_rate = max(-10, min(10, int(rate or 0)))

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_voices(self, provider: str = "auto") -> list[str]:
        """Return voice names for the selected provider."""
        provider_name = self._select_tts_provider(provider)

        if provider_name == "windows":
            return await self._list_windows_voices()

        if provider_name == "pyttsx3":
            return await asyncio.to_thread(self._list_pyttsx3_voices)

        return []

    async def list_voice_infos(self, provider: str = "auto") -> list[dict[str, Any]]:
        """Return richer voice information when available."""
        provider_name = self._select_tts_provider(provider)

        if provider_name == "windows":
            names = await self._list_windows_voices()
            return [
                VoiceInfo(id=name, name=name, provider="windows").to_dict()
                for name in names
            ]

        if provider_name == "pyttsx3":
            return await asyncio.to_thread(self._list_pyttsx3_voice_infos)

        return []

    async def speak(
        self,
        text: Any,
        voice_name: Optional[str] = None,
        *,
        provider: str = "auto",
        rate: Optional[int] = None,
        volume: Optional[float] = None,
    ) -> dict[str, Any]:
        """Speak text through the selected TTS provider."""
        message = str(text or "").strip()

        if not message:
            return VoiceResult(
                ok=False,
                message="No text was provided to speak.",
                provider=provider,
            ).to_dict()

        provider_name = self._select_tts_provider(provider)

        if provider_name == "windows":
            return await self._speak_windows(
                message,
                voice_name=voice_name or self.voice_name,
                rate=self.speech_rate if rate is None else int(rate),
                volume=self.volume if volume is None else float(volume),
            )

        if provider_name == "pyttsx3":
            return await asyncio.to_thread(
                self._speak_pyttsx3_sync,
                message,
                voice_name or self.voice_name,
                self.speech_rate if rate is None else int(rate),
                self.volume if volume is None else float(volume),
            )

        return VoiceResult(
            ok=False,
            message="No text-to-speech provider is available.",
            provider=provider_name,
        ).to_dict()

    async def listen(
        self,
        timeout_seconds: int = 8,
        provider: Optional[str] = None,
    ) -> dict[str, Any]:
        """Listen for spoken input and return recognized text."""
        provider_name = self._select_recognition_provider(
            provider or self.recognition_provider)

        try:
            timeout_seconds = max(3, int(timeout_seconds))
        except Exception:
            timeout_seconds = 8

        if provider_name == "windows":
            return await self._listen_windows(timeout_seconds=timeout_seconds)

        if provider_name == "google":
            return await self._listen_google(timeout_seconds=timeout_seconds)

        return VoiceResult(
            ok=False,
            message="No voice recognition provider is available.",
            text="",
            provider=provider_name,
        ).to_dict()

    async def speak_and_listen(
        self,
        prompt: Any,
        *,
        timeout_seconds: int = 8,
        speak_provider: str = "auto",
        listen_provider: Optional[str] = None,
    ) -> dict[str, Any]:
        """Speak a prompt, then listen for an answer."""
        speak_result = await self.speak(prompt, provider=speak_provider)

        if not speak_result.get("ok"):
            return {
                "ok": False,
                "message": f"Could not speak prompt: {speak_result.get('message')}",
                "text": "",
                "speak_result": speak_result,
                "listen_result": None,
            }

        listen_result = await self.listen(timeout_seconds=timeout_seconds, provider=listen_provider)

        return {
            "ok": bool(listen_result.get("ok")),
            "message": listen_result.get("message", ""),
            "text": listen_result.get("text", ""),
            "speak_result": speak_result,
            "listen_result": listen_result,
        }

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------

    def _normalize_provider(self, provider: Any, *, allowed: set[str], default: str) -> str:
        normalized = str(provider or default).strip().lower() or default
        return normalized if normalized in allowed else default

    def _select_tts_provider(self, provider: str = "auto") -> str:
        requested = self._normalize_provider(
            provider if provider != "auto" else self.tts_provider,
            allowed=self.SUPPORTED_TTS_PROVIDERS,
            default="auto",
        )

        if requested == "windows" and self.windows_tts_available():
            return "windows"

        if requested == "pyttsx3" and self.pyttsx3_available():
            return "pyttsx3"

        if requested == "auto":
            if self.windows_tts_available():
                return "windows"
            if self.pyttsx3_available():
                return "pyttsx3"

        return ""

    def _select_recognition_provider(self, provider: str = "auto") -> str:
        requested = self._normalize_provider(
            provider,
            allowed=self.SUPPORTED_RECOGNITION_PROVIDERS,
            default="auto",
        )

        if requested == "windows" and self.windows_recognition_available():
            return "windows"

        if requested == "google" and self.google_recognition_available():
            return "google"

        if requested == "auto":
            if self.windows_recognition_available():
                return "windows"
            if self.google_recognition_available():
                return "google"

        return ""

    # ------------------------------------------------------------------
    # Windows System.Speech
    # ------------------------------------------------------------------

    async def _list_windows_voices(self) -> list[str]:
        script = (
            "Add-Type -AssemblyName System.Speech\n"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            "$synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }\n"
        )

        result = await self._run_powershell(script)

        if not result.get("ok"):
            return []

        voices = [
            line.strip()
            for line in str(result.get("stdout", "") or "").splitlines()
            if line.strip()
        ]

        return voices

    async def _speak_windows(
        self,
        text: str,
        *,
        voice_name: str = "",
        rate: int = 0,
        volume: float = 1.0,
    ) -> dict[str, Any]:
        if not self.windows_tts_available():
            return VoiceResult(
                ok=False,
                message="Windows voice playback is not available.",
                provider="windows",
            ).to_dict()

        script = self._powershell_speak_script(
            text,
            voice_name=voice_name,
            rate=rate,
            volume=volume,
        )

        return await self._run_powershell(
            script,
            success_message="Reply spoken.",
            provider="windows",
        )

    async def _listen_windows(self, timeout_seconds: int = 8) -> dict[str, Any]:
        if not self.windows_recognition_available():
            return VoiceResult(
                ok=False,
                message="Windows voice listening is not available.",
                text="",
                provider="windows",
            ).to_dict()

        script = self._powershell_listen_script(timeout_seconds)
        result = await self._run_powershell(script, provider="windows")

        if not result.get("ok"):
            result.setdefault("text", "")
            return result

        text = str(result.get("stdout", "") or "").strip()

        if not text:
            return VoiceResult(
                ok=False,
                message="No speech was detected.",
                text="",
                provider="windows",
                stdout=str(result.get("stdout", "")),
                stderr=str(result.get("stderr", "")),
            ).to_dict()

        return VoiceResult(
            ok=True,
            message="Voice prompt captured.",
            text=text,
            provider="windows",
            stdout=str(result.get("stdout", "")),
            stderr=str(result.get("stderr", "")),
        ).to_dict()

    async def _run_powershell(
        self,
        script: str,
        *,
        success_message: str = "OK",
        provider: str = "windows",
    ) -> dict[str, Any]:
        executable = self._powershell_executable()

        if executable is None:
            return VoiceResult(
                ok=False,
                message="PowerShell was not found.",
                provider=provider,
            ).to_dict()

        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.powershell_timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return VoiceResult(
                    ok=False,
                    message="Voice PowerShell command timed out.",
                    provider=provider,
                ).to_dict()

        except Exception as exc:
            self.logger.debug("Voice PowerShell launch failed: %s", exc)
            return VoiceResult(
                ok=False,
                message=f"Voice service failed to start: {exc}",
                provider=provider,
            ).to_dict()

        stdout_text = stdout.decode("utf-8", errors="ignore").strip()
        stderr_text = stderr.decode("utf-8", errors="ignore").strip()

        if process.returncode != 0:
            message = stderr_text or stdout_text or "Voice service failed."
            return VoiceResult(
                ok=False,
                message=message,
                provider=provider,
                stdout=stdout_text,
                stderr=stderr_text,
            ).to_dict()

        return VoiceResult(
            ok=True,
            message=success_message,
            provider=provider,
            stdout=stdout_text,
            stderr=stderr_text,

        ).to_dict()

    @staticmethod
    def _powershell_executable() -> Optional[str]:
        for name in ("powershell", "pwsh"):
            path = shutil.which(name)
            if path:
                return path
        return None

    def _powershell_speak_script(
        self,
        text: str,
        voice_name: str = "",
        *,
        rate: int = 0,
        volume: float = 1.0,
    ) -> str:
        escaped_text = self._escape_here_string(text)
        escaped_voice = self._escape_here_string(voice_name)
        safe_rate = max(-10, min(10, int(rate or 0)))
        safe_volume = max(0, min(100, int(float(volume) * 100)))

        return (
            "Add-Type -AssemblyName System.Speech\n"
            "$text = @'\n"
            f"{escaped_text}\n"
            "'@\n"
            "$voice = @'\n"
            f"{escaped_voice}\n"
            "'@\n"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            f"$synth.Rate = {safe_rate}\n"
            f"$synth.Volume = {safe_volume}\n"
            "if ($voice.Trim()) {\n"
            "  try { $synth.SelectVoice($voice.Trim()) } catch { }\n"
            "}\n"
            "$synth.SetOutputToDefaultAudioDevice()\n"
            "$synth.Speak($text)\n"
            "Write-Output 'spoken'\n"
        )

    def _powershell_listen_script(self, timeout_seconds: int) -> str:
        safe_timeout = max(3, int(timeout_seconds))

        return (
            "Add-Type -AssemblyName System.Speech\n"
            "try {\n"
            "  $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine\n"
            "  $engine.SetInputToDefaultAudioDevice()\n"
            "  $grammar = New-Object System.Speech.Recognition.DictationGrammar\n"
            "  $engine.LoadGrammar($grammar)\n"
            "  $engine.InitialSilenceTimeout = [TimeSpan]::FromSeconds(5)\n"
            "  $engine.BabbleTimeout = [TimeSpan]::FromSeconds(2)\n"
            "  $engine.EndSilenceTimeout = [TimeSpan]::FromSeconds(1)\n"
            f"  $result = $engine.Recognize([TimeSpan]::FromSeconds({safe_timeout}))\n"
            "  if ($result -and $result.Text) {\n"
            "    Write-Output $result.Text\n"
            "  }\n"
            "} catch {\n"
            "  Write-Error $_.Exception.Message\n"
            "  exit 1\n"
            "}\n"
        )

    def _escape_here_string(self, value: Any) -> str:
        # Prevent terminating the PowerShell here-string accidentally.
        return str(value or "").replace("'@", "'@ ")

    # ------------------------------------------------------------------
    # pyttsx3 TTS
    # ------------------------------------------------------------------

    def _list_pyttsx3_voices(self) -> list[str]:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            result = [str(getattr(voice, "name", "") or getattr(
                voice, "id", "")).strip() for voice in voices]
            try:
                engine.stop()
            except Exception:
                pass
            return [item for item in result if item]

        except Exception as exc:
            self.logger.debug("pyttsx3 voice listing failed: %s", exc)
            return []

    def _list_pyttsx3_voice_infos(self) -> list[dict[str, Any]]:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            output: list[dict[str, Any]] = []

            for voice in voices:
                voice_id = str(getattr(voice, "id", "") or "")
                name = str(getattr(voice, "name", "") or voice_id)
                languages = getattr(voice, "languages", []) or []
                language = ""
                if languages:
                    language = str(languages[0])

                output.append(
                    VoiceInfo(
                        id=voice_id,
                        name=name,
                        provider="pyttsx3",
                        language=language,
                        gender=str(getattr(voice, "gender", "") or ""),
                        metadata={
                            "age": getattr(voice, "age", None),
                            "languages": [str(item) for item in languages],
                        },
                    ).to_dict()
                )

            try:
                engine.stop()
            except Exception:
                raise

            return output

        except Exception as exc:
            self.logger.debug("pyttsx3 voice info listing failed: %s", exc)
            return []

    def _speak_pyttsx3_sync(
        self,
        text: str,
        voice_name: str = "",
        rate: int = 0,
        volume: float = 1.0,
    ) -> dict[str, Any]:
        try:
            import pyttsx3

            engine = pyttsx3.init()

            voices = engine.getProperty("voices") or []
            selected_voice_id = ""

            if voice_name:
                lookup = voice_name.strip().lower()
                for voice in voices:
                    voice_id = str(getattr(voice, "id", "") or "")
                    name = str(getattr(voice, "name", "") or "")
                    if lookup in voice_id.lower() or lookup in name.lower():
                        selected_voice_id = voice_id
                        break

            if selected_voice_id:
                engine.setProperty("voice", selected_voice_id)

            current_rate = int(engine.getProperty("rate") or 200)
            adjusted_rate = max(
                80, min(400, current_rate + (int(rate or 0) * 15)))
            engine.setProperty("rate", adjusted_rate)
            engine.setProperty("volume", max(0.0, min(1.0, float(volume))))

            engine.say(text)
            engine.runAndWait()

            try:
                engine.stop()
            except Exception:
                raise

            return VoiceResult(
                ok=True,
                message="Reply spoken.",
                provider="pyttsx3",
                metadata={
                    "voice": selected_voice_id or voice_name,
                    "rate": adjusted_rate,
                    "volume": volume,
                },
            ).to_dict()

        except Exception as exc:
            self.logger.debug("pyttsx3 speak failed: %s", exc)
            return VoiceResult(
                ok=False,
                message=f"pyttsx3 voice playback failed: {exc}",
                provider="pyttsx3",
            ).to_dict()

    # ------------------------------------------------------------------
    # Google recognition
    # ------------------------------------------------------------------

    async def _listen_google(self, timeout_seconds: int = 8) -> dict[str, Any]:
        if not self.google_recognition_available():
            return VoiceResult(
                ok=False,
                message="Google voice recognition requires optional packages 'SpeechRecognition' and 'sounddevice'.",
                text="",
                provider="google",
            ).to_dict()

        try:
            import sounddevice as sd
            import speech_recognition as sr
        except Exception as exc:
            return VoiceResult(
                ok=False,
                message=f"Google voice recognition is unavailable: {exc}",
                text="",
                provider="google",
            ).to_dict()

        sample_rate = 16000

        try:
            audio = await asyncio.to_thread(
                self._record_audio_google,
                sd,
                timeout_seconds,
                sample_rate,
            )

        except Exception as exc:
            return VoiceResult(
                ok=False,
                message=self._describe_google_recording_error(
                    exc, sounddevice_module=sd),
                text="",
                provider="google",
            ).to_dict()

        try:
            recognizer = sr.Recognizer()
            audio_data = sr.AudioData(audio.tobytes(), sample_rate, 2)
            language="ENGLISH"
            show_all=False
            text = await asyncio.to_thread(recognizer.recognize_bing(audio_data,language,show_all), audio_data)

        except Exception as exc:
            return VoiceResult(
                ok=False,
                message=self._describe_google_transcription_error(
                    exc, speech_recognition_module=sr),
                text="",
                provider="google",
            ).to_dict()

        text = str(text or "").strip()

        if not text:
            return VoiceResult(
                ok=False,
                message="No speech was detected.",
                text="",
                provider="google",
            ).to_dict()

        return VoiceResult(
            ok=True,
            message="Google voice prompt captured.",
            text=text,
            provider="google",
        ).to_dict()

    def _record_audio_google(self, sounddevice_module: Any, timeout_seconds: int, sample_rate: int) -> Any:
        recording = sounddevice_module.rec(
            int(timeout_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sounddevice_module.wait()
        return recording.flatten()

    def _describe_google_recording_error(
        self,
        exc: BaseException,
        sounddevice_module: Any = None,
    ) -> str:
        detail = str(exc or "").strip()
        portaudio_error = (
            getattr(sounddevice_module, "PortAudioError", None)
            if sounddevice_module is not None
            else None
        )
        lowered = detail.lower()

        if (portaudio_error is not None and isinstance(exc, portaudio_error)) or isinstance(exc, OSError):
            return self._format_google_failure(
                "Google voice recognition could not access the microphone.",
                detail,
            )

        if "input device" in lowered or "device unavailable" in lowered or "invalid number of channels" in lowered:
            return self._format_google_failure(
                "Google voice recognition could not access a usable microphone input device.",
                detail,
            )

        return self._format_google_failure(
            "Google voice recognition failed while recording audio.",
            detail,
        )

    def _describe_google_transcription_error(
        self,
        exc: BaseException,
        speech_recognition_module: Any = None,
    ) -> str:
        detail = str(exc or "").strip()

        unknown_value_error = (
            getattr(speech_recognition_module, "UnknownValueError", None)
            if speech_recognition_module is not None
            else None
        )

        request_error = (
            getattr(speech_recognition_module, "RequestError", None)
            if speech_recognition_module is not None
            else None
        )

        lowered = detail.lower()

        if unknown_value_error is not None and isinstance(exc, unknown_value_error):
            return "Google voice recognition could not understand the audio. Please speak clearly and try again."

        if request_error is not None and isinstance(exc, request_error):
            return self._format_google_failure(
                "Google voice recognition could not reach the Google speech service. Check your internet connection and try again.",
                detail,
            )

        if "timed out" in lowered or "timeout" in lowered:
            return self._format_google_failure(
                "Google voice recognition timed out while waiting for transcription.",
                detail,
            )

        return self._format_google_failure(
            "Google voice recognition failed during transcription.",
            detail,
        )

    def _format_google_failure(self, summary: str, detail: str) -> str:
        cleaned_detail = str(detail or "").strip()

        if not cleaned_detail:
            return summary

        if cleaned_detail.lower() in summary.lower():
            return summary

        return f"{summary} Details: {cleaned_detail}"
