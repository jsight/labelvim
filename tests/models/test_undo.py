import pytest

from labelvim.models.model import Point, Rectangle
from labelvim.models.undo import UndoTree


@pytest.fixture
def rectangle():
    return Rectangle(id=1, category_id=0, topleft=Point(0.1, 0.1), bottomright=Point(0.5, 0.5))


@pytest.fixture
def rectangle2():
    return Rectangle(id=2, category_id=0, topleft=Point(0.2, 0.2), bottomright=Point(0.6, 0.6))


def test_add_shape(rectangle):
    img = UndoTree()
    img.add_shape(rectangle)
    assert len(img.shapes) == 1
    assert img.shapes[0].id == 1


def test_undo_add_shape(rectangle):
    img = UndoTree()
    img.add_shape(rectangle)
    assert len(img.shapes) == 1
    img.undo()
    assert len(img.shapes) == 0


def test_redo_add_shape(rectangle):
    img = UndoTree()
    img.add_shape(rectangle)
    img.undo()
    assert len(img.shapes) == 0
    img.redo()
    assert len(img.shapes) == 1
    assert img.shapes[0].id == 1


def test_remove_shape(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.remove_shape(0)
    assert len(img.shapes) == 1
    assert img.shapes[0].id == 2


def test_undo_remove_shape(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.remove_shape(0)
    assert len(img.shapes) == 1
    img.undo()
    assert len(img.shapes) == 2
    assert img.shapes[0].id == 1
    assert img.shapes[1].id == 2


def test_redo_remove_shape(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.remove_shape(0)
    img.undo()
    assert len(img.shapes) == 2
    img.redo()
    assert len(img.shapes) == 1
    assert img.shapes[0].id == 2


def test_undo_at_root(rectangle):
    img = UndoTree()
    assert not img.undo()  # Nothing to undo
    img.add_shape(rectangle)
    img.undo()
    assert not img.undo()  # Back at root


def test_redo_no_child(rectangle):
    img = UndoTree()
    assert not img.redo()  # Nothing to redo
    img.add_shape(rectangle)
    img.undo()
    img.redo()
    assert not img.redo()  # Only one redo possible


def test_branching(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.undo()  # Undo add rectangle2
    # Add a different shape after undo, should create a branch
    rect3 = Rectangle(id=3, category_id=0, topleft=Point(0.3, 0.3), bottomright=Point(0.7, 0.7))
    img.add_shape(rect3)
    assert len(img.shapes) == 2
    assert img.shapes[1].id == 3
    # Redo should not be possible now (branch was created)
    assert not img.redo()


def test_redo_after_branching(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    assert len(img.shapes) == 2
    assert img.shapes[0] == rectangle
    assert img.shapes[1] == rectangle2
    img.undo()  # Undo add rectangle2
    assert len(img.shapes) == 1
    assert img.shapes[0] == rectangle
    img.redo()
    assert len(img.shapes) == 2
    assert img.shapes[0] == rectangle
    assert img.shapes[1] == rectangle2
