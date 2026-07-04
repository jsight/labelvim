"""Canvas behaviour across images of widely varying sizes.

The scaling / coordinate math is the historically fragile part of the app, so
this drives the real CanvasWidget.load_image over a spread of dimensions (tiny,
huge, extreme aspect ratios, odd, square) and asserts it stays sane: a positive
scale factor, a paint that doesn't crash, and a click that round-trips back to
roughly the original pixel it came from. Also covers unreadable/empty files.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtCore import QPoint  # noqa: E402
from PyQt5.QtGui import QColor, QImage  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from labelvim.widgets.canvas_widget import CanvasWidget  # noqa: E402

# (name, width, height) — a spread that stresses scaling and aspect ratio.
SIZES = [
    ("tiny_16x16", 16, 16),
    ("small_100x100", 100, 100),
    ("square_512", 512, 512),
    ("normal_640x480", 640, 480),
    ("hd_1920x1080", 1920, 1080),
    ("huge_4000x3000", 4000, 3000),
    ("wide_3000x200", 3000, 200),
    ("tall_200x3000", 200, 3000),
    ("odd_641x373", 641, 373),
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_image(path, w, h):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(40, 60, 80))
    # a couple of marked pixels so it's a real, decodable image
    img.setPixelColor(0, 0, QColor(255, 0, 0))
    img.setPixelColor(w - 1, h - 1, QColor(0, 255, 0))
    assert img.save(path)


def _canvas(app, w, h):
    cw = CanvasWidget()
    cw.resize(1200, 800)
    return cw


@pytest.mark.parametrize("name,w,h", SIZES)
def test_load_scale_paint_roundtrip(app, tmp_path, name, w, h):
    path = str(tmp_path / f"{name}.png")
    _make_image(path, w, h)
    cw = _canvas(app, w, h)
    cw.load_image(path)

    assert cw.original_pixmap is not None and not cw.original_pixmap.isNull()
    assert cw.original_pixmap.width() == w and cw.original_pixmap.height() == h
    assert cw.scale_factor > 0

    # paint must not raise for any size
    cw.grab()

    # a click at the centre must round-trip back to ~the centre pixel
    sf = cw.scale_factor
    ox = (cw.width() - cw.current_pixmap.width()) // 2
    oy = (cw.height() - cw.current_pixmap.height()) // 2
    cx, cy = w // 2, h // 2
    sx, sy = ox + int(cx * sf), oy + int(cy * sf)
    back = cw.map_to_original_image(QPoint(sx, sy))
    assert back is not None, f"{name}: centre click mapped off-image"
    tol = int(1 / sf) + 2  # zoomed-out truncation can lose ~1/scale px
    assert abs(back.x() - cx) <= tol
    assert abs(back.y() - cy) <= tol


def test_unreadable_image_resets_to_clean_state(app, tmp_path):
    # Load a good image first, then a corrupt one: the corrupt load must not
    # leave the previous image on screen, and must clear the pixmaps so the
    # window's `original_pixmap is None` guards fire.
    good = str(tmp_path / "good.png")
    _make_image(good, 100, 100)
    bad = tmp_path / "corrupt.jpg"
    bad.write_bytes(b"not an image")
    cw = _canvas(app, 100, 100)
    cw.load_image(good)
    assert cw.current_pixmap is not None

    cw.load_image(str(bad))  # must not raise
    assert cw.original_pixmap is None
    assert cw.current_pixmap is None
    cw.grab()  # paint must still be safe with no image


def test_empty_file_resets_to_clean_state(app, tmp_path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    cw = _canvas(app, 1, 1)
    cw.load_image(str(empty))  # must not raise
    assert cw.original_pixmap is None
    assert cw.current_pixmap is None
    cw.grab()


def test_unreadable_image_emits_notify(app, tmp_path):
    bad = tmp_path / "corrupt.jpg"
    bad.write_bytes(b"not an image")
    cw = _canvas(app, 1, 1)
    seen = []
    cw.notify.connect(lambda message, level: seen.append((level, message)))
    cw.load_image(str(bad))
    assert seen and seen[-1][0] == "error"
