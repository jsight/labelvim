import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from labelvim.models.model import Shape


# Command interface for undoable actions
class Command(ABC):
    @abstractmethod
    def execute(self, image: "UndoTree") -> None:
        pass

    @abstractmethod
    def undo(self, image: "UndoTree") -> None:
        pass


@dataclass
class AddShapeCommand(Command):
    shape: Shape

    def execute(self, image: "UndoTree") -> None:
        image.shapes.append(copy.deepcopy(self.shape))

    def undo(self, image: "UndoTree") -> None:
        image.shapes.pop()


@dataclass
class RemoveShapeCommand(Command):
    index: int
    shape: Shape | None = None

    def execute(self, image: "UndoTree") -> None:
        self.shape = copy.deepcopy(image.shapes[self.index])
        image.shapes.pop(self.index)

    def undo(self, image: "UndoTree") -> None:
        assert self.shape is not None, "execute() must run before undo()"
        image.shapes.insert(self.index, copy.deepcopy(self.shape))


# Undo tree node
@dataclass
class UndoTreeNode:
    state: list[Shape]  # Snapshot of shapes
    command: Command | None  # Action that led to this state
    parent: "UndoTreeNode | None" = None
    children: list["UndoTreeNode"] = field(default_factory=list)


@dataclass
class UndoTree:
    shapes: list[Shape]
    undo_tree: UndoTreeNode
    current_node: UndoTreeNode

    def __init__(self):
        self.clear()

    def clear(self):
        initial_state: list[Shape] = []
        initial_node = UndoTreeNode(state=initial_state, command=None, parent=None)
        self.shapes = initial_state
        self.undo_tree = initial_node
        self.current_node = initial_node

    def execute_command(self, command: Command) -> None:
        # Execute the command
        command.execute(self)
        # Create a new node with the current state
        new_node = UndoTreeNode(
            state=copy.deepcopy(self.shapes), command=command, parent=self.current_node
        )
        # Add the new node as a child of the current node
        self.current_node.children.append(new_node)
        # Move to the new node
        self.current_node = new_node

    def undo(self) -> bool:
        if self.current_node.parent is None:
            return False  # No parent to undo to
        # Move to parent node
        assert self.current_node.command is not None  # non-root nodes always have a command
        self.current_node.command.undo(self)
        self.current_node = self.current_node.parent
        self.shapes = copy.deepcopy(self.current_node.state)
        return True

    def redo(self, child_index: int = 0) -> bool:
        if not self.current_node.children:
            return False  # No children to redo to
        # Move to the specified child node
        self.current_node = self.current_node.children[child_index]
        assert self.current_node.command is not None  # child nodes always have a command
        self.current_node.command.execute(self)
        self.shapes = copy.deepcopy(self.current_node.state)
        return True

    def add_shape(self, shape: Shape) -> None:
        self.execute_command(AddShapeCommand(shape))

    def remove_shape(self, index: int) -> None:
        self.execute_command(RemoveShapeCommand(index))

    def remove_shape_by_id(self, shape_id: int) -> None:
        self.remove_shape(self.find_shape_index_by_id(shape_id))

    def find_shape_index_by_id(self, shape_id: int) -> int:
        return [index for index, value in enumerate(self.shapes) if value.id == shape_id][0]
