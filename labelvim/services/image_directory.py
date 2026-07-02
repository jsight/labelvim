"""Qt-free model of the image directory being annotated.

Owns the list of images, which ones already have a saved annotation, the
current selection index, and deletion — so this logic is unit-testable without
any widgets. The window (LabelVim) drives the UI from this state.
"""

import os
from dataclasses import dataclass, field

from labelvim.utils.utils import get_image_list


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


@dataclass
class ImageDirectoryService:
    load_dir: str = ""
    save_dir: str = ""
    image_paths: list[str] = field(default_factory=list)
    # Stems (basename without extension) whose annotation JSON exists on disk.
    annotated_stems: set[str] = field(default_factory=set)
    current_index: int = -1

    def load(self, load_dir: str) -> list[str]:
        """Scan a load directory for images and reset the selection."""
        self.load_dir = load_dir
        self.image_paths = get_image_list(load_dir) if load_dir else []
        self.current_index = -1
        return self.image_paths

    def set_save_dir(self, save_dir: str, annotated_stems: set[str] | None = None) -> None:
        self.save_dir = save_dir
        self.annotated_stems = set(annotated_stems) if annotated_stems else set()

    # --- queries ---

    @property
    def stems(self) -> list[str]:
        return [_stem(p) for p in self.image_paths]

    @property
    def count(self) -> int:
        return len(self.image_paths)

    def is_valid_index(self, index: int) -> bool:
        return 0 <= index < self.count

    def path_at(self, index: int) -> str | None:
        return self.image_paths[index] if self.is_valid_index(index) else None

    def stem_at(self, index: int) -> str | None:
        path = self.path_at(index)
        return _stem(path) if path is not None else None

    def current_path(self) -> str | None:
        return self.path_at(self.current_index)

    def current_stem(self) -> str | None:
        return self.stem_at(self.current_index)

    def has_annotation(self, stem: str | None) -> bool:
        return stem is not None and stem in self.annotated_stems

    def json_path(self, stem: str) -> str:
        return os.path.join(self.save_dir, stem + ".json")

    # --- mutations ---

    def select(self, index: int) -> bool:
        """Set the current index; returns True if it points at a valid image."""
        self.current_index = index
        return self.is_valid_index(index)

    def next(self) -> int:
        if self.current_index < self.count - 1:
            self.current_index += 1
        return self.current_index

    def previous(self) -> int:
        if self.current_index > 0:
            self.current_index -= 1
        return self.current_index

    def mark_annotated(self, stem: str) -> None:
        self.annotated_stems.add(stem)

    def remove(self, index: int) -> str | None:
        """Remove the image at ``index`` and forget its annotation record.

        Returns the on-disk JSON path that should be deleted (if the removed
        image had a saved annotation), else None. Clamps the current index.
        """
        if not self.is_valid_index(index):
            return None
        stem = self.stems[index]
        self.image_paths.pop(index)
        json_to_delete = None
        if stem in self.annotated_stems:
            self.annotated_stems.discard(stem)
            json_to_delete = self.json_path(stem)
        if self.current_index >= self.count:
            self.current_index = self.count - 1
        return json_to_delete
