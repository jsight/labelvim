"""Round-trip invariants for the original <-> screen coordinate mapping."""

import pytest

from labelvim.utils import coords


def test_image_offset_centres_pixmap():
    assert coords.image_offset(800, 600) == 100
    assert coords.image_offset(600, 600) == 0
    # widget smaller than pixmap -> negative offset (pixmap overflows)
    assert coords.image_offset(400, 600) == -100


def test_to_screen_applies_scale_and_offset():
    assert coords.to_screen(0, 0, 1.0, 100, 50) == (100, 50)
    assert coords.to_screen(10, 20, 2.0, 100, 50) == (120, 90)


def test_to_original_rejects_points_outside_pixmap():
    # offset 100,50; pixmap 200x150 -> screen box x[100,300) y[50,200)
    assert coords.to_original(90, 100, 1.0, 100, 50, 200, 150) is None  # left of image
    assert coords.to_original(310, 100, 1.0, 100, 50, 200, 150) is None  # right of image
    assert coords.to_original(150, 40, 1.0, 100, 50, 200, 150) is None  # above image
    assert coords.to_original(150, 100, 1.0, 100, 50, 200, 150) == (50, 50)  # inside


@pytest.mark.parametrize("scale", [0.25, 0.5, 1.0, 1.5, 2.0, 4.0])
@pytest.mark.parametrize("point", [(0, 0), (37, 12), (160, 120), (100, 75)])
def test_round_trip_original_screen_original(scale, point):
    """original -> screen -> original is stable within integer-truncation error."""
    pixmap_w, pixmap_h = int(200 * scale), int(150 * scale)
    offset_x = coords.image_offset(800, pixmap_w)
    offset_y = coords.image_offset(600, pixmap_h)
    x, y = point

    sx, sy = coords.to_screen(x, y, scale, offset_x, offset_y)
    back = coords.to_original(sx, sy, scale, offset_x, offset_y, pixmap_w, pixmap_h)

    assert back is not None
    # Truncation on both legs bounds the error: the screen-space int() loses up
    # to one screen pixel (== 1/scale original pixels when zoomed out), plus one
    # more from the original-space int(). At scale >= 1 this collapses to <= 1px.
    tol = int(1 / scale) + 1
    assert abs(back[0] - x) <= tol
    assert abs(back[1] - y) <= tol


def test_round_trip_is_exact_at_unit_scale():
    offset_x = coords.image_offset(800, 200)
    offset_y = coords.image_offset(600, 150)
    for x, y in [(0, 0), (13, 47), (199, 149)]:
        sx, sy = coords.to_screen(x, y, 1.0, offset_x, offset_y)
        assert coords.to_original(sx, sy, 1.0, offset_x, offset_y, 200, 150) == (x, y)
