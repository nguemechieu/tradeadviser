from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


_SPINNER_PATH = Path(__file__).resolve().parents[2] / "assets" / "spinner.gif"


class LoadingOverlay(QFrame):
    """Full-surface loading scrim with animated feedback."""

    _FALLBACK_FRAMES = ("|", "/", "-", "\\")

    def __init__(self, parent: QWidget | None, *, title: str = "Loading workspace...") -> None:
        super().__init__(parent)
        self._fallback_index = 0
        self._movie = QMovie(str(_SPINNER_PATH)) if _SPINNER_PATH.exists() else None
        self._fallback_timer = QTimer(self)
        self._fallback_timer.setInterval(120)
        self._fallback_timer.timeout.connect(self._advance_fallback_frame)

        self.setObjectName("loadingOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(32, 32, 32, 32)
        root_layout.addStretch(1)

        self.card = QFrame(self)
        self.card.setObjectName("loadingOverlayCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(14)

        self.spinner_label = QLabel(self.card)
        self.spinner_label.setObjectName("loadingOverlaySpinner")
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label.setMinimumSize(88, 88)
        if self._movie is not None:
            self._movie.setScaledSize(QSize(88, 88))
            self.spinner_label.setMovie(self._movie)
        else:
            self.spinner_label.setText(self._FALLBACK_FRAMES[0])

        self.title_label = QLabel(title, self.card)
        self.title_label.setObjectName("loadingOverlayTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)

        self.detail_label = QLabel("", self.card)
        self.detail_label.setObjectName("loadingOverlayDetail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.hide()

        card_layout.addWidget(self.spinner_label, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.detail_label)

        root_layout.addWidget(self.card, 0, Qt.AlignmentFlag.AlignCenter)
        root_layout.addStretch(1)

        self.setStyleSheet(
            """
            QFrame#loadingOverlay {
                background-color: rgba(7, 12, 20, 215);
                border: none;
            }
            QFrame#loadingOverlayCard {
                background-color: #0d1726;
                border: 1px solid #244060;
                border-radius: 24px;
                min-width: 360px;
                max-width: 560px;
            }
            QFrame#loadingOverlay QLabel {
                color: #dce9f8;
            }
            QLabel#loadingOverlaySpinner {
                color: #8ad6ff;
                font-size: 34px;
                font-weight: 800;
            }
            QLabel#loadingOverlayTitle {
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#loadingOverlayDetail {
                color: #9cb7d8;
                font-size: 13px;
            }
            """
        )

        parent_widget = self.parentWidget()
        if parent_widget is not None:
            parent_widget.installEventFilter(self)
            self._sync_geometry()

    def eventFilter(self, watched: object, event: object) -> bool:
        parent_widget = self.parentWidget()
        if watched is parent_widget and isinstance(event, QEvent):
            if event.type() in {
                QEvent.Type.Resize,
                QEvent.Type.Move,
                QEvent.Type.Show,
                QEvent.Type.WindowStateChange,
            }:
                self._sync_geometry()
        return super().eventFilter(watched, event)

    def _consume_interaction(self, event) -> None:
        try:
            event.accept()
        except Exception:
            pass

    def mousePressEvent(self, event) -> None:
        self._consume_interaction(event)

    def mouseReleaseEvent(self, event) -> None:
        self._consume_interaction(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self._consume_interaction(event)

    def wheelEvent(self, event) -> None:
        self._consume_interaction(event)

    def keyPressEvent(self, event) -> None:
        self._consume_interaction(event)

    def keyReleaseEvent(self, event) -> None:
        self._consume_interaction(event)

    def _advance_fallback_frame(self) -> None:
        if self._movie is not None:
            return
        frame = self._FALLBACK_FRAMES[self._fallback_index % len(self._FALLBACK_FRAMES)]
        self.spinner_label.setText(frame)
        self._fallback_index += 1

    def _sync_geometry(self) -> None:
        parent_widget = self.parentWidget()
        if parent_widget is None:
            return
        self.setGeometry(parent_widget.rect())

    def set_loading(self, title: str, detail: str | None = None) -> None:
        self.title_label.setText(str(title or "Loading workspace..."))
        detail_text = str(detail or "").strip()
        self.detail_label.setText(detail_text)
        self.detail_label.setVisible(bool(detail_text))
        self._sync_geometry()
        self.show()
        self.raise_()
        if self._movie is not None:
            self._movie.start()
        else:
            self._fallback_index = 0
            self.spinner_label.setText(self._FALLBACK_FRAMES[0])
            if not self._fallback_timer.isActive():
                # Safely start timer - use singleShot if not on main thread
                try:
                    import threading
                    from PySide6.QtCore import QTimer as QT
                    if threading.current_thread() is threading.main_thread():
                        self._fallback_timer.start()
                    else:
                        # From background thread, use singleShot which is thread-safe
                        QT.singleShot(50, lambda: self._fallback_timer.start() if not self._fallback_timer.isActive() else None)
                except Exception:
                    pass

    def clear_loading(self) -> None:
        self.hide()
        if self._movie is not None:
            self._movie.stop()
        if self._fallback_timer.isActive():
            self._fallback_timer.stop()
