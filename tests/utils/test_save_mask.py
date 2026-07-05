"""save_mask must write a lossless PNG regardless of the source extension."""

import numpy as np
from PIL import Image

from labelvim.utils.save_mask import save_mask


def _distinct_colors(path):
    arr = np.array(Image.open(path))
    return {tuple(px) for px in arr.reshape(-1, arr.shape[-1]).tolist()}


def test_save_mask_forces_png_extension(tmp_path):
    mask = np.zeros((8, 8, 3), dtype=np.uint8)
    # a .jpg source name must still be written as .png
    save_mask(mask, str(tmp_path), "33932.jpg")
    out = tmp_path / "mask" / "33932.png"
    assert out.exists()
    assert not (tmp_path / "mask" / "33932.jpg").exists()
    assert Image.open(out).format == "PNG"


def test_save_mask_is_lossless(tmp_path):
    # Two exact palette colours + background; a lossy encoder would smear these
    # into many intermediate values around the edge.
    mask = np.zeros((16, 16, 3), dtype=np.uint8)
    mask[:8, :8] = (234, 168, 85)
    mask[8:, 8:] = (143, 195, 54)
    save_mask(mask, str(tmp_path), "img.png")
    colors = _distinct_colors(tmp_path / "mask" / "img.png")
    assert colors == {(0, 0, 0), (234, 168, 85), (143, 195, 54)}
