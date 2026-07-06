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


def _int_rect(id=1, category_id=0, x1=10, y1=20, x2=30, y2=40):
    return Rectangle(
        id=id, category_id=category_id, topleft=Point(x1, y1), bottomright=Point(x2, y2)
    )


def test_move_shape_and_undo_redo():
    img = UndoTree()
    img.add_shape(_int_rect())
    img.move_shape(0, 5, -3)
    assert (img.shapes[0].topleft.x, img.shapes[0].topleft.y) == (15, 17)
    assert (img.shapes[0].bottomright.x, img.shapes[0].bottomright.y) == (35, 37)
    img.undo()
    assert (img.shapes[0].topleft.x, img.shapes[0].topleft.y) == (10, 20)
    img.redo()
    assert (img.shapes[0].topleft.x, img.shapes[0].topleft.y) == (15, 17)


def test_replace_shape_and_undo_redo():
    img = UndoTree()
    img.add_shape(_int_rect())
    img.replace_shape(0, _int_rect(category_id=2, x2=99))
    assert img.shapes[0].category_id == 2
    assert img.shapes[0].bottomright.x == 99
    img.undo()
    assert img.shapes[0].category_id == 0
    assert img.shapes[0].bottomright.x == 30
    img.redo()
    assert img.shapes[0].bottomright.x == 99


def test_interleaved_add_move_remove(rectangle, rectangle2):
    img = UndoTree()
    img.add_shape(rectangle)
    img.add_shape(rectangle2)
    img.move_shape(0, 1, 1)
    img.remove_shape(1)
    assert len(img.shapes) == 1
    img.undo()  # undo remove
    assert len(img.shapes) == 2
    img.undo()  # undo move
    assert img.shapes[0].topleft.x == rectangle.topleft.x
    img.undo()  # undo add rectangle2
    assert len(img.shapes) == 1
    img.redo()  # redo add rectangle2
    assert len(img.shapes) == 2


def test_find_shape_index_by_id_or_none():
    img = UndoTree()
    img.add_shape(_int_rect(id=7))
    assert img.find_shape_index_by_id_or_none(7) == 0
    assert img.find_shape_index_by_id_or_none(999) is None


def test_undo_all_adds_returns_to_empty():
    # Regression: clear() used to alias self.shapes with the root node's
    # snapshot, so in-place command mutations corrupted the root state and undo
    # could never reach empty (a boundary undo even re-added a shape).
    img = UndoTree()
    for i in range(3):
        img.add_shape(_int_rect(id=i))
    assert [s.id for s in img.shapes] == [0, 1, 2]
    assert img.undo() and [s.id for s in img.shapes] == [0, 1]
    assert img.undo() and [s.id for s in img.shapes] == [0]
    assert img.undo() and img.shapes == []  # reaches empty, not [0, 1]
    assert img.undo() is False  # past the root is a no-op, not a phantom redo
    assert img.shapes == []


def test_undo_redo_full_cycle_three_ops():
    img = UndoTree()
    for i in range(3):
        img.add_shape(_int_rect(id=i))
    for _ in range(3):
        img.undo()
    assert img.shapes == []
    for _ in range(3):
        img.redo()
    assert [s.id for s in img.shapes] == [0, 1, 2]


def test_mixed_ops_fully_undo_to_empty():
    img = UndoTree()
    img.add_shape(_int_rect(id=0))
    img.add_shape(_int_rect(id=1))
    img.move_shape(0, 5, 5)
    img.replace_shape(1, _int_rect(id=9, x2=99))
    img.remove_shape(0)
    for _ in range(5):
        img.undo()
    assert img.shapes == []
    assert img.undo() is False
