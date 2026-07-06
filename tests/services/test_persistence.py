"""Tests for the Qt-free AnnotationPersistenceService I/O."""

import json

from labelvim.models.document import AnnotationDocument
from labelvim.services.persistence import AnnotationPersistenceService

DOC = {
    "annotations": [
        {
            "id": 0,
            "category_id": 1,
            "bbox": [10, 20, 30, 40],
            "area": 1200,
            "segmentation": [],
            "iscrowd": 0,
        }
    ],
    "imagePath": "img.jpg",
    "imageData": None,
    "imageHeight": 100,
    "imageWidth": 200,
}


def test_write_document_round_trips(tmp_path):
    svc = AnnotationPersistenceService()
    doc = AnnotationDocument.from_dict(DOC)
    path = svc.write_document(doc, str(tmp_path), "img")
    assert path == str(tmp_path / "img.json")
    assert json.loads((tmp_path / "img.json").read_text()) == DOC


def test_move_into_save_dir_moves_when_separate(tmp_path):
    load = tmp_path / "load"
    save = tmp_path / "save"
    load.mkdir()
    save.mkdir()
    src = load / "img.jpg"
    src.write_bytes(b"data")
    svc = AnnotationPersistenceService()
    dest = svc.move_into_save_dir(str(src), str(save))
    assert dest == str(save / "img.jpg")
    assert not src.exists()
    assert (save / "img.jpg").read_bytes() == b"data"


def test_move_into_save_dir_noop_when_same(tmp_path):
    src = tmp_path / "img.jpg"
    src.write_bytes(b"data")
    svc = AnnotationPersistenceService()
    assert svc.move_into_save_dir(str(src), str(tmp_path)) is None
    assert src.exists()


def test_move_into_save_dir_noop_without_save_dir(tmp_path):
    src = tmp_path / "img.jpg"
    src.write_bytes(b"data")
    svc = AnnotationPersistenceService()
    assert svc.move_into_save_dir(str(src), "") is None
    assert src.exists()


def test_flags_default_off():
    svc = AnnotationPersistenceService()
    assert svc.save_mask is False
    assert svc.include_img is False
