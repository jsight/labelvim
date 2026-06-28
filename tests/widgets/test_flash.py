"""Tests for the non-blocking flash/toast overlay."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from labelvim.widgets.flash import FlashOverlay  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def parent(app):
    w = QWidget()
    w.resize(400, 300)
    return w


def test_hidden_until_flashed(parent):
    f = FlashOverlay(parent)
    # isHidden() reflects the explicit show/hide state (parent isn't shown in the
    # test, so isVisible() would be False regardless).
    assert f.isHidden()


def test_flash_shows_message(parent):
    f = FlashOverlay(parent)
    f.flash("hello world", level="warning")
    assert not f.isHidden()
    assert f.text() == "hello world"


def test_level_picks_style(parent):
    f = FlashOverlay(parent)
    f.flash("oops", level="error")
    assert "#7f1d1d" in f.styleSheet()
    f.flash("fyi", level="info")
    assert "#1e3a5f" in f.styleSheet()


def test_unknown_level_falls_back_to_info(parent):
    f = FlashOverlay(parent)
    f.flash("hmm", level="bogus")
    assert "#1e3a5f" in f.styleSheet()  # info background


def test_does_not_steal_focus(parent):
    f = FlashOverlay(parent)
    assert f.focusPolicy() == 0  # Qt.FocusPolicy.NoFocus
