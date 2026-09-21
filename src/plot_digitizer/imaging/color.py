"""Color sampling utilities for picking a curve's color to trace."""

from __future__ import annotations

import numpy as np

from plot_digitizer.model.point import Point


def sample_color_bgr(image: np.ndarray, point: Point) -> tuple[int, int, int]:
    """Read the BGR color at a pixel position, clamped to the image bounds."""
    height, width = image.shape[:2]
    x = min(max(round(point.x), 0), width - 1)
    y = min(max(round(point.y), 0), height - 1)
    b, g, r = image[y, x]
    return int(b), int(g), int(r)
