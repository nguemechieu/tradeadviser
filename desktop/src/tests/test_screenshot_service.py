import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.services.screenshot_service import (
    build_screenshot_output_path,
    capture_widget_to_output,
    ensure_png_path,
    prompt_and_save_widget_screenshot,
)


class DummyPixmap:
    def __init__(self, payload=b"png", is_null=False):
        self.payload = payload
        self._is_null = is_null
        self.saved_paths = []

    def isNull(self):
        return self._is_null

    def save(self, path, _format):
        self.saved_paths.append(path)
        Path(path).write_bytes(self.payload)
        return True


class DummyWidget:
    def __init__(self, pixmap):
        self._pixmap = pixmap

    def grab(self):
        return self._pixmap


def test_build_screenshot_output_path_sanitizes_fragments(tmp_path):
    path = build_screenshot_output_path(
        prefix="market chat",
        suffix="BTC/USDT",
        output_dir=tmp_path,
    )

    assert path.parent == tmp_path
    assert path.suffix == ".png"
    assert path.name.startswith("market_chat_BTC_USDT_")


def test_capture_widget_to_output_writes_png_file(tmp_path):
    widget = DummyWidget(DummyPixmap())

    path = capture_widget_to_output(
        widget,
        prefix="chart shot",
        suffix="ETH/USD",
        output_dir=tmp_path,
    )

    assert path is not None
    assert Path(path).exists()
    assert Path(path).suffix == ".png"


def test_prompt_and_save_widget_screenshot_adds_png_suffix(tmp_path):
    widget = DummyWidget(DummyPixmap())

    path = prompt_and_save_widget_screenshot(
        parent=None,
        widget=widget,
        filename_prefix="Sopotek Screenshot",
        dialog_getter=lambda *_args, **_kwargs: (str(tmp_path / "manual_capture"), "PNG Files (*.png)"),
    )

    assert path == str(ensure_png_path(tmp_path / "manual_capture"))
    assert Path(path).exists()
