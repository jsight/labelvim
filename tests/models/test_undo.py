import pytest
from labelvim.models.undo import UndoTree, AddShapeCommand, RemoveShapeCommand
from labelvim.models.model import Rectangle, Point

@pytest.fixture
def rectangle():
    return Rectangle(
        name="rect1",
        topleft=Point(0.1, 0.1),
        bottomright=Point(0.5, 0.5)
    )

@pytest.fixture
def rectangle2():
    return Rectangle(
        name="rect2",
        topleft=Point(0.2, 0.2),
        bottomright=Point(0.6, 0.6)
    )

def test_add_shape(rectangle):
    img = UndoTree()
    img.add_shape(rectangle)
    assert len(img.shapes) == 1
    assert img.shapes[0].name == "rect1"

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
    assert img.shapes[0].name == "rect1"

def test_remove_shape(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.remove_shape(0)
    assert len(img.shapes) == 1
    assert img.shapes[0].name == "rect2"

def test_undo_remove_shape(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.remove_shape(0)
    assert len(img.shapes) == 1
    img.undo()
    assert len(img.shapes) == 2
    assert img.shapes[0].name == "rect1"
    assert img.shapes[1].name == "rect2"

def test_redo_remove_shape(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.remove_shape(0)
    img.undo()
    assert len(img.shapes) == 2
    img.redo()
    assert len(img.shapes) == 1
    assert img.shapes[0].name == "rect2"

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
    rect3 = Rectangle(name="rect3", topleft=Point(0.3, 0.3), bottomright=Point(0.7, 0.7))
    img.add_shape(rect3)
    assert len(img.shapes) == 2
    assert img.shapes[1].name == "rect3"
    # Redo should not be possible now (branch was created)
    assert not img.redo() 
