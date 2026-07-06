"""Per-save-directory config.yaml handling, outside the window.

Wraps ConfigSpecHandler and exposes the three values the app cares about
(annotation type, mask export, include-image) with sane defaults, so the window
just reads/writes settings instead of juggling a raw dict.
"""

import os

from labelvim.utils.config import ConfigSpecHandler

CONFIG_FILE_NAME = "config.yaml"


class ConfigService:
    def __init__(self) -> None:
        self._handler: ConfigSpecHandler | None = None
        self._config: dict = {}

    def open(self, save_dir: str) -> None:
        """Open (creating if absent) config.yaml in ``save_dir``."""
        path = os.path.join(save_dir, CONFIG_FILE_NAME)
        self._handler = ConfigSpecHandler(path)
        self._config = self._handler.get_config()

    def annotation_type_value(self) -> int | None:
        """The stored annotation-type enum value, or None if unset."""
        return self._config.get("annotation_type")

    def save_mask(self) -> bool:
        return bool(self._config.get("save_mask", False))

    def include_img(self) -> bool:
        return bool(self._config.get("include_img", False))

    def update(self, annotation_type_value: int, save_mask: bool, include_img: bool) -> None:
        """Persist the three settings (no-op until a directory has been opened)."""
        self._config["annotation_type"] = annotation_type_value
        self._config["save_mask"] = save_mask
        self._config["include_img"] = include_img
        if self._handler is not None:
            self._handler.update_config(self._config)
