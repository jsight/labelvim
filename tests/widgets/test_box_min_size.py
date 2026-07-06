"""Scale-aware minimum box size (replaces the old fixed 20-original-pixel gate).

A drawn box must span at least MIN_BOX_DISPLAY_PX *displayed* pixels to count
as deliberate. Measuring in screen space means small boxes are drawable when
zoomed in and boxes work on tiny images, while accidental clicks are still
rejected — with a non-blocking notice rather than a silent no-op.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QImage, QMouseEvent, QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from labelvim.utils.config import ANNOTATION_MODE, ANNOTATION_TYPE  # noqa: E402
from labelvim.widgets.canvas_widget import CanvasWidget  # noqa: E402

W, H = 400, 400


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _canvas(app, scale=1.0):
    cw = CanvasWidget()
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(QColor(20, 20, 20))
    cw.original_pixmap = QPixmap.fromImage(img)
    cw.current_pixmap = cw.original_pixmap.copy()
    cw.scale_factor = scale
    cw.setFixedSize(W, H)
    cw.label_list = ["cat"]
    cw.update_annotation_type(ANNOTATION_TYPE.BBOX)
    return cw


@pytest.mark.parametrize(
    "scale,dist,expected",
    [
        (1.0, 4, False),  # 4 displayed px -> accidental
        (1.0, 6, True),  # 6 displayed px -> deliberate
        (10.0, 1, True),  # tiny image zoomed up: 10 displayed px
        (0.1, 40, False),  # zoomed out: 4 displayed px
        (0.1, 60, True),  # zoomed out: 6 displayed px
    ],
)
def test_box_meets_min_size_is_scale_aware(app, scale, dist, expected):
    cw = _canvas(app, scale)
    from PyQt5.QtCore import QPoint

    assert cw._box_meets_min_size(QPoint(0, 0), QPoint(dist, 0)) is expected


def _press(cw, x, y):
    cw.mousePressEvent(
        QMouseEvent(
            QEvent.MouseButtonPress, QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
    )


def _release(cw, x, y):
    cw.mouseReleaseEvent(
        QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
    )


def test_tiny_box_is_rejected_with_a_notice(app):
    cw = _canvas(app, scale=1.0)
    cw.set_annotation_mode(ANNOTATION_MODE.CREATE)
    seen = []
    cw.notify.connect(lambda message, level: seen.append((level, message)))
    _press(cw, 100, 100)
    _release(cw, 101, 100)  # 1 displayed px -> too small
    assert len(cw.undo_tree.shapes) == 0  # nothing created
    assert seen and seen[-1][0] == "warning"  # not a silent no-op


def test_deliberate_box_is_accepted(app):
    cw = _canvas(app, scale=1.0)
    cw.set_annotation_mode(ANNOTATION_MODE.CREATE)
    _press(cw, 100, 100)
    _release(cw, 160, 150)  # well above threshold
    # geometry accepted -> pending a label pick
    assert cw._pending_shape is not None
    cw._on_label_chosen(0)
    assert len(cw.undo_tree.shapes) == 1
