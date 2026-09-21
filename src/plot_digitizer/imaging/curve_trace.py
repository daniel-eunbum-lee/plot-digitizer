"""Color-based curve tracing: turn a sampled curve color into an ordered point list.

Traces column-by-column, taking the median row of matching pixels in each
column. This only handles function-like curves (a single y per x); looping
or near-vertical/parametric curves need a skeleton/graph-walk approach,
which is a documented v1 non-goal (see PLAN.md).
"""

from __future__ import annotations

import cv2
import numpy as np

from plot_digitizer.model.point import Point

_DEFAULT_TOLERANCE = 30.0
_MORPHOLOGY_KERNEL = np.ones((3, 3), np.uint8)


def trace_curve_by_color(
    image: np.ndarray,
    target_bgr: tuple[int, int, int],
    *,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> list[Point]:
    mask = _color_mask(image, target_bgr, tolerance)
    height, width = mask.shape
    points: list[Point] = []
    for x in range(width):
        matching_rows = np.nonzero(mask[:, x])[0]
        if matching_rows.size == 0:
            continue
        # Median rather than mean: robust to a handful of stray matched
        # pixels far from the main stroke in that column (e.g. where the
        # curve crosses a similarly-colored gridline or legend swatch).
        points.append(Point(x=float(x), y=float(np.median(matching_rows))))
    return points


def _color_mask(
    image: np.ndarray, target_bgr: tuple[int, int, int], tolerance: float
) -> np.ndarray:
    target = np.array(target_bgr, dtype=np.float64)
    distance = np.linalg.norm(image.astype(np.float64) - target, axis=2)
    mask: np.ndarray = (distance <= tolerance).astype(np.uint8)
    # Open then close: clears single-pixel color-noise speckles, then fills
    # small gaps anti-aliasing leaves along an otherwise-continuous stroke.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _MORPHOLOGY_KERNEL).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _MORPHOLOGY_KERNEL).astype(np.uint8)
    return mask
