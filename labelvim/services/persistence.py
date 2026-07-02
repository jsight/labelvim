"""Saving annotations, masks, and the source-image move — outside the window.

Operates on an AnnotationDocument and the existing mask utilities. The window
(LabelVim) gathers the document from the canvas and calls this; the service does
the file I/O so it can be reasoned about (and partly tested) without widgets.
"""

import json
import logging
import os
import shutil
from typing import TYPE_CHECKING

from labelvim.utils.save_mask import create_mask
from labelvim.utils.save_mask import save_mask as write_mask_file

if TYPE_CHECKING:
    from labelvim.models.document import AnnotationDocument

logger = logging.getLogger(__name__)


class AnnotationPersistenceService:
    def __init__(self, save_mask: bool = False, include_img: bool = False) -> None:
        # Mask export toggles (also mirrored into config.yaml by the window).
        self.save_mask = save_mask
        self.include_img = include_img

    def json_path(self, save_dir: str, stem: str) -> str:
        return os.path.join(save_dir, stem + ".json")

    def write_document(self, document: "AnnotationDocument", save_dir: str, stem: str) -> str:
        """Write ``document.to_dict()`` to ``save_dir/stem.json`` and return the path.

        This is the single on-disk annotation serializer.
        """
        path = self.json_path(save_dir, stem)
        with open(path, "w") as f:
            json.dump(document.to_dict(), f, indent=4)
        return path

    def move_into_save_dir(self, image_path: str, save_dir: str) -> str | None:
        """Move the source image into ``save_dir`` when it lives elsewhere.

        Used to track "finished" files by relocating them next to their saved
        annotation. Returns the new path, or None if no move was needed.
        """
        if not save_dir:
            return None
        src = os.path.normpath(image_path)
        if os.path.dirname(src) == os.path.normpath(save_dir):
            return None
        dest = os.path.join(save_dir, os.path.basename(image_path))
        shutil.move(image_path, dest)
        return dest

    def write_mask(
        self,
        document: "AnnotationDocument",
        image_path: str,
        save_dir: str,
        label_map: list[str],
        mask_type: str,
    ) -> None:
        """Render and save the annotation mask for one image."""
        import cv2

        image = cv2.imread(image_path)
        if image is None:
            logger.warning("Cannot read image for mask: %s", image_path)
            return
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        data = document.to_dict()
        mask = create_mask(
            image=image,
            annotations=data["annotations"],
            label_map=label_map,
            include_img=self.include_img,
            mask_type=mask_type,
        )
        write_mask_file(mask, save_dir, data["imagePath"])
