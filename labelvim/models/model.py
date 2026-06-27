from abc import ABC
from dataclasses import dataclass


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


@dataclass
class Shape(ABC):
    id: int | None
    category_id: int | None


@dataclass
class Rectangle(Shape):
    topleft: Point
    bottomright: Point

    def __post_init__(self) -> None:
        assert self.topleft.x <= self.bottomright.x, "topleft.x must be <= bottomright.x"
        assert self.topleft.y <= self.bottomright.y, "topleft.y must be <= bottomright.y"

    def to_legacy_json(self) -> dict[str, list[float]]:
        return {
            "bbox": [
                self.topleft.x,
                self.topleft.y,
                self.bottomright.x - self.topleft.x,
                self.bottomright.y - self.topleft.y,
            ]
        }

    def edit(self) -> None:
        # Placeholder for editing implementation
        pass

    def contains(self, point: Point) -> bool:
        return (
            self.topleft.x <= point.x <= self.bottomright.x
            and self.topleft.y <= point.y <= self.bottomright.y
        )


@dataclass
class Polygon(Shape):
    rectangle: Rectangle
    points: list[Point]

    def edit(self) -> None:
        # Placeholder for editing implementation
        pass

    def contains(self, point: Point) -> bool:
        # Placeholder for point-in-polygon algorithm
        return False
