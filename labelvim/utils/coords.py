"""Pure coordinate mapping between original-image space and screen space.

The canvas centres a scaled pixmap inside the widget, so a point moves between
the two spaces by a single scale factor plus a centring offset:

    screen   = offset + original * scale
    original = (screen - offset) / scale
    offset   = (widget_size - pixmap_size) // 2

Historically this arithmetic lived inline in the widget and quietly corrupted
saved coordinates when it drifted. Keeping it here as Qt-free integer math makes
it unit-testable and gives both the painter and the mouse handlers one source of
truth for the mapping.
"""


def image_offset(widget_size: int, pixmap_size: int) -> int:
    """Centring offset of the pixmap within the widget along one axis."""
    return (widget_size - pixmap_size) // 2


def to_screen(x: float, y: float, scale: float, offset_x: int, offset_y: int) -> tuple[int, int]:
    """Map an original-image point to screen pixels."""
    return (offset_x + int(x * scale), offset_y + int(y * scale))


def to_original(
    sx: int,
    sy: int,
    scale: float,
    offset_x: int,
    offset_y: int,
    pixmap_w: int,
    pixmap_h: int,
) -> tuple[int, int] | None:
    """Map a screen point to original-image pixels.

    Returns ``None`` when the point falls outside the displayed pixmap, matching
    the widget's "ignore clicks off the image" behaviour.
    """
    relative_x = sx - offset_x
    relative_y = sy - offset_y
    if 0 <= relative_x < pixmap_w and 0 <= relative_y < pixmap_h:
        return (int(relative_x / scale), int(relative_y / scale))
    return None
