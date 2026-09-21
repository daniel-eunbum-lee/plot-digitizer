"""Image loading, independent of any GUI framework."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class ImageLoadError(ValueError):
    """Raised when an image file cannot be read."""


def load_image(path: Path) -> np.ndarray:
    """Load an image as a BGR uint8 array (OpenCV's native channel order)."""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ImageLoadError(f"could not read image: {path}")
    return image
