"""Menu wiring: no dead entries, Annotation Type is actionable."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from main import LabelVim

    win = LabelVim()
    yield win
    win.close()


def test_unimplemented_view_actions_are_hidden(window):
    # Fill / Line Color are not implemented; they must not appear as menu
    # entries that silently do nothing.
    assert window.actionFill.isVisible() is False
    assert window.actionLine_Color.isVisible() is False


def test_annotation_type_action_is_connected(window):
    assert window.actionAnnotation_Type.receivers(window.actionAnnotation_Type.triggered) > 0


def test_change_annotation_type_persists_to_config(window, tmp_path, monkeypatch):
    from labelvim.utils.config import ANNOTATION_TYPE

    window.save_dir = str(tmp_path)
    window.config.open(str(tmp_path))

    # Stand in for the modal chooser: pick segmentation.
    def choose_polygon():
        window.annotation_type = ANNOTATION_TYPE.POLYGON
        window.canvas_widget.update_annotation_type(ANNOTATION_TYPE.POLYGON)

    monkeypatch.setattr(window, "show_task_selection_dialog", choose_polygon)
    window._LabelVim__change_annotation_type()

    reopened = type(window.config)()
    reopened.open(str(tmp_path))
    assert reopened.annotation_type_value() == ANNOTATION_TYPE.POLYGON.value
