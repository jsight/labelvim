"""A small non-blocking flash/toast overlay.

Shows a transient message over a parent widget and fades out on its own, so
info/error feedback never interrupts the keyboard-driven workflow the way a
modal dialog does. Use for non-critical info/warnings; keep real confirmations
(destructive actions) as dialogs.
"""

from PyQt5.QtCore import QPropertyAnimation, Qt, QTimer
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

# (background, foreground) per level.
_LEVEL_STYLES = {
    "info": ("#1e3a5f", "#dbeafe"),
    "success": ("#14532d", "#dcfce7"),
    "warning": ("#7c2d12", "#ffedd5"),
    "error": ("#7f1d1d", "#fee2e2"),
}


class FlashOverlay(QLabel):
    """A translucent auto-fading label positioned near the top of its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)
        # Never steal mouse/keyboard focus — the workflow keeps going.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(1.0)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._begin_fade)

        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(400)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._on_faded)

    def flash(self, message: str, level: str = "info", duration_ms: int = 2500) -> None:
        bg, fg = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 8px;"
            f" padding: 8px 16px; font-size: 13px;"
        )
        self.setText(message)
        self._fade.stop()
        self._effect.setOpacity(1.0)
        self._reposition()
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        width = min(self.width(), parent.width() - 40)
        self.setFixedWidth(max(width, 120))
        x = (parent.width() - self.width()) // 2
        self.move(max(x, 0), 12)

    def _begin_fade(self) -> None:
        self._fade.stop()
        self._fade.start()

    def _on_faded(self) -> None:
        self.hide()
        self._effect.setOpacity(1.0)
