from datetime import datetime
from pathlib import Path
import re

from PySide6.QtWidgets import QFileDialog


DEFAULT_SCREENSHOT_DIR = Path("output") / "screenshots"


def sanitize_screenshot_fragment(value, fallback="capture"):
    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "")).strip("_")
    return sanitized or fallback


def ensure_png_path(path):
    target = Path(path)
    if target.suffix:
        return target
    return target.with_suffix(".png")


def build_screenshot_output_path(prefix="capture", suffix=None, output_dir=None):
    base_dir = Path(output_dir) if output_dir is not None else DEFAULT_SCREENSHOT_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    fragments = [sanitize_screenshot_fragment(prefix, "capture")]
    if suffix:
        fragments.append(sanitize_screenshot_fragment(suffix, "item"))

    filename = "_".join(fragments)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"{filename}_{timestamp}.png"


def capture_widget_to_path(widget, path):
    if widget is None:
        return None

    pixmap = widget.grab()
    if pixmap is None or pixmap.isNull():
        return None

    target = ensure_png_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(target), "PNG"):
        return None
    return str(target)


def capture_widget_to_output(widget, prefix="capture", suffix=None, output_dir=None):
    path = build_screenshot_output_path(prefix=prefix, suffix=suffix, output_dir=output_dir)
    return capture_widget_to_path(widget, path)


def prompt_and_save_widget_screenshot(
    parent,
    widget,
    filename_prefix="Sopotek_Screenshot",
    dialog_getter=None,
):
    dialog = dialog_getter or QFileDialog.getSaveFileName
    suggested_name = f"{sanitize_screenshot_fragment(filename_prefix, 'Screenshot')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    selected_path, _selected_filter = dialog(
        parent,
        "Save Screenshot",
        suggested_name,
        "PNG Files (*.png)",
    )
    if not selected_path:
        return None
    return capture_widget_to_path(widget, selected_path)
