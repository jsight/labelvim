# AnnotationDocument — design note (Phase 2)

Status: **proposed** (gur-c5ee6b23.1). This is the keystone for Phase 2; the
canvas/undo/save-load tasks build on it.

## Problem

Annotation state today is scattered, with no single owner:

- `CanvasWidget.undo_tree.shapes` holds the authoritative shape list (good), but
- parallel/legacy state lingers: `self.rectangles`, `self.polygon_points`,
  `self.selected_object`, `self.selected_object_subset`, `self.selected_vertex`,
  `self.line_segment`, plus image metadata that only exists transiently during
  save (`imagePath/imageWidth/imageHeight`).
- Serialization is bespoke and lossy: `update_annotation_from_json` rebuilds only
  `Rectangle`s and **drops polygon segmentation**; `update_annotation_to_json`
  reads `undo_tree.shapes` but also references the legacy `self.rectangles`.

This scatter is the root cause of the recurring save/restore/edit/undo drift
bugs (see the "Fixed save/restore…" commit history).

## Decision

Introduce `labelvim/models/document.py::AnnotationDocument` as the **single
source of truth** for one image's annotations. The canvas becomes a *view* that
renders from the document and emits intents; `UndoTree` operates *on* the
document's shape list.

### Coordinate convention (settled)

All model coordinates are stored in **original image pixel space**, never screen
space. This is already true today (`Rectangle.topleft/bottomright` are image
pixels; `bbox` on disk is image pixels). The view maps image→screen at paint
time using `scale_factor`. Saving therefore never depends on zoom state — which
removes an entire class of coordinate-corruption bugs. Phase 4 adds round-trip
tests pinning `map_to_original(map_to_screen(p)) == p`.

## Shape

```python
@dataclass
class ImageMeta:
    path: str | None = None         # imagePath
    width: int | None = None        # imageWidth
    height: int | None = None       # imageHeight

@dataclass
class Selection:
    shape_index: int | None = None  # index into document.shapes
    vertex_index: int | None = None # selected vertex within that shape (edit mode)

class AnnotationDocument:
    meta: ImageMeta
    shapes: list[Shape]             # the ONE shape store (Rectangle | Polygon)
    selection: Selection
    undo: UndoTree                  # operates on self.shapes

    # --- queries (no Qt) ---
    def shape_at(self, point: Point) -> int | None: ...
    def vertex_at(self, point: Point, radius: float) -> tuple[int, int] | None: ...

    # --- mutations: all go through undo so everything is undoable ---
    def add_shape(self, shape: Shape) -> None: ...
    def remove_shape(self, index: int) -> None: ...
    def move_shape(self, index: int, dx: float, dy: float) -> None: ...
    def move_vertex(self, shape_index: int, vertex_index: int, to: Point) -> None: ...

    # --- serialization (the only save/load path) ---
    @classmethod
    def from_dict(cls, data: dict) -> "AnnotationDocument": ...
    def to_dict(self) -> dict: ...
```

### On-disk schema (unchanged — COCO-like, per image)

```json
{
  "annotations": [
    {"id": 0, "category_id": 0, "bbox": [x, y, w, h],
     "area": 9108, "segmentation": [[x1,y1,...]], "iscrowd": 0}
  ],
  "imagePath": "33934.jpg", "imageData": null,
  "imageHeight": 426, "imageWidth": 640
}
```

`to_dict`/`from_dict` own the mapping between this schema and the typed model,
and must round-trip: `from_dict(d).to_dict() == d` for any valid `d` (stable key
order, ints stay ints, no float drift). Unlike today, polygon `segmentation`
survives the round trip.

## Migration plan (maps to the Phase 2 subtasks)

1. **This note + skeleton** (gur-c5ee6b23.1).
2. **Geometry** (gur-c5ee6b23.2): real `Polygon.contains` (ray cast),
   `Shape.move`, bbox, vertex hit-test — pure Python, unit-tested.
3. **Move state into the document** (gur-c5ee6b23.3): delete the parallel
   `self.rectangles`/selection attrs; canvas reads/writes `self.document`.
4. **Paint from model** (gur-c5ee6b23.4): `paintEvent` derives everything from
   `document` + `scale_factor`; migrate Qt enums to scoped forms (clears the
   mypy stub friction noted in P1.6).
5. **Undo through the document** (gur-c5ee6b23.5): add move/edit commands so all
   mutations are undoable via one path.
6. **Save/load through the document** (gur-c5ee6b23.6): replace the bespoke
   `update_annotation_from/to_json` with `to_dict/from_dict`.

## Open questions for review

- **Selection in undo?** Proposal: selection is *view* state, **not** part of the
  undo history (undoing shouldn't replay cursor moves). Shape data only.
- **`id` semantics:** today `id` is the list position (`len(shapes)`), which
  breaks after removal. Proposal: `id` becomes a stable per-shape identifier
  assigned on creation; on-disk `id` is re-derived as the array index only at
  `to_dict` time (to keep COCO output contiguous). Confirm acceptable.
- **Polygon model:** `Polygon` currently carries both a `rectangle` (bbox) and
  `points`. Proposal: keep `points` authoritative and compute the bbox on demand
  rather than storing/syncing it.
