import logging

from PyQt5 import QtWidgets
from PyQt5.QtCore import QStringListModel, Qt, pyqtSignal
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QAction, QInputDialog, QMenu, QMessageBox

# External imports
from labelvim.utils.config import ANNOTATION_TYPE
from labelvim.widgets.custom_delegates import CustomDelegate

logger = logging.getLogger(__name__)


class CustomListViewWidget(QtWidgets.QListView):
    """
    A custom QListView widget with added functionalities such as item selection,
    item removal, list clearing, and handling mouse events to toggle checkbox states.

    Signals:
        update_list (list): Emitted to update the list of labels.
        notify_selected_item (str): Emitted when an item is selected,
                                    containing the selected item's text.

    Attributes:
        model (QStandardItemModel): The data model for storing list items with checkboxes.
        label_list (list): A list to store label names displayed in the list view.
    """

    update_list = pyqtSignal(list)
    notify_selected_item = pyqtSignal(str, int)

    def __init__(self, parent=None):
        """
        Initializes the CustomListViewWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.label_list = []
        self.set_model()
        self.set_label_list()
        self.selectionModel().currentChanged.connect(self.get_selected_item)
        self.update_list.connect(self.set_label_list)
        self.index = 0

    def set_model(self):
        """
        Sets the data model for the list view and enables updates.
        """
        self.setModel(self.model)
        self.setUpdatesEnabled(True)

    def set_label_list(self, label_list: list | None = None):
        """
        Updates the list view with a new list of labels.

        Args:
            label_list (list, optional): A list of label names to display. Defaults to an empty list.
        """
        logger.debug(f"Label List in set label list: {label_list}")
        self.model.clear()
        if isinstance(label_list, list) and len(label_list) > 0:
            self.label_list = label_list
            for file_name in self.label_list:
                item = QStandardItem(file_name)
                item.setCheckable(True)
                item.setEditable(False)
                # Store the state in the item
                item.setData(False, Qt.UserRole + 1)  # False means unchecked
                self.model.appendRow(item)
            self.set_current_index(self.index)

    def get_selected_item(self, current, previous):
        """
        Emits the signal with the currently selected item's text.

        Args:
            current (QModelIndex): The index of the current item.
            previous (QModelIndex): The index of the previously selected item.
        """
        logger.debug(f"Current: {current.row()}")
        current_idx = current.row()
        if current_idx < 0:
            current_idx = 0
        self.index = current_idx  # self.selectedIndexes()[0].row()
        self.notify_selected_item.emit(self.model.data(current, Qt.DisplayRole), self.index)

    def remove_selected_item(self):
        """
        Removes the currently selected item from the list view.
        """
        if len(self.selectedIndexes()) > 0:
            self.model.removeRow(self.selectedIndexes()[0].row())

    def update_current_index(self, index):
        """
        Updates the current selection in the list view to the specified index.

        Args:
            index (QModelIndex): The index to set as the current selection.
        """
        self.setCurrentIndex(index)

    def next_index(self):
        """
        Moves the selection to the next item in the list view, if possible.
        """
        self.index = self.selectedIndexes()[0].row()
        if self.index < self.model.rowCount() - 1:
            self.setCurrentIndex(self.model.index(self.index + 1, 0))
            self.index = self.selectedIndexes()[0].row()
            # self.setCurrentIndex(self.model.index(self.selectedIndexes()[0].row() + 1, 0))

    def previous_index(self):
        """
        Moves the selection to the previous item in the list view, if possible.
        """
        index = self.selectedIndexes()[0].row()
        if index > 0:
            self.setCurrentIndex(self.model.index(index - 1, 0))
            self.index = self.selectedIndexes()[0].row()
            # self.setCurrentIndex(self.model.index(self.selectedIndexes()[0].row() - 1, 0))
        # return index

    def clear_list(self):
        """
        Clears all items from the list view.
        """
        self.model.removeRows(0, self.model.rowCount())

    def clear_selection(self):
        """
        Clears the current selection in the list view.
        """
        self.clearSelection()

    def get_label_list(self):
        """
        Returns the current list of labels.

        Returns:
            list: The list of label names.
        """
        return self.label_list

    def get_selected_index(self):
        """
        Returns the indexes of the selected items.

        Returns:
            list: A list of QModelIndex objects representing the selected items.
        """
        return self.selectedIndexes()

    def get_current_index(self):
        """
        Returns the index of the current selection.


        Returns:
            int: The index of the current selection.
        """
        return self.index

    def mousePressEvent(self, event):
        """
        Handles mouse press events on the list view. Toggles the checkbox state of
        the item under the mouse cursor.

        Args:
            event (QMouseEvent): The mouse event object.
        """
        index = self.indexAt(event.pos())
        # print(f"Index: {index.row()}")
        # print(f"model row count {self.model.rowCount()}")
        if index.isValid():
            item = self.model.itemFromIndex(index)
            logger.debug(f"Item: {item.text()}")
            current_state = item.data(Qt.UserRole + 1)

            # Toggle the state
            new_state = not current_state
            item.setData(new_state, Qt.UserRole + 1)
            self.index = self.selectedIndexes()[0].row()

        # Call the parent class's mousePressEvent to handle other events
        super().mousePressEvent(event)

    def set_current_index(self, index):
        """
        Sets the current selection in the list view to the specified index.

        Args:
            index (int): The index to set as the current selection.
        """
        self.setCurrentIndex(self.model.index(index, 0))


class CustomLabelWidget(QtWidgets.QListView):
    """
    A custom QListView widget for displaying and managing a list of labels.
    Allows adding new labels by double-clicking and supports updating the list
    based on an annotation type.

    Attributes:
        model (QStringListModel): The data model for storing label names.
        label_list (list): A list to store label names displayed in the list view.
        annotation_type (str): The type of annotation currently being handled.
    """

    update_label_list_slot_transmitter = pyqtSignal(list)  # Signal to update the label list
    update_label_list_slot_receiver = pyqtSignal(list)  # Signal to update the label list

    def __init__(self, parent=None):
        """
        Initializes the CustomLabelWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        # Initialize the model and label list
        self.model = QStringListModel()
        # label list is empty
        self.label_list = []
        self.set_model()
        self.delegate = CustomDelegate(self)
        self.setItemDelegate(self.delegate)
        # Set the annotation type to None
        self.annotation_type = ANNOTATION_TYPE.NONE
        # Connect the signals
        self.update_label_list_slot_receiver.connect(
            self.__update_list
        )  # Connect the signal to update the label list
        self.model.dataChanged.connect(self.on_data_changed)  # Connect the dataChanged signal

    def set_model(self):
        """
        Sets the data model for the list view and enables updates.
        """
        # set the model and enable updates
        self.setModel(self.model)
        self.setUpdatesEnabled(True)
        # Set the edit triggers to NoEditTriggers
        self.setEditTriggers(QtWidgets.QListView.NoEditTriggers)

    def set_label_list(self, label_list: list | None = None):
        """
        Updates the list view with a new list of labels.

        Args:
            label_list (list, optional): A list of label names to display. Defaults to an empty list.
        """
        logger.debug("%s %s", "Setting label list to:", label_list)
        # Check if the label list is a non-empty list
        if isinstance(label_list, list) and len(label_list) > 0:
            # Clear the model before updating
            self.clear_list()
            # Update the label list and model
            self.label_list = label_list
            # update the model
            logger.debug(f"Label List in set label list: {self.label_list}")
            self.model.setStringList(self.label_list)

    def clear_list(self):
        """
        Clears all items from the list view.
        """
        # Clear the list and update the model
        self.model.setStringList([])

    def __update_list(self, label_list: list):
        """
        Updates the list of labels based on the provided label list.

        Args:
            label_list (list): The list of labels to update.
        """
        # Get the label list based on the annotation type
        self.set_label_list(label_list)

    def update_annotation_type(self, annotation_type):
        """
        Updates the annotation type currently being used.

        Args:
            annotation_type (str): The new annotation type to use.
        """
        # Set the annotation type based on the provided value
        # self.annotation_type = {
        #     "Object Detection": ANNOTATION_TYPE.BBOX,
        #     "Segmentation": ANNOTATION_TYPE.POLYGON
        # }.get(annotation_type, ANNOTATION_TYPE.NONE)
        # Print the annotation type
        self.annotation_type = annotation_type
        logger.debug(f"Annotation Type: {self.annotation_type}")

    def mouseDoubleClickEvent(self, event):
        """
        Handles mouse double-click events on the list view. Prompts the user to
        add a new label if the left mouse button is double-clicked.

        Args:
            event (QMouseEvent): The mouse event object.
        """
        # Check if the annotation type is set and the left mouse button is double-clicked
        if self.annotation_type != "None" and event.button() == Qt.LeftButton:
            # Show input dialog to add a new label
            new_label, ok = QInputDialog.getText(self, "Add New Label", "Enter a new label:")
            # Check if the user entered a label and clicked OK
            if ok and new_label.strip():
                # Add the new label
                self.add_label(new_label)
            # Call the parent class's mousePressEvent to handle other events
            super().mousePressEvent(event)

    def add_label(self, new_label):
        """
        Adds a new label to the list view.

        Args:
            new_label (str): The label to add.
        """
        # Check if the label already exists
        if new_label not in self.label_list:
            # Add the new label to the list
            self.label_list.append(new_label)
            # Update the model
            self.model.setStringList(self.label_list)
            # Emit signal to update the list
            self.update_label_list_slot_transmitter.emit(self.label_list)
        else:
            # Show a warning message if the label already exists
            QMessageBox.warning(self, "Warning", "This label already exists.")

    def remove_label(self, label):
        """
        Removes a label from the list view.

        Args:
            label (str): The label to remove.
        """
        # Check if the label exists in the list
        if label in self.label_list:
            # Remove the label from the list
            self.label_list.remove(label)
            # Update the model
            self.model.setStringList(self.label_list)

    def contextMenuEvent(self, event):
        """
        Handles the context menu event, providing an option to edit the selected item.

        Args:
            event (QContextMenuEvent): The context menu event object.
        """
        # Get the index at the mouse position
        index = self.indexAt(event.pos())
        # Check if the index is valid
        if index.isValid():
            # Create a context menu
            menu = QMenu(self)
            # Create an action to edit the item
            edit_action = QAction("Edit", self)
            # Connect the action to the edit_label method
            edit_action.triggered.connect(lambda: self.edit_label(index))
            # Add the action to the menu
            menu.addAction(edit_action)
            # Show the context menu at the mouse position
            menu.exec_(event.globalPos())

    def edit_label(self, index):
        """
        Triggers inline editing for the selected item.

        Args:
            index (QModelIndex): The index of the item to be edited.
        """
        # Start editing the item at the specified index
        self.edit(index)

    def on_data_changed(self, topLeft, bottomRight, roles):
        """
        Slot that is triggered when the data in the model is changed.

        Args:
            topLeft (QModelIndex): The top-left index of the changed data.
            bottomRight (QModelIndex): The bottom-right index of the changed data.
            roles (list): The roles that have changed.
        """
        # Get the updated label list
        self.label_list = self.model.stringList()
        # Emit signal to update the list
        self.update_label_list_slot_transmitter.emit(self.label_list)


class CustomObjectListWidget(QtWidgets.QListView):
    """
    A custom QListView widget for displaying and managing a list of labels.
    Allows adding new labels by double-clicking and supports updating the list
    based on an annotation type.

    Attributes:
        model (QStringListModel): The data model for storing label names.
        label_list (list): A list to store label names displayed in the list view.
        annotation_type (str): The type of annotation currently being handled.
    """

    object_selection_notification_slot = pyqtSignal(int)  # selected object id (-1 = cleared)

    def __init__(self, parent=None):
        """
        Initializes the CustomLabelWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        # Initialize the model and label list
        self.model = QStringListModel()
        # label list is empty
        self.label_list = []  # list of labels Updated by main.py
        self.category_id = []  # list of category id
        self.object_id = []
        self.object = dict()
        self.set_model()
        # handel clicked event
        self.clicked.connect(self.on_item_clicked)
        self.set_label_list(self.label_list)

    def set_model(self):
        """
        Sets the data model for the list view and enables updates.
        """
        # set the model and enable updates
        self.setModel(self.model)
        self.setUpdatesEnabled(True)
        # # Set the edit triggers to NoEditTriggers
        self.setEditTriggers(QtWidgets.QListView.NoEditTriggers)

    def set_shapes(self, shapes: list):
        """Rebuild the object list to reflect the current document shapes.

        The canvas emits its full shape list on every change ([] = cleared), so
        the list is a plain projection of that — no per-item add/remove/update
        protocol.
        """
        self.object = {shape.id: shape.category_id for shape in shapes}
        self.set_label_list(
            category_id=[shape.category_id for shape in shapes],
            object_id=[shape.id for shape in shapes],
        )

    def set_label_list(self, category_id: list | None = None, object_id: list | None = None):
        """
        Updates the list view with a new list of labels.

        Args:
            label_list (list, optional): A list of label names to display. Defaults to an empty list.
        """
        # Clear the model before updating
        self.clear_list()
        # Update the label list and model
        self.category_id = category_id if category_id is not None else []
        self.object_id = object_id if object_id is not None else []
        logger.debug(f"Category ID: {category_id}")
        logger.debug(f"Object ID: {object_id}")
        object_list = [
            f"{self.label_list[id]} ({self.object_id[idx]})"
            for idx, id in enumerate(self.category_id)
        ]
        # update the model
        self.model.setStringList(object_list)

    def clear_list(self):
        """
        Clears all items from the list view.
        """
        # Clear the list and update the model
        self.object_id.clear()
        self.category_id.clear()
        self.object.clear()
        self.model.setStringList([])

    def refresh_list(self, label_list: list):
        """
        Refresh the list view
        """
        self.label_list = label_list
        object_list = [
            f"{self.label_list[id]} ({self.object_id[idx]})"
            for idx, id in enumerate(self.category_id)
        ]
        # object_list = [f"{self.label_list[id]}_{id}" for id in self.category_id]
        self.model.setStringList(object_list)

    def on_item_clicked(self, index):
        """
        Emits the signal with the currently selected item's text.

        Args:
            index (QModelIndex): The index of the current item.
        """
        # Emit the signal with the selected item's text
        # print(f"Index: {index.row()}")
        # print(f"Item: {self.model.data(index, Qt.DisplayRole)}")
        id = self.object_id[index.row()]
        self.object_selection_notification_slot.emit(id)

    def mousePressEvent(self, event) -> None:
        """
        Handles mouse press events on the list view. Toggles the checkbox state of
        the item under the mouse cursor.
        """
        index = self.indexAt(event.pos())
        if not index.isValid():
            # Clear the selection if the click is outside items
            self.clearSelection()
            logger.debug("Clearing selection")
            self.object_selection_notification_slot.emit(-1)
        # Call the parent class's mousePressEvent to handle normal clicks
        super().mousePressEvent(event)

    # def contextMenuEvent(self, event):
    #     """
    #     Handles the context menu event, providing an option to edit the selected item.

    #     Args:
    #         event (QContextMenuEvent): The context menu event object.
    #     """
    #     # Get the index at the mouse position
    #     index = self.indexAt(event.pos())
    #     # Check if the index is valid
    #     if index.isValid():
    #         # Create a context menu
    #         menu = QMenu(self)
    #         # Create an action to edit the item
    #         edit_action = QAction('Edit', self)
    #         # Connect the action to the edit_label method
    #         edit_action.triggered.connect(lambda: self.edit_label_at_index(index))
    #         # Add the action to the menu
    #         menu.addAction(edit_action)
    #         # Show the context menu at the mouse position
    #         menu.exec_(event.globalPos())

    # def edit_label_at_index(self, index):
    #     """
    #     Triggers inline editing for the selected item.

    #     Args:
    #         index (QModelIndex): The index of the item to be edited.
    #     """
    #     # Start editing the item at the specified index
    #     self.edit(index)

    # @pyqtSlot(QModelIndex, QModelIndex)
    # def handle_data_changed(self, top_left: QModelIndex, bottom_right: QModelIndex):
    #     """
    #     Slot to handle data changes in the list view.

    #     Args:
    #         top_left (QModelIndex): The top-left index of the changed data.
    #         bottom_right (QModelIndex): The bottom-right index of the changed data.
    #     """
    #     row = top_left.row()
    #     # get index of the item and old data

    #     new_data = self.model.data(top_left, Qt.EditRole)
    #     print(f"Item at row {row} was changed to '{new_data}'")
    #     # Optionally, you can update your data model or UI here
