"""ExportFileDialog must construct even with a missing/partial config.yaml."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from labelvim.utils.config import ANNOTATION_TYPE  # noqa: E402
from labelvim.widgets.export_file import ExportFileDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _dir(tmp_path, config_text):
    if config_text is not None:
        (tmp_path / "config.yaml").write_text(config_text)
    (tmp_path / "33924.json").write_text("{}")
    return str(tmp_path)


@pytest.mark.parametrize(
    "config_text,expected",
    [
        (None, ANNOTATION_TYPE.BBOX),  # no config file
        ("", ANNOTATION_TYPE.BBOX),  # empty file
        ("save_mask: false\n", ANNOTATION_TYPE.BBOX),  # missing annotation_type key
        ("annotation_type: 999\n", ANNOTATION_TYPE.BBOX),  # unknown enum value
        ("annotation_type: 2\n", ANNOTATION_TYPE.POLYGON),  # valid
    ],
)
def test_export_dialog_constructs_with_any_config(app, tmp_path, config_text, expected):
    d = _dir(tmp_path, config_text)
    dlg = ExportFileDialog(save_dir=d, data_dir=d)  # must not raise
    assert dlg.task_type == expected
    assert dlg.file_list == ["33924.json"]  # json list found regardless of config
