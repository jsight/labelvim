"""Tests for the Qt-free ImageDirectoryService."""

import os

from labelvim.services.image_directory import ImageDirectoryService


def _mkimgs(tmp_path, names):
    for n in names:
        (tmp_path / n).write_bytes(b"")
    return str(tmp_path)


def _svc(tmp_path, names):
    svc = ImageDirectoryService()
    svc.load(_mkimgs(tmp_path, names))
    return svc


def test_load_scans_only_images(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.png", "notes.txt", "c.jpeg"])
    assert svc.count == 3
    assert set(svc.stems) == {"a", "b", "c"}
    assert svc.current_index == -1


def test_load_empty_dir_string(tmp_path):
    svc = ImageDirectoryService()
    assert svc.load("") == []
    assert svc.count == 0


def test_next_previous_clamp(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.jpg", "c.jpg"])
    assert svc.next() == 0  # from -1
    assert svc.next() == 1
    assert svc.next() == 2
    assert svc.next() == 2  # clamps at the end
    assert svc.previous() == 1
    assert svc.previous() == 0
    assert svc.previous() == 0  # clamps at the start


def test_select_validity(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.jpg"])
    assert svc.select(0) is True
    assert svc.current_index == 0
    assert svc.select(5) is False
    assert svc.select(-1) is False


def test_annotation_tracking(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.jpg"])
    svc.set_save_dir("/save", {"a"})
    assert svc.has_annotation("a")
    assert not svc.has_annotation("b")
    assert not svc.has_annotation(None)
    svc.mark_annotated("b")
    assert svc.has_annotation("b")
    assert svc.json_path("a") == os.path.join("/save", "a.json")


def test_remove_annotated_returns_json_and_clamps(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.jpg", "c.jpg"])
    svc.set_save_dir("/save", set(svc.stems))
    svc.select(2)
    stem = svc.stems[2]
    json_path = svc.remove(2)
    assert json_path == os.path.join("/save", stem + ".json")
    assert svc.count == 2
    assert svc.current_index == 1  # clamped from 2


def test_remove_unannotated_returns_none(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.jpg"])
    svc.set_save_dir("/save", set())
    assert svc.remove(0) is None
    assert svc.count == 1


def test_remove_invalid_index(tmp_path):
    svc = _svc(tmp_path, ["a.jpg"])
    assert svc.remove(9) is None
    assert svc.count == 1


def test_current_helpers(tmp_path):
    svc = _svc(tmp_path, ["a.jpg", "b.jpg"])
    assert svc.current_path() is None  # nothing selected yet
    svc.select(0)
    assert svc.current_path() in svc.image_paths
    assert svc.current_stem() in {"a", "b"}
