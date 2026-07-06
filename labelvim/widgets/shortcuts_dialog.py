"""A keyboard cheat-sheet dialog — the in-app reference for the vim-style keys.

The whole app is keyboard-first, so the shortcuts must be discoverable without
reading the source. SHORTCUTS is the single source of truth for both this dialog
and the docs; keep it in sync with main.py's eventFilter and layout.py's menu
accelerators.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QTextBrowser, QVBoxLayout, QWidget

# (section title, [(keys, description), ...])
SHORTCUTS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Modes",
        [
            ("I", "Enter EDIT mode (from NORMAL)"),
            ("Esc", "Cancel an in-progress vertex edit, or leave EDIT mode"),
        ],
    ),
    (
        "Create",
        [
            ("C", "Start a new box at the cursor"),
            ("Enter", "Complete the box (then pick a label) / commit a vertex edit"),
            ("1 – 9", "Pick a category in the label picker"),
            ("↑ / ↓, Enter", "Move / choose in the label picker; Esc cancels"),
        ],
    ),
    (
        "Edit (EDIT mode)",
        [
            ("n / N", "Select next / previous shape"),
            ("v", "Grab a vertex, or cycle to the next vertex"),
            ("h j k l  or  ← ↓ ↑ →", "Move the cursor / nudge the vertex (Shift = coarse)"),
        ],
    ),
    (
        "History",
        [
            ("u", "Undo"),
            ("Ctrl+R", "Redo"),
        ],
    ),
    (
        "Files & view",
        [
            ("Ctrl+O", "Open image directory"),
            ("Ctrl+U", "Choose save directory"),
            ("Ctrl+S", "Save the current annotation"),
            ("Ctrl+A / Ctrl+D", "Next / previous image"),
            ("Ctrl+Del", "Delete the current file"),
            ("Ctrl+= / Ctrl+- / Ctrl+0", "Zoom in / out / fit to window"),
            ("Ctrl+Q", "Quit"),
        ],
    ),
    (
        "Help",
        [
            ("?", "Show this shortcuts reference"),
        ],
    ),
]


def shortcuts_html() -> str:
    """Render SHORTCUTS as a simple HTML cheat sheet."""
    rows = []
    for title, entries in SHORTCUTS:
        rows.append(f"<h3 style='margin-bottom:2px'>{title}</h3>")
        rows.append("<table cellspacing='0' cellpadding='4'>")
        for keys, description in entries:
            rows.append(
                "<tr>"
                f"<td style='white-space:nowrap'><b><code>{keys}</code></b></td>"
                f"<td>{description}</td>"
                "</tr>"
            )
        rows.append("</table>")
    return "\n".join(rows)


class ShortcutsDialog(QDialog):
    """Non-modal reference listing every keyboard shortcut."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(False)
        self.resize(460, 560)

        layout = QVBoxLayout(self)
        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(False)
        browser.setHtml(shortcuts_html())
        layout.addWidget(browser)

    def keyPressEvent(self, event) -> None:
        # Esc or ? closes the reference.
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Question):
            self.close()
        else:
            super().keyPressEvent(event)
