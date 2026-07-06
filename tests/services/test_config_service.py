"""Tests for the Qt-free ConfigService."""

import os

from labelvim.services.config_service import ConfigService


def test_open_missing_creates_config(tmp_path):
    svc = ConfigService()
    svc.open(str(tmp_path))
    assert os.path.exists(tmp_path / "config.yaml")
    # nothing set yet -> defaults
    assert svc.annotation_type_value() is None
    assert svc.save_mask() is False
    assert svc.include_img() is False


def test_update_persists_and_reloads(tmp_path):
    svc = ConfigService()
    svc.open(str(tmp_path))
    svc.update(annotation_type_value=1, save_mask=True, include_img=True)

    reopened = ConfigService()
    reopened.open(str(tmp_path))
    assert reopened.annotation_type_value() == 1
    assert reopened.save_mask() is True
    assert reopened.include_img() is True


def test_update_without_open_is_noop():
    svc = ConfigService()
    # No directory opened -> update just holds values in memory, no crash.
    svc.update(annotation_type_value=2, save_mask=True, include_img=False)
    assert svc.save_mask() is True
    assert svc.include_img() is False
