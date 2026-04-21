"""Desktop entrypoint for the TradeAdviser application."""

# cspell:words qasync sopotek timerid getpid gaierror clientconnectordnserror

from __future__ import annotations

import asyncio
import contextlib
import faulthandler
import importlib
import os
import socket
import sys
from pathlib import Path
from typing import Any, TextIO

# Configure UTF-8 encoding IMMEDIATELY to prevent charmap errors on Windows
# This must happen before any other imports that create loggers
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


_FAULTHANDLER_STATE: dict[str, TextIO | None] = {"stream": None}
_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
_VALID_AI_DEVICES = {"cpu", "cuda", "dml", "mps"}


def _src_root() -> Path:
    """Get the absolute path to the src directory.

    Returns
    -------
    Path
        The directory containing this script.
    """
    return Path(__file__).resolve().parent


def _ensure_src_on_path() -> None:
    """Add the src directory to Python's module search path.

    This enables importing of local modules from the src directory.
    """
    import os as _os_module
    
    src_root_str = _os_module.path.abspath(_os_module.path.dirname(__file__))
    project_root_str = _os_module.path.dirname(_os_module.path.dirname(src_root_str))
    backend_str = _os_module.path.join(project_root_str, "server", "app", "backend")
    
    # Normalize paths for comparison
    src_root_str = _os_module.path.normpath(src_root_str)
    project_root_str = _os_module.path.normpath(project_root_str)
    backend_str = _os_module.path.normpath(backend_str)
    
    # Clear existing entries and add in correct order (backend, project, src)
    sys.path = [p for p in sys.path if p not in (src_root_str, project_root_str, backend_str)]
    
    # Add in reverse priority order so src is first
    sys.path.insert(0, backend_str)
    sys.path.insert(0, project_root_str)
    sys.path.insert(0, src_root_str)


# Ensure src is on path BEFORE importing any local modules
_ensure_src_on_path()

# Import backend package to register 'sopotek' namespace by modifying sys.modules
# This is needed for imports like "from sopotek.shared.contracts import ..."
_backend_path = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    '..',
    'server', 'app', 'backend'
))
if _backend_path in sys.path:
    # Load the backend __init__.py to set up sopotek namespace
    import importlib.util
    _spec = importlib.util.spec_from_file_location("__backend_init__", os.path.join(_backend_path, '__init__.py'))
    if _spec and _spec.loader:
        _backend_init = importlib.util.module_from_spec(_spec)
        sys.modules['__backend_init__'] = _backend_init
        try:
            _spec.loader.exec_module(_backend_init)
        except Exception:
            pass  # If backend init fails, continue with fallback imports

# Delayed import of PySide6 to avoid interfering with local module imports  
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    # If PySide6 not available, we'll error later anyway
    QtCore = QtGui = QtWidgets = None


def _load_qeventloop() -> type[Any]:
    """Load and return the qasync QEventLoop class.

    Returns
    -------
    type[Any]
        The QEventLoop class from the qasync module.
    """
    qasync_module = importlib.import_module("qasync")
    _patch_qasync_duplicate_timer_keyerror(qasync_module)
    return qasync_module.QEventLoop


def _patch_qasync_duplicate_timer_keyerror(qasync_module: Any) -> bool:
    """Guard qasync against duplicate timer callbacks raising ``KeyError``.

    On some Windows/Python combinations, qasync can receive a duplicate
    ``timerEvent`` after its internal callback entry has already been removed.
    That failure is noisy and can destabilize lightweight UI actions. We keep
    the original behavior for everything else and only swallow that specific
    missing-callback case.
    """
    timer_cls = getattr(qasync_module, "_SimpleTimer", None)
    timer_event = getattr(timer_cls, "timerEvent", None)
    if timer_cls is None or not callable(timer_event):
        return False
    if getattr(timer_event, "_sopotek_duplicate_timer_guard", False):
        return False

    def guarded_timer_event(self: Any, event: Any) -> Any:
        try:
            return timer_event(self, event)
        except KeyError:
            with contextlib.suppress(Exception):
                if event is not None and hasattr(event, "accept"):
                    event.accept()
            return None
    guarded_timer_event._sopotek_duplicate_timer_guard = True  # type: ignore[attr-defined]
    timer_cls.timerEvent = guarded_timer_event
    return True


def _load_app_controller() -> type[Any]:
    """Load and return the AppController class from the ui module.

    Returns
    -------
    type[Any]
        The AppController class.
    """
    from ui.components.app_controller import AppController
    return AppController


def _local_x11_socket(display: str | None) -> str | None:
    """Return the expected Unix socket path for a local X11 display."""
    value = str(display or "").strip()
    if not value:
        return None
    if value.lower().startswith("unix/"):
        value = value[5:]
    if not value.startswith(":"):
        return None

    display_id = value[1:].split(".", 1)[0].strip()
    if not display_id.isdigit():
        return None
    return f"/tmp/.X11-unix/X{display_id}"


def _has_usable_linux_display() -> bool:
    """Check whether the current Linux display environment is usable."""
    display = str(os.getenv("DISPLAY") or "").strip()
    wayland_display = str(os.getenv("WAYLAND_DISPLAY") or "").strip()
    if not (display or wayland_display):
        return False

    socket_path = _local_x11_socket(display)
    if socket_path and not os.path.exists(socket_path):
        return False
    return True


def _configure_qt_platform() -> str | None:
    """Choose a safe Qt platform plugin for the current environment."""
    configured = str(os.getenv("QT_QPA_PLATFORM") or "").strip()
    if configured:
        return configured

    if sys.platform.startswith("linux") and not _has_usable_linux_display():
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        return "offscreen"

    return None


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in _TRUE_ENV_VALUES


def _append_chromium_flag(existing_flags: str, flag: str) -> str:
    text = str(existing_flags or "").strip()
    normalized_flag = str(flag or "").strip()
    if not normalized_flag:
        return text
    parts = text.split()
    if normalized_flag in parts:
        return text
    return f"{text} {normalized_flag}".strip()


def _configure_browser_qt_runtime() -> bool:
    """Force safer software-only Qt settings for browser/Xvfb container runs."""
    if not sys.platform.startswith("linux"):
        return False
    if not (_env_truthy("SOPOTEK_HTTP_UI") or _env_truthy("SOPOTEK_DISABLE_WEBENGINE")):
        return False

    defaults = {
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "QT_OPENGL": "software",
        "QT_QUICK_BACKEND": "software",
        "QSG_RHI_BACKEND": "software",
        "QT_XCB_GL_INTEGRATION": "none",
        "QTWEBENGINE_DISABLE_SANDBOX": "1",
    }   
    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    chromium_flags = str(os.getenv("QTWEBENGINE_CHROMIUM_FLAGS") or "").strip()
    for flag in (
            "--no-sandbox",
            "--disable-gpu",
            "--disable-gpu-compositing",
            "--disable-gpu-rasterization",
            "--disable-dev-shm-usage",
            "--disable-features=Vulkan,VulkanFromANGLE,UseSkiaRenderer",
    ):
        chromium_flags = _append_chromium_flag(chromium_flags, flag)
    if chromium_flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = chromium_flags
    return True


def _normalize_ai_device_name(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"gpu", "cuda:0"}:
        normalized = "cuda"
    if normalized in _VALID_AI_DEVICES:
        return normalized
    return None


def _probe_torch_ai_device() -> str | None:
    try:
        torch = importlib.import_module("torch")
    except Exception:
        return None

    try:
        if bool(getattr(torch.cuda, "is_available", lambda: False)()):
            return "cuda"
    except Exception:
        pass

    try:
        mps_backend = getattr(getattr(torch, "backends", None), "mps", None)
        if mps_backend is not None and bool(getattr(mps_backend, "is_available", lambda: False)()):
            return "mps"
    except Exception:
        pass

    return None


def _probe_onnxruntime_ai_device() -> str | None:
    try:
        ort = importlib.import_module("onnxruntime")
    except Exception:
        return None

    try:
        providers = [str(item) for item in ort.get_available_providers()]
    except Exception:
        return None

    if "CUDAExecutionProvider" in providers:
        return "cuda"
    if "DmlExecutionProvider" in providers:
        return "dml"
    return None


def _preferred_ai_device() -> str:
    override = _normalize_ai_device_name(os.getenv("SOPOTEK_AI_DEVICE"))
    if override is not None:
        return override

    for probe in (_probe_torch_ai_device, _probe_onnxruntime_ai_device):
        detected = probe()
        if detected is not None:
            return detected
    return "cpu"


def _configure_ai_runtime() -> str:
    device = _preferred_ai_device()
    os.environ.setdefault("SOPOTEK_AI_DEVICE", device)
    os.environ.setdefault("SOPOTEK_AI_ACCELERATION", "1" if device != "cpu" else "0")
    return device


def _install_faulthandler() -> None:
    """Install Python's faulthandler to capture native crashes and core dumps.

    Attempts to write crash traces to a log file. Falls back to stderr if file
    logging fails.
    """
    if faulthandler.is_enabled():
        return

    try:
        _setup_faulthandler_file_logging()
    except (OSError, RuntimeError, ValueError):
        try:
            faulthandler.enable(all_threads=True)
        except (OSError, RuntimeError, ValueError):
            return


def _setup_faulthandler_file_logging():
    log_dir = _src_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stream = (log_dir / "native_crash.log").open(
        mode="a",
        buffering=-1,
        encoding="utf-8",
        errors=None,
        newline=None
    )
    stream.write(f"\n=== Native crash trace session pid={os.getpid()} ===\n")
    faulthandler.enable(file=stream, all_threads=True)
    _FAULTHANDLER_STATE["stream"] = stream


def _is_dns_resolution_noise(context: dict[str, Any] | None) -> bool:
    """Check if an asyncio exception is transient DNS resolution noise.

    Parameters
    ----------
    context : dict[str, Any] | None
        The asyncio exception handler context.

    Returns
    -------
    bool
        True if the exception is DNS-related transient noise, False otherwise.
    """
    payload = context or {}
    message = str(payload.get("message") or "").lower()
    exception = payload.get("exception")
    future = payload.get("future")
    future_repr = str(future or "").lower()

    details: list[str] = []
    details.extend(
        str(item).lower()
        for item in (
            exception,
            getattr(exception, "__cause__", None),
            getattr(exception, "__context__", None),
        )
        if item is not None
    )
    if isinstance(exception, socket.gaierror):
        return True

    haystack = " ".join([message, future_repr, *details])
    return any(
        token in haystack
        for token in (
            "getaddrinfo failed",
            "could not contact dns servers",
            "dns lookup failed",
            "clientconnectordnserror",
        )
    )


def _install_asyncio_exception_filter(loop: Any, logger: Any = None) -> None:
    """Install a custom asyncio exception handler to filter DNS resolution noise.

    Suppresses transient DNS resolution errors while preserving meaningful
    exceptions for proper logging and debugging.

    Parameters
    ----------
    loop : Any
        The asyncio event loop.
    logger : Any, optional
        Logger instance for debug messages, by default None.
    """
    previous_handler = loop.get_exception_handler()

    def handler(active_loop: Any, context: dict[str, Any]) -> None:
        if _is_dns_resolution_noise(context):
            if logger is not None:
                logger.debug(
                    "Suppressed transient DNS resolver noise: %s",
                    context.get("message") or context.get("exception"),
                    )
            return

        if previous_handler is not None:
            previous_handler(active_loop, context)
        else:
            active_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)


def _is_qt_windows_noise(message: str | None) -> bool:
    """Check if a Qt message is harmless Windows platform integration noise.

    Parameters
    ----------
    message : str | None
        The Qt message text.

    Returns
    -------
    bool
        True if the message is known harmless noise, False otherwise.
    """
    text:str=""
    if text := str(message or "").strip():
        return any(
            token in text
            for token in (
                "External WM_DESTROY received for",
                "QWindowsWindow::setGeometry: Unable to set geometry",
                "OpenThemeData() failed for theme 15 (WINDOW).",
            )
        )
    else:
        return False


def _install_qt_message_filter() -> None:
    """Install a custom Qt message handler to filter Windows platform noise.

    Suppresses known harmless Qt warnings on Windows while preserving meaningful
    messages.
    """
    previous_handler = QtCore.qInstallMessageHandler(None)

    def handler(mode: Any, context: Any, message: str) -> None:
        if _is_qt_windows_noise(message):
            return
        if callable(previous_handler):
            previous_handler(mode, context, message)
        else:
            sys.stderr.write(f"{message}\n")

    QtCore.qInstallMessageHandler(handler)


def main(argv: list[str] | None = None) -> int:
    _install_faulthandler()
    _install_qt_message_filter()
    ai_device = _configure_ai_runtime()
    browser_runtime = _configure_browser_qt_runtime()
    platform_plugin = _configure_qt_platform()
    if platform_plugin == "offscreen":
        sys.stderr.write(
            "No usable Linux display detected; using Qt offscreen mode. "
            "Set DISPLAY or WAYLAND_DISPLAY and override QT_QPA_PLATFORM if you need an interactive GUI.\n"
        )
    elif browser_runtime:
        sys.stderr.write(
            "Browser container mode detected; forcing software Qt rendering and disabling embedded WebEngine panels.\n"
        )
    if ai_device != "cpu":
        sys.stderr.write(f"AI acceleration enabled; preferred runtime device is {ai_device}.\n")

    app = QtWidgets.QApplication(sys.argv if argv is None else list(argv))
    app.setStyle("Fusion")
    qeventloop_cls = _load_qeventloop()
    loop = qeventloop_cls(app)
    asyncio.set_event_loop(loop)

    def _stop_loop() -> None:
        if loop.is_running():
            loop.stop()

    app_controller_cls = _load_app_controller()
    window = app_controller_cls()
    _install_asyncio_exception_filter(loop, logger=getattr(window, "logger", None))
    window.setIconSize(QtCore.QSize(48, 48))
    # Load window icon with fallback support for Windows compatibility
    icon_path = _src_root() / "assets" / "logo.ico"
    if not icon_path.exists():
        icon_path = _src_root() / "assets" / "logo.png"
    if icon_path.exists():
        try:
            icon = QtGui.QIcon(str(icon_path))
            if not icon.isNull():
                window.setWindowIcon(icon)
        except Exception:
            pass  # Silently continue if icon loading fails

    window.setWindowIconText("TradeAdviser")
    window.setWindowTitle("TradeAdviser")
    quit_signal = getattr(app, "aboutToQuit", None)
    connect = getattr(quit_signal, "connect", None)
    if connect is not None:
        connect(_stop_loop)  # pylint: disable=not-callable
    window.show()

    with loop:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            shutdown_coro = getattr(window, "shutdown_for_exit", None)
            if callable(shutdown_coro):
                with contextlib.suppress(KeyboardInterrupt, RuntimeError):
                    loop.run_until_complete(shutdown_coro())
            shutdown_asyncgens = getattr(loop, "shutdown_asyncgens", None)
            if callable(shutdown_asyncgens):
                with contextlib.suppress(KeyboardInterrupt, RuntimeError):
                    loop.run_until_complete(shutdown_asyncgens())
            shutdown_default_executor = getattr(loop, "shutdown_default_executor", None)
            if callable(shutdown_default_executor):
                with contextlib.suppress(KeyboardInterrupt, RuntimeError):
                    loop.run_until_complete(shutdown_default_executor())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
