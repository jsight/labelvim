from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import copy

from labelvim.models.shape import Shape

# Command interface for undoable actions
class Command(ABC):
    @abstractmethod
    def execute(self, image: 'Image') -> None:
        pass

    @abstractmethod
    def undo(self, image: 'Image') -> None:
        pass

@dataclass
class AddShapeCommand(Command):
    shape: Shape

    def execute(self, image: 'Image') -> None:
        image.shapes.append(copy.deepcopy(self.shape))

    def undo(self, image: 'Image') -> None:
        image.shapes.pop()

@dataclass
class RemoveShapeCommand(Command):
    index: int
    shape: Optional[Shape] = None

    def execute(self, image: 'Image') -> None:
        self.shape = copy.deepcopy(image.shapes[self.index])
        image.shapes.pop(self.index)

    def undo(self, image: 'Image') -> None:
        image.shapes.insert(self.index, copy.deepcopy(self.shape))

# Undo tree node
@dataclass
class UndoTreeNode:
    state: List[Shape]  # Snapshot of shapes
    command: Optional[Command]  # Action that led to this state
    parent: Optional['UndoTreeNode'] = None
    children: List['UndoTreeNode'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

@dataclass
class Image:
    shapes: List[Shape]
    undo_tree: UndoTreeNode
    current_node: UndoTreeNode

    def __init__(self):
        initial_state = []
        initial_node = UndoTreeNode(state=initial_state, command=None, parent=None)
        self.shapes = initial_state
        self.undo_tree = initial_node
        self.current_node = initial_node

    def execute_command(self, command: Command) -> None:
        # Execute the command
        command.execute(self)
        # Create a new node with the current state
        new_node = UndoTreeNode(
            state=copy.deepcopy(self.shapes),
            command=command,
            parent=self.current_node
        )
        # Add the new node as a child of the current node
        self.current_node.children.append(new_node)
        # Move to the new node
        self.current_node = new_node

    def undo(self) -> bool:
        if self.current_node.parent is None:
            return False  # No parent to undo to
        # Move to parent node
        self.current_node.command.undo(self)
        self.current_node = self.current_node.parent
        self.shapes = copy.deepcopy(self.current_node.state)
        return True

    def redo(self, child_index: int = 0) -> bool:
        if not self.current_node.children:
            return False  # No children to redo to
        # Move to the specified child node
        self.current_node = self.current_node.children[child_index]
        self.current_node.command.execute(self)
        self.shapes = copy.deepcopy(self.current_node.state)
        return True

    def add_shape(self, shape: Shape) -> None:
        self.execute_command(AddShapeCommand(shape))

    def remove_shape(self, index: int) -> None:
        self.execute_command(RemoveShapeCommand(index))

