"""The single source of truth for one image's annotations.

See docs/architecture/annotation-document.md. The document owns the shape list
(via an UndoTree so every mutation is undoable), the image metadata, and the
current selection (view state, not serialized). The on-disk format is the
existing COCO-like per-image JSON; ``to_dict``/``from_dict`` are the only
serialization path and round-trip exactly.
"""

from dataclasses import dataclass
from typing import Any

from labelvim.models.model import Point, Polygon, Rectangle, Shape
from labelvim.models.undo import UndoTree


@dataclass
class ImageMeta:
    path: str | None = None
    data: str | None = None  # imageData; usually null
    height: int | None = None
    width: int | None = None


@dataclass
class Selection:
    """Which shape/vertex is active. View state — never serialized or undone."""

    shape_index: int | None = None
    vertex_index: int | None = None

    def clear(self) -> None:
        self.shape_index = None
        self.vertex_index = None


def shape_from_annotation(index: int, anno: dict[str, Any]) -> Shape:
    category_id = anno.get("category_id")
    segmentation = anno.get("segmentation") or []
    if segmentation:
        # COCO segmentation is a list of flat [x1, y1, x2, y2, ...] rings; we keep
        # the first ring as the polygon's points.
        flat = segmentation[0]
        points = [Point(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
        return Polygon(id=index, category_id=category_id, points=points)
    x, y, w, h = anno["bbox"]
    return Rectangle(
        id=index,
        category_id=category_id,
        topleft=Point(x, y),
        bottomright=Point(x + w, y + h),
    )


def annotation_from_shape(index: int, shape: Shape) -> dict[str, Any]:
    b = shape.bbox
    segmentation: list[list[float]] = []
    if isinstance(shape, Polygon):
        flat: list[float] = []
        for p in shape.points:
            flat.append(p.x)
            flat.append(p.y)
        segmentation = [flat]
    return {
        "id": index,  # re-derived as the array index (see design decision)
        "category_id": shape.category_id,
        "bbox": [b.x, b.y, b.width, b.height],
        "area": b.width * b.height,
        "segmentation": segmentation,
        "iscrowd": 0,
    }


class AnnotationDocument:
    def __init__(self) -> None:
        self.meta = ImageMeta()
        self.undo = UndoTree()
        self.selection = Selection()

    @property
    def shapes(self) -> list[Shape]:
        return self.undo.shapes

    # --- mutations: all routed through undo so everything is undoable ---

    def add_shape(self, shape: Shape) -> None:
        self.undo.add_shape(shape)

    def remove_shape(self, index: int) -> None:
        self.undo.remove_shape(index)
        self.selection.clear()

    def move_shape(self, index: int, dx: float, dy: float) -> None:
        self.shapes[index].move(dx, dy)

    # --- queries ---

    def shape_at(self, point: Point) -> int | None:
        """Topmost shape containing the point, or None."""
        for index in range(len(self.shapes) - 1, -1, -1):
            if self.shapes[index].contains(point):
                return index
        return None

    # --- serialization (the only save/load path) ---

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnnotationDocument":
        doc = cls()
        doc.meta = ImageMeta(
            path=data.get("imagePath"),
            data=data.get("imageData"),
            height=data.get("imageHeight"),
            width=data.get("imageWidth"),
        )
        for index, anno in enumerate(data.get("annotations", [])):
            # Load directly into the shape list without recording undo history.
            doc.shapes.append(shape_from_annotation(index, anno))
        return doc

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotations": [
                annotation_from_shape(index, shape) for index, shape in enumerate(self.shapes)
            ],
            "imagePath": self.meta.path,
            "imageData": self.meta.data,
            "imageHeight": self.meta.height,
            "imageWidth": self.meta.width,
        }
