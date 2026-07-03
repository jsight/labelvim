import logging
import os
import sys
from enum import Enum

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog

from labelvim.models.document import ImageMeta
from labelvim.services.config_service import ConfigService
from labelvim.services.image_directory import ImageDirectoryService
from labelvim.services.persistence import AnnotationPersistenceService
from labelvim.utils.annotation_manager import AnnotationManager
from labelvim.utils.config import (
    ANNOTATION_MODE,
    ANNOTATION_TYPE,
)
from labelvim.utils.label_list_reader import label_list_reader
from labelvim.utils.utils import get_image_list, return_mattching
from labelvim.widgets.export_file import ExportFileDialog
from labelvim.widgets.flash import FlashOverlay
from labelvim.widgets.task_selection import TaskSelectionDialog
from layout import Ui_MainWindow

logger = logging.getLogger(__name__)


class Mode(Enum):
    NORMAL = 1
    EDIT = 2


class ModalState:
    def __init__(self):
        self.state = Mode.NORMAL


class LabelVim(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.installEventFilter(self)
        self._flash_overlay = None
        # Qt-free model of the image directory: image list, annotated stems,
        # current index, deletion. LabelVim drives the UI from it.
        self.dir_service = ImageDirectoryService()
        # Saving (annotation JSON, mask export, source-image move) lives here.
        self.persistence = AnnotationPersistenceService()
        # Per-save-directory config.yaml (annotation type + mask toggles).
        self.config = ConfigService()
        self.json_data = {}
        self.annotation_mode = ANNOTATION_MODE.NONE
        self.annotation_type = ANNOTATION_TYPE.NONE
        self.label_file_name = "label.yaml"
        self.save_mask = False
        self.include_img = False

        # btn action
        self.OpenDirBtn.clicked.connect(self.__load_directory)
        self.SaveDirBtn.clicked.connect(self.__save_directory)
        self.DeleteFileBtn.clicked.connect(self.__delete_file)
        self.NextBtn.clicked.connect(self.__next)
        self.PreviousBtn.clicked.connect(self.__previous)
        self.CreateObjectBtn.clicked.connect(self.__create_object)
        self.EditObjectBtn.clicked.connect(self.__edit_object)
        self.DeleteAnnotationBtn.clicked.connect(self.__delete_annotation)
        self.ClearAnnotationBtn.clicked.connect(self.__clear_annotation)
        self.SaveBtn.clicked.connect(self.__save)
        self.ZoomInBtn.clicked.connect(self.__zoom_in)
        self.ZoomOutBtn.clicked.connect(self.__zoom_out)
        self.ZoomFitBtn.clicked.connect(self.__zoom_fit)
        self.actionQuit.triggered.connect(self.exit_app)

        self.actionOpen.triggered.connect(self.__load_directory)
        self.actionSave_Folder.triggered.connect(self.__save_directory)
        self.actionDelete_File.triggered.connect(self.__delete_file)
        self.actionNext.triggered.connect(self.__next)
        self.actionPrevious.triggered.connect(self.__previous)
        self.actionSave.triggered.connect(self.__save)
        self.actionSave_Mask.triggered.connect(self.__save_mask_flag_set)
        self.actionSave_Mask_include_img.triggered.connect(self.__save_mask_include_img_flag_set)

        self.actionZoom_In.triggered.connect(self.__zoom_in)
        self.actionZoom_Out.triggered.connect(self.__zoom_out)
        self.actionFit_Windows.triggered.connect(self.__zoom_fit)
        self.actionExport.triggered.connect(self.__handle_export)
        # self.actionAnnotation_Type.triggered.connect(self.show_task_selection_dialog)

        self.show()
        self.__disable_btn_at_start()
        # self.show_task_selection_dialog()

        # self.LabelWidget.update_annotation_type(self.annotation_type)

        # Connect signals and slots
        self.FileListWidget.notify_selected_item.connect(self.__load_image)
        self.canvas_widget.update_label_list_slot_receiver.emit(self.LabelWidget.label_list)
        self.canvas_widget.scale_factor_slot.connect(self.update_zoom_label)
        # Canvas shape changes -> object list rebuilds itself directly.
        self.canvas_widget.shapes_changed.connect(self.ObjectLabelListWidget.set_shapes)
        # Status bar: live cursor / selection / vertex / step summary from the canvas.
        self.statusInfoLabel = QtWidgets.QLabel("")
        self.statusbar.addWidget(self.statusInfoLabel, 1)
        self.canvas_widget.status_slot.connect(self.statusInfoLabel.setText)
        self.LabelWidget.update_label_list_slot_transmitter.connect(
            self.update_label_list_to_Display
        )
        # Object-list selection -> select that shape on the canvas (direct).
        self.ObjectLabelListWidget.object_selection_notification_slot.connect(
            self.canvas_widget.select_object
        )

        self.json_writer = None
        #
        self.annotation_manager = None
        self.label_list_reader = label_list_reader
        self.modal_state = ModalState()

    # --- directory state proxies (the ImageDirectoryService is the authority) ---

    @property
    def img_file_list(self):
        return self.dir_service.image_paths

    @property
    def img_list(self):
        return self.dir_service.stems

    @property
    def json_list(self):
        return self.dir_service.annotated_stems

    @property
    def load_dir(self):
        return self.dir_service.load_dir

    @load_dir.setter
    def load_dir(self, value):
        self.dir_service.load_dir = value

    @property
    def save_dir(self):
        return self.dir_service.save_dir

    @save_dir.setter
    def save_dir(self, value):
        self.dir_service.save_dir = value

    @property
    def current_index(self):
        return self.dir_service.current_index

    @current_index.setter
    def current_index(self, value):
        self.dir_service.current_index = value

    @property
    def save_mask(self):
        return self.persistence.save_mask

    @save_mask.setter
    def save_mask(self, value):
        self.persistence.save_mask = value

    @property
    def include_img(self):
        return self.persistence.include_img

    @include_img.setter
    def include_img(self, value):
        self.persistence.include_img = value

    def __set_annotation_buttons_enabled(self, enabled):
        for button in (
            self.SaveBtn,
            self.DeleteAnnotationBtn,
            self.EditObjectBtn,
            self.ClearAnnotationBtn,
            self.actionSave,
        ):
            button.setEnabled(enabled)

    def __load_annotation_for_current(self):
        """Load (or clear) the annotation for the currently selected image and
        toggle the annotation action buttons accordingly."""
        stem = self.dir_service.current_stem()
        if self.save_dir and self.dir_service.has_annotation(stem):
            self.annotation_manager = AnnotationManager(self.save_dir, stem + ".json")
            self.annotation_data = self.annotation_manager.annotation
            self.canvas_widget.annotation_data_slot_receiver.emit(
                self.annotation_data["annotations"]
            )
            self.__set_annotation_buttons_enabled(True)
        else:
            self.annotation_manager = None
            self.__set_annotation_buttons_enabled(False)

    def eventFilter(self, source, event):
        # if event.type() in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        if event.type() == QtCore.QEvent.KeyRelease:
            # print("received event type:", event.type())
            key = event.key()
            is_shift_pressed = event.modifiers() & QtCore.Qt.ShiftModifier
            logger.debug("%s %s", "is_shift_pressed:", is_shift_pressed)
            key_text = QtGui.QKeySequence(key).toString()
            # self.modeLabel.setText("Keys:" + key_text + "self.modal_state.state:" + str(self.modal_state.state))
            if key_text == "I" and self.modal_state.state == Mode.NORMAL:
                self.modal_state.state = Mode.EDIT
                self.modeLabel.setText("EDIT")
                self.canvas_widget.set_edit_mode(True)
            elif event.key() == QtCore.Qt.Key_Escape and self.modal_state.state == Mode.EDIT:
                # Esc first cancels an in-progress vertex edit; only if none is
                # active does it leave EDIT mode.
                if not self.canvas_widget.cancel_vertex_edit():
                    self.modal_state.state = Mode.NORMAL
                    self.modeLabel.setText("NORMAL")
                    self.canvas_widget.set_edit_mode(False)
            if key_text == "K" or event.key() == QtCore.Qt.Key_Up:
                self.canvas_widget.move_up(is_shift_pressed)
            elif key_text == "H" or event.key() == QtCore.Qt.Key_Left:
                self.canvas_widget.move_left(is_shift_pressed)
            elif key_text == "L" or event.key() == QtCore.Qt.Key_Right:
                self.canvas_widget.move_right(is_shift_pressed)
            elif key_text == "J" or event.key() == QtCore.Qt.Key_Down:
                self.canvas_widget.move_down(is_shift_pressed)
            elif key_text == "N" and self.modal_state.state == Mode.EDIT:
                # n / N: cycle the selected shape forward / backward.
                if is_shift_pressed:
                    self.canvas_widget.select_prev_shape()
                else:
                    self.canvas_widget.select_next_shape()
            elif key_text == "V" and self.modal_state.state == Mode.EDIT:
                # v: start editing the selected shape's vertices, or cycle vertex.
                self.canvas_widget.enter_or_cycle_vertex()
            elif key_text == "C":
                # Only start drawing if creation can actually proceed (otherwise
                # __create_object flashes why); never a silent no-op.
                if self.__create_object():
                    self.canvas_widget.kb_create_box()
            elif event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
                logger.debug("enter pressed")
                # Enter commits a vertex edit if one is active; otherwise it
                # completes an in-progress box.
                if not self.canvas_widget.commit_vertex_edit():
                    self.canvas_widget.kb_move_complete()
            elif key_text == "U" and not (event.modifiers() & QtCore.Qt.ControlModifier):
                # vim-style: u = undo, Ctrl+R = redo
                self.canvas_widget.undo()
            elif key_text == "R" and (event.modifiers() & QtCore.Qt.ControlModifier):
                self.canvas_widget.redo()

            # return True
        return False

    def show_task_selection_dialog(self):
        """
        Displays a custom dialog when the GUI starts, asking the user to choose
        between object detection or segmentation.
        """
        # if self.annotation_type == ANNOTATION_TYPE.NONE:
        dialog = TaskSelectionDialog(self)
        if dialog.exec_():
            annotation_type = dialog.selected_task()
            if annotation_type != ANNOTATION_TYPE.NONE:
                self.annotation_type = annotation_type
                self.LabelWidget.update_annotation_type(self.annotation_type)
                self.canvas_widget.update_annotation_type(self.annotation_type)

    def __load_directory(self):
        """
        Called when the OpenDirBtn is clicked. This is a
        private method that opens a file dialog to allow the user to select a directory.
        It then loads and processes image files from the chosen directory, updating the
        file list widget and enabling or disabling buttons based on the presence of images.
        """
        self.load_dir = QFileDialog.getExistingDirectory(self, "Select a Directory")
        self.__load_directory_data()

    def __load_directory_data(self):
        if self.load_dir:
            self.dir_service.load(self.load_dir)
            logger.debug(
                f"Total File in the selected directory {self.load_dir}: {len(self.img_file_list)}"
            )
            self.FileListWidget.update_list.emit(self.img_file_list)
            self.listCountLabel.setText(f"Loaded {len(self.img_list)} images")
            if self.img_file_list:
                self.__enable_btn_after_load()
            else:
                self.__disable_btn_at_start()

    def __load_image(self, file_name, index):
        """
        called when the user selects an image file from the list widget in FileListWidget.
        """
        self.current_index = index
        if self.current_index < 0:
            self.annotation_manager = None
            self.__disable_btn_at_start()
            self.canvas_widget.reset()
            return
        logger.debug(f"current index: {self.current_index}")
        logger.debug(f"file name: {file_name}")
        self.canvas_widget.load_image(file_name)
        self.__load_annotation_for_current()

    def __save_directory(self):
        """
        Opens a dialog to select a save directory, loads JSON files from the directory,
        updates the label list manager, and syncs the list with available image files.
        """
        self.save_dir = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if self.save_dir:
            self.config.open(self.save_dir)

            # Resolve the annotation type: use the stored one, or ask the user.
            stored = self.config.annotation_type_value()
            if stored is None or ANNOTATION_TYPE(stored) == ANNOTATION_TYPE.NONE:
                self.show_task_selection_dialog()  # sets self.annotation_type
            else:
                self.annotation_type = ANNOTATION_TYPE(stored)

            # Mask-export toggles come from config (default off).
            self.save_mask = self.config.save_mask()
            self.include_img = self.config.include_img()
            self.config.update(self.annotation_type.value, self.save_mask, self.include_img)
            self.__change_icon_save_mask()
            self.__change_icon_save_mask_include_img()

            self.LabelWidget.update_annotation_type(self.annotation_type)
            self.canvas_widget.update_annotation_type(self.annotation_type)
            logger.debug(f"Save Directory: {self.save_dir}")

            # Track which images already have a saved annotation JSON in this dir.
            json_paths = get_image_list(self.save_dir, extension=[".json"])
            json_stems = [os.path.splitext(os.path.basename(p))[0] for p in json_paths]
            self.dir_service.annotated_stems = set(return_mattching(json_stems, self.img_list))

            # Update the label list manager's path and load the label file if it exists
            self.label_list_reader.label_list_path = os.path.join(
                self.save_dir, self.label_file_name
            )
            logger.debug(f"Label List Path: {self.label_list_reader.label_list_path}")
            if os.path.exists(os.path.join(self.save_dir, self.label_file_name)):
                self.label_list_reader.read()
            else:
                self.label_list_reader.update(
                    []
                )  # Initialize with an empty list if the file doesn't exist
            # print(f"Label List: {self.label_list_reader.label_list}")
            self.update_label_list_to_Label_Widget(self.label_list_reader.label_list)
            self.update_label_list_to_Display(self.label_list_reader.label_list)

            self.current_index = self.FileListWidget.get_current_index()
            logger.debug(f"save dir Current Index: {self.current_index}")
            self.__load_annotation_for_current()

    def __delete_file(self):
        """
        Deletes the currently selected file from the list. Removes the file from
        the image file list and updates the JSON list if applicable.
        """
        # Get the index of the currently selected item
        deleted_file_index = self.FileListWidget.get_current_index()
        logger.debug("+==============================+")
        logger.debug(f"Deleted File Index: {deleted_file_index}")

        if deleted_file_index is not None and self.dir_service.is_valid_index(deleted_file_index):
            # remove() drops the image + its annotation record and returns the
            # on-disk JSON path to delete (if the image had a saved annotation).
            json_to_delete = self.dir_service.remove(deleted_file_index)
            if json_to_delete is not None and os.path.exists(json_to_delete):
                os.remove(json_to_delete)
            self.FileListWidget.remove_selected_item()

    def __save(self):
        """Persist the current annotation (JSON, optional mask, image move)."""
        stem = self.dir_service.current_stem()
        input_img_file = self.dir_service.current_path()
        if self.annotation_manager is None or stem is None or input_img_file is None:
            logger.debug("Nothing to save (no image / save directory).")
            return

        # Build the document from the canvas shapes + image metadata; its
        # to_dict() is the single on-disk serializer (stable, polygon-aware, and
        # guaranteed to round-trip a load->save cycle).
        document = self.canvas_widget.to_document()
        document.meta = ImageMeta(
            path=os.path.basename(input_img_file),
            data=self.annotation_manager.annotation.get("imageData"),
            height=self.canvas_widget.original_pixmap.height(),
            width=self.canvas_widget.original_pixmap.width(),
        )
        self.persistence.write_document(document, self.save_dir, stem)
        self.dir_service.mark_annotated(stem)

        # Relocate the finished image next to its annotation when the save dir
        # differs from the load dir (reload the file list to reflect the move).
        moved = self.persistence.move_into_save_dir(input_img_file, self.save_dir)
        if moved:
            self.__load_directory_data()

        if self.save_mask:
            mask_type = "bbox" if self.annotation_type == ANNOTATION_TYPE.BBOX else "polygon"
            self.persistence.write_mask(
                document,
                moved or input_img_file,
                self.save_dir,
                self.label_list_reader.label_list,
                mask_type,
            )

    def __next(self):
        """Move to the next image and load its annotation (if any)."""
        self.FileListWidget.next_index()
        self.current_index = self.FileListWidget.get_current_index()
        logger.debug("========Next Button Clicked======== index %s", self.current_index)
        self.__load_annotation_for_current()

    def __previous(self):
        """Move to the previous image and load its annotation (if any)."""
        self.FileListWidget.previous_index()
        self.current_index = self.FileListWidget.get_current_index()
        logger.debug("========Previous Button Clicked======== index %s", self.current_index)
        self.__load_annotation_for_current()

    def __create_object(self):
        """Set up the environment for creating a new annotation.

        Returns True if creation can proceed; otherwise flashes the reason and
        returns False, so the `C` key never silently does nothing.
        """
        if not self.save_dir:
            self.flash("Select a save directory first", level="warning")
            self.SaveBtn.setEnabled(False)
            self.DeleteAnnotationBtn.setEnabled(False)
            self.EditObjectBtn.setEnabled(False)
            self.ClearAnnotationBtn.setEnabled(False)
            self.actionSave.setEnabled(False)
            return False

        if self.canvas_widget.original_pixmap is None:
            self.flash("Load an image first", level="warning")
            return False

        logger.debug("Create Object")
        self.annotation_mode = ANNOTATION_MODE.CREATE
        logger.debug(f"Annotation Mode: {self.annotation_mode}")
        self.canvas_widget.btn_action_slot.emit(self.annotation_mode)

        # Initialize the annotation manager if not already initialized
        if self.annotation_manager is None:
            current_image = self.img_list[self.current_index]
            self.annotation_manager = AnnotationManager(self.save_dir, current_image + ".json")
            self.annotation_manager.update_basic_info(
                os.path.basename(self.img_file_list[self.current_index]),
                self.canvas_widget.original_pixmap.height(),
                self.canvas_widget.original_pixmap.width(),
            )
            self.annotation_data = self.annotation_manager.annotation

        # Enable the annotation action buttons
        self.SaveBtn.setEnabled(True)
        self.DeleteAnnotationBtn.setEnabled(True)
        self.EditObjectBtn.setEnabled(True)
        self.ClearAnnotationBtn.setEnabled(True)
        self.actionSave.setEnabled(True)
        return True

    def __edit_object(self):
        logger.debug("Edit Object")
        self.annotation_mode = ANNOTATION_MODE.EDIT
        logger.debug(f"Annotation Mode: {self.annotation_mode}")
        self.canvas_widget.btn_action_slot.emit(self.annotation_mode)

    def __delete_annotation(self):
        logger.debug("Duplicate Annotation")
        self.annotation_mode = ANNOTATION_MODE.DELETE
        self.canvas_widget.btn_action_slot.emit(self.annotation_mode)
        logger.debug(f"Annotation Mode: {self.annotation_mode}")

    def __clear_annotation(self):
        logger.debug("Clear Annotation")
        self.annotation_mode = ANNOTATION_MODE.CLEAR
        logger.debug(f"Annotation Mode: {self.annotation_mode}")
        self.canvas_widget.btn_action_slot.emit(self.annotation_mode)

    def __zoom_in(self):
        self.canvas_widget.zoom_in()

    def __zoom_out(self):
        self.canvas_widget.zoom_out()

    def __zoom_fit(self):
        self.canvas_widget.fit_to_window()

    def update_zoom_label(self, scale_factor):
        self.ZoomLabel.setText(f"{scale_factor * 100:.2f}%")

    def __disable_btn_at_start(self):
        self.DeleteFileBtn.setEnabled(False)
        self.NextBtn.setEnabled(False)
        self.PreviousBtn.setEnabled(False)
        self.CreateObjectBtn.setEnabled(False)
        self.EditObjectBtn.setEnabled(False)
        self.DeleteAnnotationBtn.setEnabled(False)
        self.ClearAnnotationBtn.setEnabled(False)
        self.SaveBtn.setEnabled(False)
        self.ZoomInBtn.setEnabled(False)
        self.ZoomOutBtn.setEnabled(False)
        self.ZoomFitBtn.setEnabled(False)
        # action menu disable
        self.actionNext.setEnabled(False)
        self.actionPrevious.setEnabled(False)
        self.actionDelete_File.setEnabled(False)
        self.actionSave.setEnabled(False)
        self.actionZoom_In.setEnabled(False)
        self.actionZoom_Out.setEnabled(False)
        self.actionFit_Windows.setEnabled(False)

    def __enable_btn_after_load(self):
        """
        enable the buttons after loading the directory and getting the file list
        """
        self.NextBtn.setEnabled(True)
        self.PreviousBtn.setEnabled(True)
        self.CreateObjectBtn.setEnabled(True)
        self.DeleteFileBtn.setEnabled(True)
        self.ZoomInBtn.setEnabled(True)
        self.ZoomOutBtn.setEnabled(True)
        self.ZoomFitBtn.setEnabled(True)
        # action menu enable
        self.actionNext.setEnabled(True)
        self.actionPrevious.setEnabled(True)
        self.actionDelete_File.setEnabled(True)
        self.actionZoom_In.setEnabled(True)
        self.actionZoom_Out.setEnabled(True)
        self.actionFit_Windows.setEnabled(True)
        # self.actionSave.setEnabled(True)

    def flash(self, message, level="info"):
        """Show a non-blocking transient message (keeps the keyboard flow going).

        Use for non-blocking info/warnings (reserve modal dialogs for genuine
        destructive confirmations).
        """
        if self._flash_overlay is None:
            self._flash_overlay = FlashOverlay(self)
        self._flash_overlay.flash(message, level)

    ## Signal and Slot
    def update_label_list_to_Display(self, label_list):
        # print(f"update_label_list: {label_list}")
        self.label_list_reader.update(label_list)
        self.canvas_widget.update_label_list_slot_receiver.emit(label_list)
        self.ObjectLabelListWidget.refresh_list(
            label_list
        )  # Update the label list in the object list widget
        # self.ObjectLabelListWidget.label_list = label_list

    def update_label_list_to_Label_Widget(self, label_list):
        # print(f"update_label_list: {label_list}")
        self.label_list_reader.update(label_list)
        self.LabelWidget.update_label_list_slot_receiver.emit(label_list)
        self.ObjectLabelListWidget.refresh_list(
            label_list
        )  # Update the label list in the object list widget
        # self.ObjectLabelListWidget.label_list = label_list # Update the label list in the object list widget

    def __save_mask_flag_set(self):
        self.save_mask = not self.save_mask
        self.config.update(self.annotation_type.value, self.save_mask, self.include_img)
        self.__change_icon_save_mask()

    def __save_mask_include_img_flag_set(self):
        self.include_img = not self.include_img
        self.config.update(self.annotation_type.value, self.save_mask, self.include_img)
        self.__change_icon_save_mask_include_img()

    def __change_icon_save_mask(self):
        if self.save_mask:
            self.actionSave_Mask.setIconVisibleInMenu(True)
        else:
            self.actionSave_Mask.setIconVisibleInMenu(False)

    def __change_icon_save_mask_include_img(self):
        if self.include_img:
            self.actionSave_Mask_include_img.setIconVisibleInMenu(True)
        else:
            self.actionSave_Mask_include_img.setIconVisibleInMenu(False)

    def exit_app(self):
        self.close()

    def __handle_export(self):
        if self.save_dir:
            dialog = ExportFileDialog(save_dir=self.save_dir, data_dir=self.load_dir)
            dialog.show()
            if dialog.exec_():
                logger.debug("%s %s", "Task Type:", dialog.task_type)
                logger.debug("%s %s", "Export Type:", dialog.export_type)
                logger.debug("%s %s", "Include Mask:", dialog.include_mask)
        else:
            self.flash("Select a save directory first", level="warning")
        # dialog = ExportFileDialog()
        # dialog.show()
        # if dialog.exec_():
        #     print('Task Type:', dialog.task_type)
        #     print('Export Type:', dialog.export_type)
        #     print('Include Mask:', dialog.include_mask)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LABELVIM_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QtWidgets.QApplication(sys.argv)
    window = LabelVim()
    window.show()
    sys.exit(app.exec_())
