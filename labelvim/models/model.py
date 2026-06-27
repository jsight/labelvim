from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Labels:
    labels: list[str]

    def add_label(self, label: str) -> None:
        if label in self.labels:
            return
        self.labels.append(label)

    def get_index_for_label(self, label: str) -> int:
        return self.labels.index(label)


@dataclass
class Point:
    x: float
    y: float
    selected: bool = False

    def translate(self, dx: float, dy: float) -> None:
        """Move this point in place by (dx, dy)."""
        self.x += dx
        self.y += dy

    def distance_to(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass
class BBox:
    """Axis-aligned bounding box in COCO convention: top-left corner + size."""

    x: float
    y: float
    width: float
    height: float


@dataclass
class Shape(ABC):
    id: int | None
    category_id: int | None

    @abstractmethod
    def vertices(self) -> list[Point]:
        """The editable vertices of this shape, in order."""

    @abstractmethod
    def move(self, dx: float, dy: float) -> None:
        """Translate the whole shape in place by (dx, dy)."""

    @abstractmethod
    def contains(self, point: Point) -> bool:
        """Whether the point lies inside the shape."""

    @property
    @abstractmethod
    def bbox(self) -> BBox:
        """Axis-aligned bounding box of the shape."""

    def vertex_index_near(self, point: Point, radius: float) -> int | None:
        """Index of the closest vertex within ``radius``, or None.

        Ties resolve to the nearest vertex.
        """
        best_index: int | None = None
        best_distance = radius
        for index, vertex in enumerate(self.vertices()):
            distance = vertex.distance_to(point)
            if distance <= best_distance:
                best_distance = distance
                best_index = index
        return best_index


@dataclass
class Rectangle(Shape):
    topleft: Point
    bottomright: Point

    def __post_init__(self) -> None:
        assert self.topleft.x <= self.bottomright.x, "topleft.x must be <= bottomright.x"
        assert self.topleft.y <= self.bottomright.y, "topleft.y must be <= bottomright.y"

    def vertices(self) -> list[Point]:
        return [
            self.topleft,
            Point(self.bottomright.x, self.topleft.y),
            self.bottomright,
            Point(self.topleft.x, self.bottomright.y),
        ]

    def move(self, dx: float, dy: float) -> None:
        self.topleft.translate(dx, dy)
        self.bottomright.translate(dx, dy)

    def contains(self, point: Point) -> bool:
        return (
            self.topleft.x <= point.x <= self.bottomright.x
            and self.topleft.y <= point.y <= self.bottomright.y
        )

    @property
    def bbox(self) -> BBox:
        return BBox(
            self.topleft.x,
            self.topleft.y,
            self.bottomright.x - self.topleft.x,
            self.bottomright.y - self.topleft.y,
        )

    def to_legacy_json(self) -> dict[str, list[float]]:
        b = self.bbox
        return {"bbox": [b.x, b.y, b.width, b.height]}


@dataclass
class Polygon(Shape):
    points: list[Point]
    # Deprecated: the bounding box is computed from ``points`` (see .bbox). Kept
    # optional only for backward compatibility until the canvas rewrite (Phase 2)
    # stops constructing it.
    rectangle: "Rectangle | None" = field(default=None)

    def vertices(self) -> list[Point]:
        return self.points

    def move(self, dx: float, dy: float) -> None:
        for p in self.points:
            p.translate(dx, dy)

    def contains(self, point: Point) -> bool:
        """Ray-casting point-in-polygon test (even-odd rule)."""
        pts = self.points
        n = len(pts)
        if n < 3:
            return False
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = pts[i].x, pts[i].y
            xj, yj = pts[j].x, pts[j].y
            intersects = (yi > point.y) != (yj > point.y) and point.x < (
                (xj - xi) * (point.y - yi) / (yj - yi) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    @property
    def bbox(self) -> BBox:
        if not self.points:
            return BBox(0.0, 0.0, 0.0, 0.0)
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        min_x, min_y = min(xs), min(ys)
        return BBox(min_x, min_y, max(xs) - min_x, max(ys) - min_y)
