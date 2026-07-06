"""A non-blocking, keyboard-first label picker overlay.

Replaces the modal LabelPopup for the common "what category is this shape?"
choice. Number keys 1-9 select directly; Up/Down + Enter also work; Esc cancels;
clicking an item selects it (discoverable for mouse users). It never blocks, so
the keyboard create flow keeps going.
"""

from collections.abc import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QListWidget, QVBoxLayout, QWidget


class LabelPicker(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setVisible(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            "LabelPicker { background-color: #1f2937; border: 1px solid #4b5563;"
            " border-radius: 8px; }"
            " QLabel { color: #d1d5db; padding: 6px; }"
            " QListWidget { background-color: #111827; color: #e5e7eb; border: none;"
            " font-size: 14px; }"
            " QListWidget::item { padding: 4px 8px; }"
            " QListWidget::item:selected { background-color: #2563eb; color: white; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._title = QLabel("Pick a label —  1-9 / ↑↓+Enter,  Esc cancels", self)
        layout.addWidget(self._title)
        self._list = QListWidget(self)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep keys on the frame
        self._list.itemClicked.connect(lambda _item: self._choose(self._list.currentRow()))
        layout.addWidget(self._list)

        self._on_choose: Callable[[int], None] | None = None
        self._on_cancel: Callable[[], None] | None = None

    def pick(
        self,
        labels: list[str],
        on_choose: Callable[[int], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self._on_choose = on_choose
        self._on_cancel = on_cancel
        self._list.clear()
        for i, label in enumerate(labels):
            prefix = f"{i + 1}.  " if i < 9 else "    "
            self._list.addItem(prefix + label)
        if labels:
            self._list.setCurrentRow(0)
        self._reposition()
        self.show()
        self.raise_()
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._choose(self._list.currentRow())
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            index = key - Qt.Key.Key_1
            if index < self._list.count():
                self._choose(index)
        elif key == Qt.Key.Key_Up:
            self._list.setCurrentRow(max(0, self._list.currentRow() - 1))
        elif key == Qt.Key.Key_Down:
            self._list.setCurrentRow(min(self._list.count() - 1, self._list.currentRow() + 1))
        else:
            super().keyPressEvent(event)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        width = min(max(self.sizeHint().width(), 240), parent.width() - 40)
        height = min(self.sizeHint().height(), parent.height() - 40)
        self.resize(width, height)
        self.move((parent.width() - width) // 2, (parent.height() - height) // 2)

    def _choose(self, index: int) -> None:
        if index < 0:
            return
        callback = self._on_choose
        self.hide()
        if callback is not None:
            callback(index)

    def _cancel(self) -> None:
        callback = self._on_cancel
        self.hide()
        if callback is not None:
            callback()
