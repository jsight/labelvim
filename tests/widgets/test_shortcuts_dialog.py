"""The keyboard cheat sheet must list every core verb and construct cleanly."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from labelvim.widgets.shortcuts_dialog import (  # noqa: E402
    SHORTCUTS,
    ShortcutsDialog,
    shortcuts_html,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_cheat_sheet_lists_every_core_key():
    html = shortcuts_html()
    # the vim verbs that live only in the eventFilter, plus undo/redo/create
    for key in ["I", "Esc", "C", "Enter", "n / N", "v", "h j k l", "u", "Ctrl+R", "1 – 9", "?"]:
        assert key in html, f"cheat sheet missing {key!r}"


def test_sections_present():
    titles = [title for title, _ in SHORTCUTS]
    assert "Modes" in titles
    assert "Edit (EDIT mode)" in titles
    assert "History" in titles


def test_dialog_constructs_and_is_non_modal(app):
    dlg = ShortcutsDialog()
    assert dlg.windowTitle() == "Keyboard Shortcuts"
    assert dlg.isModal() is False
