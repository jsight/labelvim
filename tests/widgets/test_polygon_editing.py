"""Mouse-driven polygon creation and editing against the model.

Regression coverage for two bugs:
  * mouse polygon creation used to store a 0-vertex polygon (the pending
    geometry was a reference to a list that got cleared before the label
    callback read it);
  * mouse polygon editing was a no-op (stubbed selection + a removed legacy
    dict store), so vertex-drag / whole-move / add-point did nothing.

The canvas is given a synthetic pixmap at scale 1.0 with a zero centring
offset, so screen coordinates equal original-image coordinates and the mouse
math is easy to reason about.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QImage, QMouseEvent, QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from labelvim.models.model import Point, Polygon  # noqa: E402
from labelvim.utils.config import ANNOTATION_MODE, ANNOTATION_TYPE  # noqa: E402
from labelvim.widgets.canvas_widget import CanvasWidget  # noqa: E402

W, H = 640, 480


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _canvas(app):
    cw = CanvasWidget()
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(QColor(30, 30, 30))
    cw.original_pixmap = QPixmap.fromImage(img)
    cw.current_pixmap = cw.original_pixmap.copy()
    cw.scale_factor = 1.0
    cw.setFixedSize(W, H)  # widget == pixmap -> zero offset -> screen == original
    cw.label_list = ["cat", "dog", "bird"]
    cw.update_annotation_type(ANNOTATION_TYPE.POLYGON)
    return cw


def _press(cw, x, y):
    cw.mousePressEvent(
        QMouseEvent(
            QEvent.MouseButtonPress, QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
    )


def _move(cw, x, y):
    cw.mouseMoveEvent(
        QMouseEvent(QEvent.MouseMove, QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    )


def _release(cw, x, y):
    cw.mouseReleaseEvent(
        QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
    )


def _points(cw, i=0):
    return [(p.x, p.y) for p in cw.undo_tree.shapes[i].points]


def _put_square(cw):
    cw.undo_tree.clear()
    cw.undo_tree.add_shape(
        Polygon(
            id=0,
            category_id=1,
            points=[Point(100, 100), Point(300, 100), Point(300, 300), Point(100, 300)],
        )
    )


# --- creation (bug: 0-vertex polygon) ---------------------------------------


def test_mouse_polygon_creation_keeps_all_vertices(app):
    cw = _canvas(app)
    cw.set_annotation_mode(ANNOTATION_MODE.CREATE)
    for x, y in [(100, 100), (300, 100), (300, 250), (150, 300)]:
        _press(cw, x, y)
    _press(cw, 103, 102)  # close near the first point
    # geometry is stashed pending a label; picking it must create a full polygon
    cw._on_label_chosen(2)
    assert len(cw.undo_tree.shapes) == 1
    poly = cw.undo_tree.shapes[0]
    assert isinstance(poly, Polygon)
    assert poly.category_id == 2
    assert len(poly.vertices()) == 4  # NOT zero
    assert (100, 100) in _points(cw)


# --- editing (bug: mouse editing was a no-op) -------------------------------


def test_mouse_vertex_drag_moves_one_vertex_single_undo(app):
    cw = _canvas(app)
    _put_square(cw)
    cw.set_annotation_mode(ANNOTATION_MODE.EDIT)
    _press(cw, 100, 100)  # grab the top-left vertex
    assert cw.selected_object == 0 and cw.selected_vertex == 0
    _move(cw, 130, 140)
    _release(cw, 130, 140)
    assert _points(cw)[0] == (130, 140)
    assert _points(cw)[1:] == [(300, 100), (300, 300), (100, 300)]  # others unchanged
    cw.undo()
    assert _points(cw) == [(100, 100), (300, 100), (300, 300), (100, 300)]


def test_mouse_whole_polygon_move_single_undo(app):
    cw = _canvas(app)
    _put_square(cw)
    cw.set_annotation_mode(ANNOTATION_MODE.EDIT)
    _press(cw, 200, 200)  # interior -> whole move
    assert cw.moving_object and cw.selected_object == 0
    _move(cw, 220, 215)
    _move(cw, 240, 230)  # net +40, +30
    _release(cw, 240, 230)
    assert _points(cw) == [(140, 130), (340, 130), (340, 330), (140, 330)]
    cw.undo()
    assert _points(cw) == [(100, 100), (300, 100), (300, 300), (100, 300)]


def test_mouse_add_point_on_edge_single_undo(app):
    cw = _canvas(app)
    _put_square(cw)
    cw.set_annotation_mode(ANNOTATION_MODE.EDIT)
    _press(cw, 200, 100)  # on the top edge, between vertices 0 and 1
    assert cw.line_segment == (0, 1)
    _move(cw, 200, 60)  # drag the freshly inserted vertex up
    _release(cw, 200, 60)
    pts = _points(cw)
    assert len(pts) == 5
    assert (200, 60) in pts
    cw.undo()
    assert len(cw.undo_tree.shapes[0].points) == 4


def test_mouse_click_empty_area_selects_nothing(app):
    cw = _canvas(app)
    _put_square(cw)
    cw.set_annotation_mode(ANNOTATION_MODE.EDIT)
    _press(cw, 500, 400)  # outside the polygon
    _release(cw, 500, 400)
    assert cw.selected_object is None
    assert _points(cw) == [(100, 100), (300, 100), (300, 300), (100, 300)]  # unchanged
