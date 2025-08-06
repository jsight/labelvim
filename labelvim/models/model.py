from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Labels:
    labels: List[str]

    def add_label(self, label):
        if label in self.labels:
            return
        self.labels.append(label)
    
    def get_index_for_label(self, label):
        return self.labels.index(label)

@dataclass
class Point:
    x: float
    y: float
    selected: bool = False

@dataclass
class Shape(ABC):
    id: Optional[int]
    category_id: Optional[int]

@dataclass
class Rectangle(Shape):
    topleft: Point
    bottomright: Point

    def __post_init__(self):
        assert self.topleft.x <= self.bottomright.x, "topleft.x must be <= bottomright.x"
        assert self.topleft.y <= self.bottomright.y, "topleft.y must be <= bottomright.y"

    def to_legacy_json(self, img_width, img_height):
        return { "bbox": [
            self.topleft.x * img_width,
            self.topleft.y * img_height,
            (self.bottomright.x * img_width) - (self.topleft.x * img_width),
            (self.bottomright.y * img_height) - (self.topleft.y * img_height),
        ]}

    def edit(self) -> None:
        # Placeholder for editing implementation
        pass

    def contains(self, point: Point) -> bool:
        return (self.topleft.x <= point.x <= self.bottomright.x and
                self.topleft.y <= point.y <= self.bottomright.y)

@dataclass
class Polygon(Shape):
    rectangle: Rectangle
    points: List[Point]

    def edit(self) -> None:
        # Placeholder for editing implementation
        pass

    def contains(self, point: Point) -> bool:
        # Placeholder for point-in-polygon algorithm
        return False

# Example usage
if __name__ == "__main__":
    # Create a rectangle
    rect = Rectangle(
        name="box1",
        topleft=Point(0.1, 0.1),
        bottomright=Point(0.5, 0.5)
    )
    print(f"Rectangle {rect.name}: {rect.topleft}, {rect.bottomright}")

    # Create a polygon
    poly = Polygon(
        name="triangle1",
        points=[
            Point(0.2, 0.2),
            Point(0.4, 0.2),
            Point(0.3, 0.4)
        ]
    )
    print(f"Polygon {poly.name} with {len(poly.points)} points")
