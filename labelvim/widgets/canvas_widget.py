import copy
import logging
from enum import Enum

from PyQt5 import QtCore
from PyQt5.QtCore import *
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import *
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QLabel

from labelvim.models.document import (
    AnnotationDocument,
    annotation_from_shape,
    shape_from_annotation,
)
from labelvim.models.model import Point, Polygon, Rectangle
from labelvim.utils import coords
from labelvim.utils.config import ANNOTATION_MODE, ANNOTATION_TYPE
from labelvim.widgets.label_picker import LabelPicker

logger = logging.getLogger(__name__)


class CanvasWidget(QLabel):
    """A custom QLabel widget to display images and draw rectangles on them."""

    update_label_list_slot_receiver = pyqtSignal(list)  # push a new label list into the canvas
    annotation_data_slot_receiver = pyqtSignal(list)  # load annotations (list of COCO-like dicts)
    shapes_changed = pyqtSignal(list)  # current shapes -> object list ([] = cleared)
    btn_action_slot = pyqtSignal(Enum)  # annotation-mode change
    scale_factor_slot = pyqtSignal(float)  # scale factor -> zoom label
    status_slot = pyqtSignal(str)  # status-bar summary line

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.size_geometry = QRect(70, 0, 1310, 790)
        # self.setGeometry(self.size_geometry)
        self.setFrameShape(QLabel.WinPanel)
        self.setFrameShadow(QLabel.Raised)
        self.setLineWidth(9)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setFocusPolicy(Qt.StrongFocus)

        # The single source of truth for this image's annotations: shapes (via
        # the undo tree) and the current selection both live on the document.
        self.document = AnnotationDocument()

        self.start_point = None
        self.end_point = None
        self.polygon_points = []  # transient: in-progress polygon vertices
        self.polygon_move_point = None

        self.original_pixmap = None
        self.current_pixmap = None
        self.brush_color = QColor(0, 0, 255, 50)
        self.polygon_brush_color = QColor(255, 0, 0, 50)
        self.pen_color = QColor(0, 255, 255)
        self.title_pen_color = QColor(0, 255, 255)
        self.selected_rectangle_brush_color = QColor(255, 0, 255, 50)
        self.selected_polygon_brush_color = QColor(255, 255, 0, 50)
        self.selected_object_subset = None
        self.line_segment = None
        self.moving_object = False
        self.last_mouse_position = QPoint()  # Store the last mouse position
        # self.pixmap = None  # To store the loaded pixmap
        self.label_list = []
        self.update_label_list_slot_receiver.connect(self.update_label_list)
        self.annotation_data_slot_receiver.connect(self.update_annotation_from_json)
        self.btn_action_slot.connect(self.set_annotation_mode)
        self.scale_factor = 1.0
        # self.__reset_scale_factor()
        self.annotation_mode = ANNOTATION_MODE.NONE
        self.annotation_type = ANNOTATION_TYPE.NONE
        self.scale_factor_w, self.scale_factor_h = 1, 1
        self.zoom_in_scale_factor = 1.05  # 1.25
        self.zoom_out_scale_factor = 0.95  # 0.8
        self.max_scale_factor = 6
        self.point_click_radious = 5  # The radious of the point click
        self.in_edit_mode = False
        self.cursor_pos = None
        self._label_picker = None  # lazily-created keyboard-first label picker
        self._pending_shape = None  # geometry awaiting a label: ("bbox"|"poly", geom)
        self._editing_index = None  # index of the shape being vertex-edited
        self._editing_shape = None  # working copy edited live; committed on Enter
        self._drag_index = None  # index of the shape being mouse-dragged
        self._drag_original = None  # its pre-drag copy; the drag commits one undo step

    # --- views onto the document's state (the single source of truth) ---

    @property
    def undo_tree(self):
        """The document's undo tree; `.shapes` is the authoritative shape list."""
        return self.document.undo

    @property
    def selected_object(self):
        """Id of the selected shape (None if nothing is selected)."""
        return self.document.selection.shape_id

    @selected_object.setter
    def selected_object(self, value):
        self.document.selection.shape_id = value

    @property
    def selected_vertex(self):
        """Index of the active vertex within the selected shape."""
        return self.document.selection.vertex_index

    @selected_vertex.setter
    def selected_vertex(self, value):
        self.document.selection.vertex_index = value

    def set_edit_mode(self, edit_mode):
        self.in_edit_mode = edit_mode
        logger.debug("%s %s", "in edit mode: ", self.in_edit_mode)
        if edit_mode:
            self.cursor_pos = (0.50, 0.50)
        else:
            self.cursor_pos = None
            self.start_point = None
            self.end_point = None
        self.update()
        self._emit_status()

    def enforce_cursor_min_max(self):
        if self.cursor_pos[0] < 0:
            self.cursor_pos = (0, self.cursor_pos[1])
        if self.cursor_pos[0] > 1:
            self.cursor_pos = (1, self.cursor_pos[1])
        if self.cursor_pos[1] < 0:
            self.cursor_pos = (self.cursor_pos[0], 0)
        if self.cursor_pos[1] > 1:
            self.cursor_pos = (self.cursor_pos[0], 1)

    def _vertex_nudge_step(self, larger_movement):
        return 5 if larger_movement else 1

    def move_up(self, larger_movement):
        if self.is_editing_vertex():
            self._nudge_editing_vertex(0, -self._vertex_nudge_step(larger_movement))
            return
        if not self.cursor_pos:
            return
        step_size = 0.05 if larger_movement else 0.01
        self.cursor_pos = (self.cursor_pos[0], self.cursor_pos[1] - step_size)
        self.enforce_cursor_min_max()
        self.kb_create_mode_move()

    def move_right(self, larger_movement):
        if self.is_editing_vertex():
            self._nudge_editing_vertex(self._vertex_nudge_step(larger_movement), 0)
            return
        if not self.cursor_pos:
            return
        step_size = 0.05 if larger_movement else 0.01
        self.cursor_pos = (self.cursor_pos[0] + step_size, self.cursor_pos[1])
        self.enforce_cursor_min_max()
        self.kb_create_mode_move()

    def move_down(self, larger_movement):
        if self.is_editing_vertex():
            self._nudge_editing_vertex(0, self._vertex_nudge_step(larger_movement))
            return
        if not self.cursor_pos:
            return
        step_size = 0.05 if larger_movement else 0.01
        self.cursor_pos = (self.cursor_pos[0], self.cursor_pos[1] + step_size)
        self.enforce_cursor_min_max()
        self.kb_create_mode_move()

    def move_left(self, larger_movement):
        if self.is_editing_vertex():
            self._nudge_editing_vertex(-self._vertex_nudge_step(larger_movement), 0)
            return
        if not self.cursor_pos:
            return
        step_size = 0.05 if larger_movement else 0.01
        self.cursor_pos = (self.cursor_pos[0] - step_size, self.cursor_pos[1])
        self.enforce_cursor_min_max()
        self.kb_create_mode_move()

    def update_annotation_type(self, annotation_type):
        logger.debug(f"Annotation Type: {annotation_type}")
        logger.debug(f"OLD Annotation Type: {self.annotation_type}")
        self.annotation_type = annotation_type
        logger.debug(f"UPDATED Annotation Type: {self.annotation_type}")

    def load_image(self, file_name):
        self.clear_annotation()
        logger.debug("Setting selected_object to none")
        self.selected_object = None
        # emit signal to clear the object list
        self.shapes_changed.emit([])
        self.annotation_mode = ANNOTATION_MODE.NONE
        self.scale_factor = 1.0
        # print(f"File Name: {file_name}")
        self.original_pixmap = QPixmap(file_name)
        if self.original_pixmap.isNull():
            logger.debug(f"Failed to load image: {file_name}")
            return
        self.current_pixmap = self.original_pixmap.copy()
        # Use the parent scroll area's viewport size for initial scaling
        parent_scroll = self.parentWidget()
        if isinstance(parent_scroll, QScrollArea):
            available_size = parent_scroll.viewport().size()
        else:
            available_size = self.size()
        self.scale_to_fit(available_size)
        self.update()
        self._emit_status()

    def scale_to_fit(self, available_size):
        if self.original_pixmap:
            # Scale to fit the available size while maintaining aspect ratio
            self.current_pixmap = self.original_pixmap.scaled(
                available_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.scale_factor = self.current_pixmap.width() / self.original_pixmap.width()
            self.max_scale_factor = 4 * self.scale_factor
            self.min_scale_factor = 0.25 * self.scale_factor
            self.scale_factor_slot.emit(self.scale_factor)
            self.setFixedSize(self.current_pixmap.size())
            self.update()

    def scale_image(self, factor):
        if self.original_pixmap:
            new_scale_factor = self.scale_factor * factor
            if new_scale_factor < self.min_scale_factor or new_scale_factor > self.max_scale_factor:
                return
            self.scale_factor = new_scale_factor
            self.scale_factor_slot.emit(self.scale_factor)
            new_size = self.scale_factor * self.original_pixmap.size()
            self.current_pixmap = self.original_pixmap.scaled(
                new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setFixedSize(self.current_pixmap.size())
            self.update()

    def adjust_scroll_bars(self):
        pass

    def reset(self):
        self.clear_annotation()
        self.annotation_mode = ANNOTATION_MODE.NONE
        self.scale_factor = 1.0
        self.current_pixmap = None
        self.original_pixmap = None
        self.update()

    def clear_annotation(self):
        """Clear the displayed image from the widget."""
        self.start_point = None
        self.end_point = None
        self.polygon_points.clear()
        self.polygon_move_point = None
        self.undo_tree.clear()
        # self.rectangles.clear()
        self.update()

    def zoom_in(self):
        self.scale_image(self.zoom_in_scale_factor)
        self.update()

    def zoom_out(self):
        self.scale_image(self.zoom_out_scale_factor)
        self.update()

    def fit_to_window(self):
        if self.original_pixmap:
            parent_scroll = self.parentWidget().parentWidget()
            if isinstance(parent_scroll, QScrollArea):
                available_size = parent_scroll.viewport().size()
            else:
                available_size = self.size()
            self.current_pixmap = self.original_pixmap.scaled(
                available_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.scale_factor = self.current_pixmap.width() / self.original_pixmap.width()
            self.scale_factor_slot.emit(self.scale_factor)
            self.setFixedSize(self.current_pixmap.size())
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def kb_create_box(self):
        if not self.original_pixmap:
            return
        # Creation works from any mode: ensure a cursor exists (it normally only
        # appears in edit mode) so `C` from NORMAL starts drawing at the center
        # instead of silently doing nothing.
        if not self.cursor_pos:
            self.cursor_pos = (0.50, 0.50)
        logger.debug("%s %s", "self.cursor_pos:", self.cursor_pos)
        self.set_annotation_mode(ANNOTATION_MODE.CREATE)
        # start_point = self.map_to_original_image(self.cursor_pos)
        start_point = QPoint(
            int(self.cursor_pos[0] * self.original_pixmap.width()),
            int(self.cursor_pos[1] * self.original_pixmap.height()),
        )
        if start_point.x() == 0:
            start_point.setX(1)
        if start_point.y() == 0:
            start_point.setY(1)

        logger.debug("%s %s", "Created start_point: ", start_point)
        logger.debug("%s %s", "Hmm:", start_point.x)
        if start_point:
            self.start_point = start_point
            logger.debug("%s %s", "start_point:", self.start_point)

    def kb_create_mode_move(self):
        if not self.original_pixmap:
            return
        if not self.cursor_pos:
            return

        logger.debug("=====")
        logger.debug("%s %s", "kb_create_mode_move:", self.cursor_pos)
        logger.debug("%s %s", "Annotation type:", self.annotation_type)
        logger.debug("%s %s", "start_point:", self.start_point)
        logger.debug("%s %s", "self.annotation_mode:", self.annotation_mode)
        logger.debug("=====")
        if self.annotation_type == ANNOTATION_TYPE.BBOX:
            if self.start_point and self.annotation_mode == ANNOTATION_MODE.CREATE:
                end_point = QPoint(
                    int(self.cursor_pos[0] * self.original_pixmap.width()),
                    int(self.cursor_pos[1] * self.original_pixmap.height()),
                )
                logger.debug("%s %s", "end_point:", end_point)
                if end_point:
                    self.end_point = end_point
        self.update()
        self._emit_status()

    def kb_move_complete(self):
        if not self.original_pixmap:
            return
        if self.annotation_type == ANNOTATION_TYPE.BBOX:
            if self.start_point and self.annotation_mode == ANNOTATION_MODE.CREATE:
                end_point = QPoint(
                    int(self.cursor_pos[0] * self.original_pixmap.width()),
                    int(self.cursor_pos[1] * self.original_pixmap.height()),
                )
                logger.debug("%s %s", "Should complete from start_point: ", self.start_point)
                if end_point:
                    self.end_point = end_point
                    rect = QRect(self.start_point, self.end_point).normalized()
                    if self.distance(self.start_point, self.end_point) > 20:
                        self.update_rectangle(bbox=rect)
        self.update()

    ## Start of mouse events
    def mousePressEvent(self, event):
        if self.original_pixmap:
            click_pos = event.pos()
            if event.button() == Qt.LeftButton:
                if self.annotation_type == ANNOTATION_TYPE.BBOX:
                    if self.annotation_mode == ANNOTATION_MODE.CREATE:
                        start_point = self.map_to_original_image(click_pos)
                        if start_point:
                            self.start_point = start_point
                    if self.annotation_mode == ANNOTATION_MODE.EDIT:
                        logger.debug(
                            "%s %s",
                            "Resetting selected object, but was previously:",
                            self.selected_object,
                        )
                        self.selected_object, self.selected_vertex = self.find_object_to_edit(
                            click_pos
                        )
                        logger.debug(
                            "%s %s", "Resetting selected object, new value:", self.selected_object
                        )
                        logger.debug(
                            f"Selected Rectangle: {self.selected_object}, Selected Vertex: {self.selected_vertex}"
                        )
                        if self.selected_vertex is None and self.selected_object is None:
                            # Start moving the rectangle if no vertex is selected
                            self.moving_object = True
                            self.last_mouse_position = self.map_to_original_image(click_pos)
                            if self.last_mouse_position is None:
                                self.moving_object = False
                            else:
                                self.select_rectangle(self.last_mouse_position)
                            logger.debug(f"Selected Rectangle: {self.selected_object}")
                        # Snapshot the shape so the whole drag is one undo step.
                        if self.selected_object is not None:
                            self._begin_drag(self.selected_object)
                elif self.annotation_type == ANNOTATION_TYPE.POLYGON:
                    new_map = self.map_to_original_image(click_pos)
                    self.polygon_move_point = None
                    if self.annotation_mode == ANNOTATION_MODE.CREATE:
                        if len(self.polygon_points) == 0:
                            # print("First Point")
                            self.polygon_points.append(new_map)
                        elif len(self.polygon_points) == 1:
                            if self.distance(self.polygon_points[0], new_map) > 10:
                                # print("Second Point")
                                self.polygon_points.append(new_map)
                        elif len(self.polygon_points) >= 2:
                            # print("More than 2 points")
                            if self.distance(self.polygon_points[0], new_map) < 10:
                                # print("Last Point")
                                self.update_rectangle(poly=self.polygon_points)
                                self.polygon_points.clear()
                            else:
                                # print("More than 2 points")
                                self.polygon_points.append(new_map)
                    elif self.annotation_mode == ANNOTATION_MODE.EDIT:
                        logger.debug(
                            "%s %s",
                            "Resetting selected object in line 372ish:",
                            self.selected_object,
                        )
                        (
                            self.selected_object,
                            self.selected_object_subset,
                            self.selected_vertex,
                            self.line_segment,
                        ) = self.find_polygon_to_edit(new_map)
                        logger.debug(
                            f"Selected Rectangle: {self.selected_object}, Selected Rectangle subset: {self.selected_object_subset} Selected Vertex: {self.selected_vertex}, Line Segment: {self.line_segment}"
                        )

                        if (
                            self.selected_vertex is None
                            and self.selected_object is None
                            and self.line_segment is None
                        ):
                            logger.debug("Moving Polygon")
                            logger.debug(f"Selected Rectangle: {self.selected_object}")
                            self.moving_object = True
                            self.last_mouse_position = new_map
                            logger.debug(f"Last Mouse Position: {self.last_mouse_position}")
                            if self.last_mouse_position is None:
                                self.moving_object = False
                            else:
                                self.select_polygon(new_map)
                            logger.debug(f"Selected Rectangle: {self.selected_object}")
                        # self.selected_object = self.select_polygon(new_map)
                        # if self.selected_object is not None:
                        #     self.polygon_move_point = new_map
        self.update()

    def mouseMoveEvent(self, event):
        if self.original_pixmap:
            click_pos = event.pos()
            if self.annotation_type == ANNOTATION_TYPE.BBOX:
                if self.start_point and self.annotation_mode == ANNOTATION_MODE.CREATE:
                    end_point = self.map_to_original_image(click_pos)
                    if end_point:
                        self.end_point = end_point

                elif (
                    self.selected_vertex is not None
                    and self.annotation_mode == ANNOTATION_MODE.EDIT
                ):
                    # Resize the selected rectangle
                    new_pos = self.map_to_original_image(click_pos)
                    if new_pos:
                        self.move_vertex(self.selected_vertex, new_pos)
                elif self.moving_object and self.annotation_mode == ANNOTATION_MODE.EDIT:
                    # Move the selected rectangle
                    new_pos = self.map_to_original_image(click_pos)  # origional image dimension
                    if new_pos:
                        self.move_rectangle(new_pos)
                        self.last_mouse_position = new_pos  # in repect to origional image dimension
            elif self.annotation_type == ANNOTATION_TYPE.POLYGON:
                new_map = self.map_to_original_image(click_pos)
                if self.annotation_mode == ANNOTATION_MODE.EDIT:
                    if self.selected_object is not None and self.selected_vertex is not None:
                        # new_map = self.map_to_original_image(click_pos)
                        if new_map:
                            self.move_polygon_vertex(new_map)
                    elif self.selected_object is not None and self.line_segment is not None:
                        new_map = self.map_to_original_image(click_pos)
                        self.last_mouse_position = new_map
                        if new_map:
                            self.add_point_to_polygon(new_map)
                            self.selected_vertex = self.line_segment[1]
                            self.line_segment = None
                    elif self.moving_object and self.selected_object is not None:
                        # print("Moving Polygon")
                        new_map = self.map_to_original_image(click_pos)
                        if new_map:
                            self.move_polygon(new_map)
                            self.last_mouse_position = new_map
        self.update()

    def mouseReleaseEvent(self, event):
        if self.original_pixmap and event.button() == Qt.LeftButton:
            click_pos = event.pos()
            if self.annotation_type == ANNOTATION_TYPE.BBOX:
                if self.start_point and self.annotation_mode == ANNOTATION_MODE.CREATE:
                    end_point = self.map_to_original_image(click_pos)
                    if end_point:
                        self.end_point = end_point
                        rect = QRect(self.start_point, self.end_point).normalized()
                        if self.distance(self.start_point, self.end_point) > 20:
                            self.update_rectangle(bbox=rect)
                elif (
                    self.selected_vertex is not None
                    and self.annotation_mode == ANNOTATION_MODE.EDIT
                ):
                    self._commit_drag()  # one undo step for the whole vertex drag
                    self.selected_vertex = None
                elif self.moving_object and self.annotation_mode == ANNOTATION_MODE.EDIT:
                    self._commit_drag()  # one undo step for the whole move
                    self.moving_object = False
                self.start_point = None
                self.end_point = None
            elif self.annotation_type == ANNOTATION_TYPE.POLYGON:
                if (
                    self.selected_vertex is not None
                    and self.annotation_mode == ANNOTATION_MODE.EDIT
                ):
                    self.selected_vertex = None
                elif self.moving_object and self.annotation_mode == ANNOTATION_MODE.EDIT:
                    self.moving_object = False
                self.last_mouse_position = None
        # self.selected_object = None
        # self.selected_object_subset = None
        self.update()

    def keyPressEvent(self, event):
        # Capture the key press event and display the key information
        key = event.key()
        logger.debug("%s %s", "Key:", key)
        if event.type() in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
            key = event.key()
            key_text = (
                QKeySequence(key).toString().encode("utf-8", errors="replace").decode("utf-8")
            )
            logger.debug("%s %s", "Key text:", key_text)

        if self.annotation_type == ANNOTATION_TYPE.POLYGON:
            if key == Qt.Key_Delete:
                logger.debug("Delete Key Pressed")
                if self.selected_object is not None and self.selected_vertex is None:
                    self.undo_tree.remove_shape(self.selected_object)
                    self.shapes_changed.emit(self.undo_tree.shapes)
                    self.selected_object = None
                elif self.selected_object is not None and self.selected_vertex is not None:
                    self.remove_point_from_polygon(self.selected_vertex)
                    self.selected_vertex = None

        # Optional: If you want to handle the key press and not propagate it further, you can skip calling the base class implementation.
        # If you want the key press to be handled by the parent class as well, call the superclass's method:
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.current_pixmap:
            return
        painter = QPainter(self)
        offset_x = coords.image_offset(self.width(), self.current_pixmap.width())
        offset_y = coords.image_offset(self.height(), self.current_pixmap.height())
        painter.drawPixmap(offset_x, offset_y, self.current_pixmap)

        def to_screen(x, y):
            """Map model coordinates (original-image pixels) to screen pixels."""
            sx, sy = coords.to_screen(x, y, self.scale_factor, offset_x, offset_y)
            return QPoint(sx, sy)

        # Committed shapes are rendered purely from the document, regardless of
        # the active annotation type. A shape under live vertex-editing is drawn
        # from its working copy for immediate feedback.
        for index, shape in enumerate(self.undo_tree.shapes):
            if index == self._editing_index and self._editing_shape is not None:
                shape = self._editing_shape
            selected = self.selected_object is not None and self.selected_object == shape.id
            if isinstance(shape, Rectangle):
                self._paint_rectangle(painter, shape, to_screen, selected)
            elif isinstance(shape, Polygon):
                self._paint_polygon(painter, shape, to_screen, selected)

        # In-progress creation overlay depends on the active annotation type.
        if self.annotation_type == ANNOTATION_TYPE.BBOX and self.start_point and self.end_point:
            rect = QRect(
                to_screen(self.start_point.x(), self.start_point.y()),
                to_screen(self.end_point.x(), self.end_point.y()),
            ).normalized()
            painter.setPen(QPen(self.pen_color, 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(self.brush_color))
            painter.drawRect(rect)
            self._paint_vertices(
                painter,
                [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()],
            )
        elif self.annotation_type == ANNOTATION_TYPE.POLYGON and self.polygon_points:
            points = [to_screen(p.x(), p.y()) for p in self.polygon_points]
            painter.setPen(QPen(self.pen_color, 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(self.polygon_brush_color))
            painter.drawPolygon(QPolygon(points))
            self._paint_vertices(painter, points)

        if self.cursor_pos is not None:
            self._paint_cursor(painter, offset_x, offset_y)

    # --- paint helpers (all map model -> screen via the passed to_screen) ---

    def _label_text(self, index):
        if index is not None and 0 <= index < len(self.label_list):
            return self.label_list[index]
        return str(index)

    def _paint_label(self, painter, top_left, width, text):
        painter.setPen(QPen(self.title_pen_color, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(QColor(255, 255, 255, 75)))
        painter.drawRect(top_left.x(), top_left.y() - 20, width, 20)
        painter.setPen(QPen(QColor(0, 0, 0), 2, Qt.PenStyle.SolidLine))
        painter.drawText(top_left.x(), top_left.y() - 5, text)

    def _paint_vertices(self, painter, points, highlight_index=None):
        saved_brush = painter.brush()
        for i, point in enumerate(points):
            if i == highlight_index:
                painter.setBrush(QBrush(QColor(255, 255, 0)))
                painter.drawEllipse(point, 7, 7)
                painter.setBrush(saved_brush)
            else:
                painter.drawEllipse(point, 5, 5)

    def _paint_rectangle(self, painter, shape, to_screen, selected):
        rect = QRect(
            to_screen(shape.topleft.x, shape.topleft.y),
            to_screen(shape.bottomright.x, shape.bottomright.y),
        ).normalized()
        painter.setPen(QPen(self.pen_color, 3 if selected else 2, Qt.PenStyle.SolidLine))
        painter.setBrush(
            QBrush(self.selected_rectangle_brush_color if selected else self.brush_color)
        )
        painter.drawRect(rect)
        self._paint_vertices(
            painter,
            [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()],
            self.selected_vertex if selected else None,
        )
        self._paint_label(
            painter, rect.topLeft(), rect.width(), self._label_text(shape.category_id)
        )

    def _paint_polygon(self, painter, shape, to_screen, selected):
        points = [to_screen(p.x, p.y) for p in shape.points]
        painter.setPen(QPen(self.pen_color, 3 if selected else 2, Qt.PenStyle.SolidLine))
        painter.setBrush(
            QBrush(self.selected_polygon_brush_color if selected else self.polygon_brush_color)
        )
        painter.drawPolygon(QPolygon(points))
        self._paint_vertices(painter, points, self.selected_vertex if selected else None)
        b = shape.bbox
        self._paint_label(
            painter,
            to_screen(b.x, b.y),
            int(b.width * self.scale_factor),
            self._label_text(shape.category_id),
        )

    def _paint_cursor(self, painter, offset_x, offset_y):
        cx = offset_x + int(self.cursor_pos[0] * self.current_pixmap.width())
        cy = offset_y + int(self.cursor_pos[1] * self.current_pixmap.height())
        painter.setPen(QPen(self.pen_color, 1, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        arm = 9
        painter.drawLine(cx - arm, cy, cx + arm, cy)
        painter.drawLine(cx, cy - arm, cx, cy + arm)
        painter.drawEllipse(QPoint(cx, cy), 2, 2)

    def update_rectangle(self, **kwargs):  # need to rename later
        """A shape's geometry is complete; ask for its label, then create it.

        The label is chosen via the non-blocking keyboard-first LabelPicker; the
        shape is created in the picker's callback so the keyboard flow never
        stalls on a modal dialog.
        """
        bbox = kwargs.get("bbox")
        poly = kwargs.get("poly")
        if bbox is not None:
            self._pending_shape = ("bbox", bbox)
            self._show_label_picker()
        elif poly:
            self._pending_shape = ("poly", poly)
            self._show_label_picker()

    def _show_label_picker(self):
        if not self.label_list:
            logger.debug("No labels available to pick from")
            self._pending_shape = None
            return
        if self._label_picker is None:
            self._label_picker = LabelPicker(self)
        self._label_picker.pick(self.label_list, self._on_label_chosen, self._on_label_cancelled)

    def _on_label_chosen(self, category_index):
        pending = self._pending_shape
        self._pending_shape = None
        if pending is None:
            return
        kind, geom = pending
        if kind == "bbox":
            self._create_rectangle(geom, category_index)
        elif kind == "poly":
            self._create_polygon(geom, category_index)
        self.update()

    def _on_label_cancelled(self):
        self._pending_shape = None
        self.start_point = None
        self.end_point = None
        self.polygon_points = []
        self.update()

    def _create_rectangle(self, bbox, category_index):
        new_rectangle = Rectangle(
            id=len(self.undo_tree.shapes),
            category_id=category_index,
            topleft=Point(bbox.x(), bbox.y()),
            bottomright=Point(bbox.x() + bbox.width(), bbox.y() + bbox.height()),
        )
        self.undo_tree.add_shape(new_rectangle)
        self.shapes_changed.emit(self.undo_tree.shapes)

    def _create_polygon(self, poly, category_index):
        # Points are in original-image pixel space (same as every other shape).
        new_polygon = Polygon(
            id=len(self.undo_tree.shapes),
            category_id=category_index,
            points=[Point(p.x(), p.y()) for p in poly],
        )
        self.undo_tree.add_shape(new_polygon)
        self.shapes_changed.emit(self.undo_tree.shapes)
        self.polygon_points = []

    @staticmethod
    def distance(p1, p2):
        """
        Calculate the distance between two points.

        Args:

            p1 (QPoint): The first point.
            p2 (QPoint): The second point.

            Returns:

                float: The distance between the two points.

        """
        return ((p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2) ** 0.5

    @staticmethod
    def distance_to_line_segment(p, v, w):
        """Calculate the distance from point p to the line segment vw."""
        l2 = CanvasWidget.distance(v, w) ** 2
        if l2 == 0.0:
            return CanvasWidget.distance(p, v)
        t = max(
            0,
            min(
                1,
                ((p.x() - v.x()) * (w.x() - v.x()) + (p.y() - v.y()) * (w.y() - v.y())) / l2,
            ),
        )
        projection = QPoint(int(v.x() + t * (w.x() - v.x())), int(v.y() + t * (w.y() - v.y())))
        return CanvasWidget.distance(p, projection)

    def map_to_original_image(self, pos):
        """
        Map the position on the displayed image to the original image.

        Args:

            pos (QPoint): The position on the displayed image.

        Returns:

                QPoint: The position on the original image.
        """
        offset_x = coords.image_offset(self.width(), self.current_pixmap.width())
        offset_y = coords.image_offset(self.height(), self.current_pixmap.height())
        mapped = coords.to_original(
            pos.x(),
            pos.y(),
            self.scale_factor,
            offset_x,
            offset_y,
            self.current_pixmap.width(),
            self.current_pixmap.height(),
        )
        if mapped is None:
            return None
        return QPoint(mapped[0], mapped[1])

    def select_rectangle(self, pos):
        """
        Select the rectangle nearest to the selected point on the displayed image.

        Args:
            pos (QPoint): The position on the displayed image.

        Returns:
            dict: The selected rectangle dictionary with its attributes.
        """
        selected_rectangles = []
        selected_rectangles_id = []

        # Map the click position to the original image coordinates
        # mapped_pos = self.map_to_original_image(pos)

        # Iterate through all rectangles to find the ones containing the point
        # for rect in self.rectangles:
        for rect in self.undo_tree.shapes:
            if not isinstance(rect, Rectangle):
                continue
            rect_obj = QRect(
                int(rect.topleft.x),
                int(rect.topleft.y),
                int(rect.bottomright.x - rect.topleft.x),
                int(rect.bottomright.y - rect.topleft.y),
                # rect["bbox"][0], rect["bbox"][1], rect["bbox"][2], rect["bbox"][3]
            )
            if rect_obj.contains(pos):
                selected_rectangles.append(rect)
                selected_rectangles_id.append(rect.id)

        # If multiple rectangles contain the point, find the one closest to the point
        if selected_rectangles:
            closest_rect = min(
                selected_rectangles,
                key=lambda rect: self.distance_to_center(pos, rect),
            )
            logger.debug("%s %s", "selecting:", closest_rect.id)
            self.selected_object = closest_rect.id

    @staticmethod
    def distance_to_center(pos, rect):
        """
        Calculate the distance from a point to the center of a bounding box.

        Args:
            pos (QPoint): The position point.
            bbox (list): The bounding box coordinates [x, y, width, height].

        Returns:
            float: The distance from the point to the center of the bounding box.
        """
        center_x = rect.topleft.x + rect.bottomright.x / 2
        center_y = rect.topleft.y + rect.bottomright.y / 2
        return (pos.x() - center_x) ** 2 + (pos.y() - center_y) ** 2

    def find_object_to_edit(self, click_pos):
        # Iterate from top to bottom (reverse order) to find the topmost object
        # for rectangle in reversed(self.rectangles):
        min_dist = 100
        selected_rect_id = None
        selected_vertex_idx = None
        for rect in reversed(self.undo_tree.shapes):
            if not isinstance(rect, Rectangle):
                continue

            vertices = [
                QPoint(int(rect.topleft.x), int(rect.topleft.y)),  # top-left
                QPoint(int(rect.bottomright.x), int(rect.topleft.y)),  # top-right
                QPoint(int(rect.topleft.x), int(rect.bottomright.y)),  # bottom-left
                QPoint(int(rect.bottomright.x), int(rect.bottomright.y)),
            ]  # bottom-right
            mapped_pos = self.map_to_original_image(click_pos)

            for i, vertex in enumerate(vertices):
                dist = self.distance(vertex, mapped_pos)
                if dist <= 20 and dist < min_dist:
                    min_dist = dist
                    selected_rect_id = rect.id
                    selected_vertex_idx = i
                    logger.debug(f"Selecting rect: {rect.id}, vertx: {i}, dist: {dist}")
        if selected_rect_id is not None and selected_vertex_idx is not None:
            return selected_rect_id, selected_vertex_idx
        else:
            return None, None

    def get_selected_object(self):
        """
        Get the selected rectangle.

        Returns:

            dict: The selected rectangle.
        """
        # for rect in self.rectangles:
        for rect in self.undo_tree.shapes:
            if not isinstance(rect, Rectangle):
                continue
            if rect.id == self.selected_object:
                logger.debug("%s %s", "returning selected:", rect)
                return rect
        return None

    def _begin_drag(self, shape_id):
        """Start a mouse-drag edit of a shape: snapshot it so the whole drag
        commits as a single undo step on release (see _commit_drag)."""
        index = self.undo_tree.find_shape_index_by_id_or_none(shape_id)
        if index is None:
            self._drag_index = None
            self._drag_original = None
            return
        self._drag_index = index
        self._drag_original = copy.deepcopy(self.undo_tree.shapes[index])

    def _commit_drag(self):
        """Record the net effect of a mouse drag as one undoable step."""
        index = self._drag_index
        original = self._drag_original
        self._drag_index = None
        self._drag_original = None
        if index is None or original is None or index >= len(self.undo_tree.shapes):
            return
        final = copy.deepcopy(self.undo_tree.shapes[index])
        if isinstance(final, Rectangle):
            final = final.normalized()
        if final == original:
            return  # a click without movement — no history entry
        self.undo_tree.shapes[index] = copy.deepcopy(original)  # restore silently
        self.document.replace_shape(index, final)  # then one command original -> final
        self.update()

    def move_vertex(self, vertex_index, new_pos):
        """Reshape the dragged rectangle by moving one corner, in place.

        Corners: 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right. The
        edit is applied live (no history); the drag is normalized and committed
        as a single undo step on mouse release.
        """
        if self._drag_index is None:
            return
        rectangle = self.undo_tree.shapes[self._drag_index]
        if not isinstance(rectangle, Rectangle):
            return
        if vertex_index == 0:
            rectangle.topleft.x, rectangle.topleft.y = new_pos.x(), new_pos.y()
        elif vertex_index == 1:
            rectangle.bottomright.x, rectangle.topleft.y = new_pos.x(), new_pos.y()
        elif vertex_index == 2:
            rectangle.topleft.x, rectangle.bottomright.y = new_pos.x(), new_pos.y()
        elif vertex_index == 3:
            rectangle.bottomright.x, rectangle.bottomright.y = new_pos.x(), new_pos.y()
        else:
            return
        self.update()

    def move_rectangle(self, new_pos):
        """Translate the dragged shape in place by the mouse delta (committed as
        one undo step on release)."""
        if self._drag_index is None:
            return
        dx = new_pos.x() - self.last_mouse_position.x()
        dy = new_pos.y() - self.last_mouse_position.y()
        self.undo_tree.shapes[self._drag_index].move(dx, dy)
        self.update()

    def select_polygon(self, pos):
        selected_polygon = []
        selected_polygon_id = []
        selected_polygon_id_subset = []
        # TODO(gur-c5ee6b23.3 follow-up): mouse polygon selection still uses the
        # old dict-based store, which no longer exists; reimplement against
        # self.document.shapes. Until then this is a no-op.
        for polygons in []:
            for poly_idx, polygon in enumerate(polygons["polygon"]):
                poly = polygon.copy()
                # polygon_points = [QPoint(point.x(), point.y()) for point in poly]
                # polygon_points = [QPoint(point[0] * self.scale_factor, point[1] * self.scale_factor) for point in polygon_points]
                polygon_obj = QPolygon(poly)
                if polygon_obj.containsPoint(pos, Qt.OddEvenFill):
                    selected_polygon.append(polygon)
                    selected_polygon_id.append(polygons["id"])
                    selected_polygon_id_subset.append(poly_idx)
        if selected_polygon:
            closest_polygon = min(
                selected_polygon,
                key=lambda polygon: self.calculate_polygon_area(polygon),
            )
            self.selected_object = selected_polygon_id[selected_polygon.index(closest_polygon)]
            logger.debug("%s %s", "Selecting polygon:", self.selected_object)
            self.selected_object_subset = selected_polygon_id_subset[
                selected_polygon.index(closest_polygon)
            ]

            # print(f"Selected Polygon: {selected_polygon}")
            # closest_polygon = min(selected_polygon, key=lambda polygon: self.calculate_polygon_area(polygon))
            # print(f"Selected Polygon: {closest_polygon}")
            # print(f"Selected Polygon: {closest_polygon['id']}")
            # self.selected_object = closest_polygon["id"]

    @staticmethod
    def calculate_polygon_area(polygon):
        area = 0
        # polygon = QPolygon(polygon['polygon'])
        polygon = QPolygon(polygon)
        for i in range(polygon.count()):
            j = (i + 1) % polygon.count()
            area += polygon.point(i).x() * polygon.point(j).y()
            area -= polygon.point(j).x() * polygon.point(i).y()
        return abs(area) / 2

    def move_polygon(self, new_pos):
        if self.selected_object is not None:
            poly = self.get_selected_object()
            dx = new_pos.x() - self.last_mouse_position.x()
            dy = new_pos.y() - self.last_mouse_position.y()

            for i, point in enumerate(poly["polygon"][self.selected_object_subset]):
                poly["polygon"][self.selected_object_subset][i] = QPoint(
                    point.x() + dx, point.y() + dy
                )
            for poly_idx, polygon in enumerate(poly["polygon"]):
                if poly_idx == 0:
                    bbox = QPolygon(polygon).boundingRect()
                else:
                    bbox = bbox.united(QPolygon(polygon).boundingRect())
            # bbox = QPolygon(poly['polygon'][self.selected_object_subset]).boundingRect()
            poly["bbox"] = [bbox.x(), bbox.y(), bbox.width(), bbox.height()]
            self.last_mouse_position = new_pos

    def move_polygon_vertex(self, new_pos):
        if self.selected_object is not None:
            poly = self.get_selected_object()
            if poly is not None:
                poly["polygon"][self.selected_object_subset][self.selected_vertex] = new_pos

                for poly_idx, polygon in enumerate(poly["polygon"]):
                    if poly_idx == 0:
                        bbox = QPolygon(polygon).boundingRect()
                    else:
                        bbox = bbox.united(QPolygon(polygon).boundingRect())
                    # bbox = QPolygon(poly['polygon'][self.selected_object_subset]).boundingRect()
                    poly["bbox"] = [bbox.x(), bbox.y(), bbox.width(), bbox.height()]

                # bbox = QPolygon(poly['polygon']).boundingRect()
                # print(f"Bounding Box in mover polygon vertex: {bbox}")
                # poly['bbox'] = [bbox.x(), bbox.y(), bbox.width(), bbox.height()]
                # print(f"Bounding Box in mover polygon vertex: {poly['bbox']}")

    def add_point_to_polygon(self, new_pos):
        if self.selected_object is not None:
            poly = self.get_selected_object()
            if poly is not None:
                poly["polygon"][self.selected_object_subset].insert(self.line_segment[1], new_pos)
                for poly_idx, polygon in enumerate(poly["polygon"]):
                    if poly_idx == 0:
                        bbox = QPolygon(polygon).boundingRect()
                    else:
                        bbox = bbox.united(QPolygon(polygon).boundingRect())
                    # bbox = QPolygon(poly['polygon'][self.selected_object_subset]).boundingRect()
                    poly["bbox"] = [bbox.x(), bbox.y(), bbox.width(), bbox.height()]
                # bbox = QPolygon(poly['polygon']).boundingRect()
                # poly['bbox'] = [bbox.x(), bbox.y(), bbox.width(), bbox.height()]

    # def remove_point_from_polygon(self, point_index):
    #     if self.selected_object is not None:
    #         poly = self.get_selected_object()
    #         if poly is not None:
    #             poly['polygon'].pop(point_index)
    #             bbox = QPolygon(poly['polygon']).boundingRect()
    #             poly['bbox'] = [bbox.x(), bbox.y(), bbox.width(), bbox.height()]

    def find_polygon_to_edit(self, click_pos):
        # TODO(gur-c5ee6b23.3 follow-up): legacy dict-based polygon store removed;
        # reimplement against self.document.shapes. No-op for now.
        for polygons in []:
            polygon = polygons["polygon"]
            # polygon_obj = QPolygon(poly)

            # Check if click_pos is near any vertex of the polygon
            for poly_idx, poly in enumerate(polygon):
                for i, point in enumerate(poly):
                    if CanvasWidget.distance(QPoint(point.x(), point.y()), click_pos) <= 10:
                        return polygons["id"], poly_idx, i, None

                # Check if click_pos is on any line segment of the polygon
                for i, point in enumerate(poly):
                    v = QPoint(point.x(), point.y())
                    w = QPoint(poly[(i + 1) % len(poly)].x(), poly[(i + 1) % len(poly)].y())
                    # print(f"V: {v}, W: {w}")
                    # print(f"Click Pos: {click_pos}")
                    if CanvasWidget.distance_to_line_segment(click_pos, v, w) <= 10:
                        return polygons["id"], poly_idx, None, (i, (i + 1) % len(poly))

        return None, None, None, None

    def update_label_list(self, label_list):
        self.label_list = label_list
        logger.debug(f"Label List: {self.label_list}")

    def update_annotation_from_json(self, annotation: list):
        """
        Update the drawn rectangles from the annotation data.

        Args:
            annotation (list): A list of annotations containing the label and rectangle data.
            annotation = [{
            ...     "id": 1,
            ...     "category_id": 1,
            ...     "bbox": [10, 20, 100, 200],
            ...     "area": 1000,
            ...     "segmentation": [[10, 20, 100, 20, 100, 200, 10, 200]],
            ...     "iscrowd": 0
            ... }]
        """
        self.undo_tree.clear()
        for index, anno in enumerate(annotation):
            self.undo_tree.add_shape(shape_from_annotation(index, anno))
        if self.undo_tree.shapes:
            self.shapes_changed.emit(self.undo_tree.shapes)
        logger.debug(f"Loaded shapes: {len(self.undo_tree.shapes)}")
        self.update()

    def update_annotation_to_json(self):
        """
        Update the annotation data from the drawn rectangles.

        Returns:
            list: A list of annotations containing the label and rectangle data.
        """
        # Serialize every shape (rectangles AND polygons) through the model
        # serializer, which produces the stable COCO-like dict and re-derives ids
        # as contiguous array indices.
        return [
            annotation_from_shape(index, shape) for index, shape in enumerate(self.undo_tree.shapes)
        ]

    def to_document(self) -> AnnotationDocument:
        """The canvas's authoritative document (image meta is set by the caller
        before serializing). Its ``to_dict`` is the single save serializer.
        """
        return self.document

    def set_annotation_mode(self, mode):
        """Set the annotation mode."""
        self.annotation_mode = mode
        logger.debug(f"Annotation Mode: {self.annotation_mode}")
        if self.annotation_mode == ANNOTATION_MODE.CLEAR:
            self.clear_annotation()
            # if len(self.rectangles) > 0:
            self.shapes_changed.emit([])
            self.annotation_mode = ANNOTATION_MODE.NONE
        elif self.annotation_mode == ANNOTATION_MODE.DELETE:
            if self.selected_object is not None:
                for idx, rect in enumerate(self.undo_tree.shapes):
                    if rect.id == self.selected_object:
                        # self.rectangles.pop(idx)
                        self.undo_tree.remove_shape(idx)
                        logger.debug("Setting selected object to None")
                        self.selected_object = None
                        break
                # update the new object id
                # for idx, rect in enumerate(self.rectangles):
                #   rect["id"] = idx
                self.shapes_changed.emit(self.undo_tree.shapes)
                logger.debug("Setting selected object to None")
                self.selected_object = None
            self.annotation_mode = ANNOTATION_MODE.CREATE
        elif self.annotation_mode == ANNOTATION_MODE.EDIT:
            pass
        elif self.annotation_mode == ANNOTATION_MODE.CREATE:
            pass
        else:
            pass
        self.update()

    def select_object(self, object_id):
        if object_id == -1:
            logger.debug("Setting selected object to None")
            self.selected_object = None
        else:
            logger.debug("%s %s", "Setting selected object to ", object_id)
            self.selected_object = object_id
        self.update()
        self._emit_status()

    def undo(self):
        """Undo the last document mutation (add/remove/move/edit)."""
        if self.undo_tree.undo():
            self._after_history_change()

    def redo(self):
        """Redo the last undone document mutation."""
        if self.undo_tree.redo():
            self._after_history_change()

    def _after_history_change(self):
        # Selection may reference a shape that no longer exists; reset it and
        # refresh the object list from the (now-authoritative) document.
        self.selected_object = None
        self.selected_vertex = None
        self._editing_index = None
        self._editing_shape = None
        self.shapes_changed.emit(self.undo_tree.shapes)
        self.update()

    # --- status bar ---

    def status_text(self):
        """One-line summary of the current interaction state for the status bar."""
        parts = []
        if (
            self.cursor_pos is not None
            and self.original_pixmap is not None
            and not self.original_pixmap.isNull()
        ):
            cx = int(self.cursor_pos[0] * self.original_pixmap.width())
            cy = int(self.cursor_pos[1] * self.original_pixmap.height())
            parts.append(f"cursor {cx},{cy}px")
        if self.selected_object is not None:
            shape = self.get_shape_by_id(self.selected_object)
            if shape is not None:
                parts.append(f"shape: {self._label_text(shape.category_id)}")
        if self.is_editing_vertex() and self._editing_shape is not None:
            count = len(self._editing_shape.vertices())
            parts.append(f"vertex {(self.selected_vertex or 0) + 1}/{count}")
            parts.append("nudge 1px (Shift 5px)")
        elif self.cursor_pos is not None:
            parts.append("step 1% (Shift 5%)")
        return "    |    ".join(parts)

    def get_shape_by_id(self, shape_id):
        for shape in self.undo_tree.shapes:
            if shape.id == shape_id:
                return shape
        return None

    def _emit_status(self):
        self.status_slot.emit(self.status_text())

    # --- keyboard vertex editing ---

    def is_editing_vertex(self):
        return self._editing_index is not None

    def select_next_shape(self):
        self._cycle_selection(1)

    def select_prev_shape(self):
        self._cycle_selection(-1)

    def _cycle_selection(self, step):
        # Cancel any in-progress vertex edit when changing the selected shape.
        self.cancel_vertex_edit()
        shapes = self.undo_tree.shapes
        if not shapes:
            return
        ids = [s.id for s in shapes]
        if self.selected_object in ids:
            i = (ids.index(self.selected_object) + step) % len(ids)
        else:
            i = 0 if step > 0 else len(ids) - 1
        self.selected_object = ids[i]
        self.selected_vertex = None
        self.update()
        self._emit_status()

    def enter_or_cycle_vertex(self):
        """Tab: start editing the selected shape's vertices, or cycle to the next."""
        if self._editing_index is None:
            if self.selected_object is None:
                return
            index = self.undo_tree.find_shape_index_by_id_or_none(self.selected_object)
            if index is None:
                return
            self._editing_index = index
            self._editing_shape = copy.deepcopy(self.undo_tree.shapes[index])
            self.selected_vertex = 0
        else:
            count = len(self._editing_shape.vertices())
            self.selected_vertex = ((self.selected_vertex or 0) + 1) % count
        self.update()
        self._emit_status()

    def _nudge_editing_vertex(self, dx, dy):
        if self._editing_shape is None:
            return
        self._editing_shape.nudge_vertex(self.selected_vertex or 0, dx, dy)
        self.update()
        self._emit_status()

    def commit_vertex_edit(self):
        """Commit the live vertex edit as a single undoable step. Returns True
        if an edit was in progress."""
        if self._editing_index is None or self._editing_shape is None:
            return False
        shape = self._editing_shape
        if isinstance(shape, Rectangle):
            shape = shape.normalized()
        self.document.replace_shape(self._editing_index, shape)
        self._editing_index = None
        self._editing_shape = None
        self.selected_vertex = None
        self.update()
        self._emit_status()
        return True

    def cancel_vertex_edit(self):
        """Discard the live vertex edit. Returns True if one was in progress."""
        if self._editing_index is None:
            return False
        self._editing_index = None
        self._editing_shape = None
        self.selected_vertex = None
        self.update()
        self._emit_status()
        return True
