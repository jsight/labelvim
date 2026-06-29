"""Tests for the keyboard-first LabelPicker overlay."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from labelvim.widgets.label_picker import LabelPicker  # noqa: E402

LABELS = ["screen", "logo", "model y text", "musical note"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def parent(app):
    w = QWidget()
    w.resize(600, 400)
    w.show()
    return w


def _picker(parent):
    chosen = []
    cancelled = []
    p = LabelPicker(parent)
    p.pick(LABELS, lambda i: chosen.append(i), lambda: cancelled.append(True))
    return p, chosen, cancelled


def test_hidden_until_pick(parent):
    p = LabelPicker(parent)
    assert p.isHidden()


def test_pick_shows_and_lists(parent):
    p, _, _ = _picker(parent)
    assert not p.isHidden()
    assert p._list.count() == len(LABELS)
    assert p._list.currentRow() == 0


def test_number_key_chooses_that_index(parent):
    p, chosen, _ = _picker(parent)
    QTest.keyClick(p, Qt.Key.Key_3)
    assert chosen == [2]  # "model y text"
    assert p.isHidden()


def test_enter_chooses_current_row(parent):
    p, chosen, _ = _picker(parent)
    QTest.keyClick(p, Qt.Key.Key_Down)  # row 1
    QTest.keyClick(p, Qt.Key.Key_Return)
    assert chosen == [1]


def test_escape_cancels(parent):
    p, chosen, cancelled = _picker(parent)
    QTest.keyClick(p, Qt.Key.Key_Escape)
    assert cancelled == [True]
    assert chosen == []
    assert p.isHidden()


def test_out_of_range_number_is_ignored(parent):
    p, chosen, _ = _picker(parent)
    QTest.keyClick(p, Qt.Key.Key_9)  # only 4 labels
    assert chosen == []
    assert not p.isHidden()
