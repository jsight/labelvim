"""Canvas-level keyboard vertex editing: live working copy, single undo step."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from labelvim.models.model import Point, Rectangle  # noqa: E402
from labelvim.widgets.canvas_widget import CanvasWidget  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _canvas(app):
    cw = CanvasWidget()
    cw.undo_tree.clear()
    cw.undo_tree.add_shape(
        Rectangle(id=0, category_id=0, topleft=Point(10, 10), bottomright=Point(50, 50))
    )
    cw.selected_object = 0
    return cw


def _tl(cw):
    return (cw.undo_tree.shapes[0].topleft.x, cw.undo_tree.shapes[0].topleft.y)


def test_commit_applies_edit_as_single_undo_step(app):
    cw = _canvas(app)
    cw.enter_or_cycle_vertex()  # vertex 0 = top-left
    assert cw.is_editing_vertex()
    cw._nudge_editing_vertex(5, 3)
    assert _tl(cw) == (10, 10)  # document unchanged during live edit
    cw.commit_vertex_edit()
    assert _tl(cw) == (15, 13)
    assert not cw.is_editing_vertex()
    cw.undo()  # one step reverts the whole vertex edit
    assert _tl(cw) == (10, 10)


def test_cancel_discards_edit(app):
    cw = _canvas(app)
    cw.enter_or_cycle_vertex()
    cw._nudge_editing_vertex(9, 9)
    assert cw.cancel_vertex_edit() is True
    assert not cw.is_editing_vertex()
    assert _tl(cw) == (10, 10)


def test_cycle_vertex_wraps(app):
    cw = _canvas(app)
    for expected in (0, 1, 2, 3, 0):
        cw.enter_or_cycle_vertex()
        assert cw.selected_vertex == expected


def test_commit_normalizes_inverted_rectangle(app):
    cw = _canvas(app)
    cw.enter_or_cycle_vertex()  # top-left
    cw._nudge_editing_vertex(100, 100)  # drag TL past BR
    cw.commit_vertex_edit()
    r = cw.undo_tree.shapes[0]
    assert r.topleft.x <= r.bottomright.x
    assert r.topleft.y <= r.bottomright.y


def test_no_edit_returns_false(app):
    cw = _canvas(app)
    assert cw.cancel_vertex_edit() is False
    assert cw.commit_vertex_edit() is False


def test_mouse_vertex_drag_coalesces_to_one_undo_step(app):
    from PyQt5.QtCore import QPoint

    cw = _canvas(app)  # rect id=0, topleft (10,10)
    cw._begin_drag(0)
    for xy in (20, 25, 30):  # a drag = many move events
        cw.move_vertex(0, QPoint(xy, xy))
    assert _tl(cw) == (30, 30)  # applied live during the drag
    cw._commit_drag()
    assert _tl(cw) == (30, 30)
    cw.undo()  # a single undo reverts the whole drag
    assert _tl(cw) == (10, 10)
    assert len(cw.undo_tree.shapes) == 1  # shape still there (only the drag was undone)


def test_mouse_move_drag_coalesces_to_one_undo_step(app):
    from PyQt5.QtCore import QPoint

    cw = _canvas(app)
    cw.last_mouse_position = QPoint(0, 0)
    cw._begin_drag(0)
    cw.move_rectangle(QPoint(5, 5))
    cw.last_mouse_position = QPoint(5, 5)
    cw.move_rectangle(QPoint(8, 8))
    cw.last_mouse_position = QPoint(8, 8)
    assert _tl(cw) == (18, 18)  # moved +8 total, live
    cw._commit_drag()
    cw.undo()
    assert _tl(cw) == (10, 10)


def test_click_without_movement_records_no_command(app):
    cw = _canvas(app)  # the only command so far is the add in _canvas()
    cw._begin_drag(0)
    cw._commit_drag()  # no movement -> no undo entry
    cw.undo()  # so this undoes the add, not a phantom drag
    assert len(cw.undo_tree.shapes) == 0


def test_status_text_reflects_selection_and_vertex(app):
    cw = _canvas(app)  # rect id=0 category_id=0, selected_object=0
    cw.label_list = ["screen"]
    assert "shape: screen" in cw.status_text()
    cw.enter_or_cycle_vertex()
    text = cw.status_text()
    assert "vertex 1/4" in text
    assert "nudge" in text
