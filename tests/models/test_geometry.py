"""Geometry tests for the shape model (point-in-polygon, move, bbox, hit-test).

Pure Python, no Qt.
"""

from labelvim.models.model import BBox, Point, Polygon, Rectangle


def rect(x1=0.0, y1=0.0, x2=10.0, y2=10.0, id=1, category_id=0):
    return Rectangle(
        id=id, category_id=category_id, topleft=Point(x1, y1), bottomright=Point(x2, y2)
    )


def square_polygon(id=1, category_id=0):
    # Unit square 0..10
    return Polygon(
        id=id,
        category_id=category_id,
        points=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)],
    )


# --- Point ---


def test_point_translate_is_in_place():
    p = Point(1.0, 2.0)
    p.translate(3.0, -1.0)
    assert (p.x, p.y) == (4.0, 1.0)


def test_point_distance():
    assert Point(0, 0).distance_to(Point(3, 4)) == 5.0


# --- Rectangle ---


def test_rectangle_vertices_order():
    r = rect(0, 0, 4, 2)
    verts = [(p.x, p.y) for p in r.vertices()]
    assert verts == [(0, 0), (4, 0), (4, 2), (0, 2)]


def test_rectangle_bbox():
    b = rect(2, 3, 12, 8).bbox
    assert (b.x, b.y, b.width, b.height) == (2, 3, 10, 5)


def test_rectangle_contains():
    r = rect(0, 0, 10, 10)
    assert r.contains(Point(5, 5))
    assert r.contains(Point(0, 0))  # on the corner counts as inside
    assert r.contains(Point(10, 10))
    assert not r.contains(Point(11, 5))
    assert not r.contains(Point(5, -1))


def test_rectangle_move():
    r = rect(0, 0, 10, 10)
    r.move(5, -2)
    assert (r.topleft.x, r.topleft.y) == (5, -2)
    assert (r.bottomright.x, r.bottomright.y) == (15, 8)
    assert r.bbox == BBox(5, -2, 10, 10)


def test_rectangle_to_legacy_json_matches_bbox():
    r = rect(2, 3, 12, 8)
    assert r.to_legacy_json() == {"bbox": [2, 3, 10, 5]}


def test_vertex_index_near_picks_closest():
    r = rect(0, 0, 10, 10)
    # closest to top-right vertex (index 1)
    assert r.vertex_index_near(Point(9.6, 0.4), radius=1.0) == 1
    # nothing within radius
    assert r.vertex_index_near(Point(5, 5), radius=1.0) is None


# --- Polygon ---


def test_polygon_contains_convex():
    poly = square_polygon()
    assert poly.contains(Point(5, 5))
    assert not poly.contains(Point(15, 5))
    assert not poly.contains(Point(-1, -1))


def test_polygon_contains_concave():
    # U-shape (concave): bottom bar y 0..4 full width, two legs up to y=10 with a
    # notch at x 4..6. Test points avoid vertex y-levels (0, 4, 10).
    poly = Polygon(
        id=1,
        category_id=0,
        points=[
            Point(0, 0),
            Point(0, 10),
            Point(4, 10),
            Point(4, 4),
            Point(6, 4),
            Point(6, 10),
            Point(10, 10),
            Point(10, 0),
        ],
    )
    assert poly.contains(Point(2, 7))  # inside the left leg
    assert poly.contains(Point(8, 7))  # inside the right leg
    assert poly.contains(Point(5, 2))  # inside the bottom bar
    assert not poly.contains(Point(5, 7))  # in the notch -> outside
    assert not poly.contains(Point(20, 7))  # far outside


def test_polygon_degenerate_is_empty():
    assert not Polygon(id=1, category_id=0, points=[Point(0, 0), Point(1, 1)]).contains(Point(0, 0))


def test_polygon_bbox():
    poly = Polygon(id=1, category_id=0, points=[Point(2, 3), Point(8, 1), Point(5, 9)])
    assert poly.bbox == BBox(2, 1, 6, 8)


def test_polygon_move():
    poly = square_polygon()
    poly.move(1, 2)
    assert [(p.x, p.y) for p in poly.points] == [(1, 2), (11, 2), (11, 12), (1, 12)]


def test_polygon_vertices_are_points():
    poly = square_polygon()
    assert poly.vertices() is poly.points


def test_polygon_vertex_index_near():
    poly = square_polygon()
    assert poly.vertex_index_near(Point(10.2, 9.8), radius=0.5) == 2
    assert poly.vertex_index_near(Point(5, 5), radius=0.5) is None


def test_polygon_nudge_vertex():
    poly = square_polygon()  # [(0,0),(10,0),(10,10),(0,10)]
    poly.nudge_vertex(2, 3, -4)
    assert (poly.points[2].x, poly.points[2].y) == (13, 6)
    # others unchanged
    assert (poly.points[0].x, poly.points[0].y) == (0, 0)


def test_rectangle_nudge_each_corner():
    # corners: 0=TL, 1=TR, 2=BR, 3=BL
    r = rect(0, 0, 10, 10)
    r.nudge_vertex(0, 2, 3)  # top-left
    assert (r.topleft.x, r.topleft.y) == (2, 3)
    r = rect(0, 0, 10, 10)
    r.nudge_vertex(1, 2, 3)  # top-right: right edge x, top edge y
    assert (r.bottomright.x, r.topleft.y) == (12, 3)
    r = rect(0, 0, 10, 10)
    r.nudge_vertex(2, 2, 3)  # bottom-right
    assert (r.bottomright.x, r.bottomright.y) == (12, 13)
    r = rect(0, 0, 10, 10)
    r.nudge_vertex(3, 2, 3)  # bottom-left: left edge x, bottom edge y
    assert (r.topleft.x, r.bottomright.y) == (2, 13)


def test_rectangle_normalized_after_inverting_drag():
    r = rect(0, 0, 10, 10)
    r.nudge_vertex(0, 20, 20)  # drag TL past BR -> inverted
    n = r.normalized()
    assert (n.topleft.x, n.topleft.y) == (10, 10)
    assert (n.bottomright.x, n.bottomright.y) == (20, 20)
