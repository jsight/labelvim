"""AnnotationDocument serialization round-trip tests (JSON stability)."""

import json
from pathlib import Path

import pytest

from labelvim.models.document import AnnotationDocument
from labelvim.models.model import Polygon, Rectangle

RECT_DOC = {
    "annotations": [
        {
            "id": 0,
            "category_id": 0,
            "bbox": [280, 217, 138, 66],
            "area": 9108,
            "segmentation": [],
            "iscrowd": 0,
        }
    ],
    "imagePath": "33934.jpg",
    "imageData": None,
    "imageHeight": 426,
    "imageWidth": 640,
}

POLY_DOC = {
    "annotations": [
        {
            "id": 0,
            "category_id": 2,
            "bbox": [10, 20, 90, 180],
            "area": 16200,
            "segmentation": [[10, 20, 100, 20, 100, 200, 10, 200]],
            "iscrowd": 0,
        }
    ],
    "imagePath": "poly.jpg",
    "imageData": None,
    "imageHeight": 300,
    "imageWidth": 300,
}


def test_roundtrip_rectangle():
    assert AnnotationDocument.from_dict(RECT_DOC).to_dict() == RECT_DOC


def test_roundtrip_polygon():
    assert AnnotationDocument.from_dict(POLY_DOC).to_dict() == POLY_DOC


def test_roundtrip_is_idempotent():
    once = AnnotationDocument.from_dict(RECT_DOC).to_dict()
    twice = AnnotationDocument.from_dict(once).to_dict()
    assert once == twice == RECT_DOC


def test_from_dict_builds_typed_shapes():
    rect_doc = AnnotationDocument.from_dict(RECT_DOC)
    assert isinstance(rect_doc.shapes[0], Rectangle)
    poly_doc = AnnotationDocument.from_dict(POLY_DOC)
    assert isinstance(poly_doc.shapes[0], Polygon)
    assert len(poly_doc.shapes[0].points) == 4


def test_meta_round_trips():
    doc = AnnotationDocument.from_dict(RECT_DOC)
    assert doc.meta.path == "33934.jpg"
    assert doc.meta.width == 640
    assert doc.meta.height == 426
    assert doc.meta.data is None


def test_ids_reindex_contiguously_after_remove():
    multi = {
        "annotations": [
            {
                "id": 0,
                "category_id": 0,
                "bbox": [0, 0, 10, 10],
                "area": 100,
                "segmentation": [],
                "iscrowd": 0,
            },
            {
                "id": 1,
                "category_id": 0,
                "bbox": [5, 5, 10, 10],
                "area": 100,
                "segmentation": [],
                "iscrowd": 0,
            },
            {
                "id": 2,
                "category_id": 0,
                "bbox": [9, 9, 10, 10],
                "area": 100,
                "segmentation": [],
                "iscrowd": 0,
            },
        ],
        "imagePath": "m.jpg",
        "imageData": None,
        "imageHeight": 100,
        "imageWidth": 100,
    }
    doc = AnnotationDocument.from_dict(multi)
    doc.remove_shape(0)  # drop the first
    out = doc.to_dict()
    assert [a["id"] for a in out["annotations"]] == [0, 1]  # re-derived, contiguous


def test_shape_at_returns_topmost():
    doc = AnnotationDocument.from_dict(RECT_DOC)
    from labelvim.models.model import Point

    assert doc.shape_at(Point(300, 240)) == 0  # inside the rectangle
    assert doc.shape_at(Point(0, 0)) is None  # outside


def test_real_example_file_round_trips():
    example = Path(__file__).resolve().parents[2] / "examples" / "33934.json"
    if not example.exists():
        pytest.skip("example fixture not present")
    data = json.loads(example.read_text())
    assert AnnotationDocument.from_dict(data).to_dict() == data
