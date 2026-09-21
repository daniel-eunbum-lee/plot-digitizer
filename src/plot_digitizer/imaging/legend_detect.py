"""Detection of a chart's legend box, so curve tracing can ignore it.

A legend swatch is drawn in the exact same color as its curve -- that is the
whole point of a legend -- so naive color-threshold tracing (`curve_trace.py`)
picks up the swatch's short sample line (and its marker glyph, if any) as if
it were real data. This module locates the legend's own bounding rectangle so
that region can be excluded from the trace mask before tracing runs.

Detection relies on three properties that, together, are specific to a
legend's frame and not to any other rectangle a chart might contain:

1. It sits fully *inside* the plot's axes, with a visible gap on every side --
   unlike the plot area's own border, which coincides with the axes spines.
2. Its border is a deliberate, solid, fairly dark stroke (matplotlib's default
   legend edgecolor renders at roughly mid-gray) -- unlike a gridline, which
   is thin, light, and often dashed/dotted, so a "rectangle" a closed
   grid-cell boundary would coincidentally trace is a much fainter box.
3. It is a small fraction of the plot's total area -- a handful of stacked
   entries, not the whole chart.

Like `axis_detection`, this only ever *proposes* a region to exclude from an
otherwise-editable traced curve; it never touches calibration or committed
points. A chart with no legend, or a legend placed outside the axes bounding
box (e.g. `bbox_to_anchor` placement), correctly yields no detection -- this
is a deliberate scope limit rather than a bug, since guessing wrong would
silently discard real curve data instead of just failing to clean up a legend.
"""

from __future__ import annotations

import cv2
import numpy as np

_CANNY_LOW = 50
_CANNY_HIGH = 150
_CLOSE_KERNEL = np.ones((3, 3), np.uint8)

# A legend is a handful of stacked entries, not the whole chart, but must be
# large enough to be more than a stray Canny artifact.
_MIN_AREA_FRACTION = 0.003
_MAX_AREA_FRACTION = 0.25

# The legend box must clear the plot's own spines by at least this many
# pixels on every side; the plot area's own border sits flush against (or
# inside by a hair of) the spines, and this is what tells the two apart.
_MIN_SPINE_MARGIN = 2.0

# Sampled a few pixels either side of each candidate edge to allow for the
# contour landing on either side of the actual stroke. Measured empirically
# against examples/test_plot_*.png: a real legend border's typical (median)
# darkness lands around 210-215 out of 255, while a coincidental grid-cell
# "rectangle" (bounded by light, often-dashed gridlines) lands above 245.
# 230 sits with headroom on both sides of that gap.
_BORDER_SAMPLE_BAND = 3
_MAX_BORDER_GRAY = 230.0


def detect_legend_box(
    image: np.ndarray,
    *,
    plot_area: tuple[float, float, float, float] | None,
) -> tuple[int, int, int, int] | None:
    """Guess the legend's pixel bounding box as `(x0, y0, x1, y1)`, or None.

    `plot_area` is `(left, top, right, bottom)`, as returned by
    `imaging.axis_detection.detect_plot_area`. Detection is skipped entirely (always
    returns None) when it is unavailable, since the plot-area margin check is
    the primary signal that rules out the plot's own border and any
    grid-bounded region -- without it, a low-confidence guess risks excising
    real curve data instead of a legend.
    """
    if plot_area is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    height, width = gray.shape[:2]
    image_area = height * width

    edges = cv2.Canny(gray, _CANNY_LOW, _CANNY_HIGH)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, _CLOSE_KERNEL)
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        x1, y1 = x + box_width, y + box_height
        area_fraction = (box_width * box_height) / image_area
        if not (_MIN_AREA_FRACTION <= area_fraction <= _MAX_AREA_FRACTION):
            continue
        if not _clears_plot_spines((x, y, x1, y1), plot_area):
            continue
        if _typical_border_darkness(gray, (x, y, x1, y1)) > _MAX_BORDER_GRAY:
            continue
        candidates.append((x, y, x1, y1))

    if not candidates:
        return None
    # Canny commonly yields both the inner and outer edge of one border
    # stroke as separate contours a pixel or two apart; the smallest is
    # whichever of those (or the true legend over any larger false match)
    # sits tightest around the actual content.
    return min(candidates, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))


def _clears_plot_spines(
    box: tuple[int, int, int, int], plot_area: tuple[float, float, float, float]
) -> bool:
    x0, y0, x1, y1 = box
    left, top, right, bottom = plot_area
    return (
        x0 - left >= _MIN_SPINE_MARGIN
        and right - x1 >= _MIN_SPINE_MARGIN
        and y0 - top >= _MIN_SPINE_MARGIN
        and bottom - y1 >= _MIN_SPINE_MARGIN
    )


def _typical_border_darkness(gray: np.ndarray, box: tuple[int, int, int, int]) -> float:
    """Median darkest-pixel-per-column/row across all four edges of `box`.

    Taking the minimum across a small band at each position (not just the
    single pixel exactly on the contour) tolerates the contour sitting a
    pixel off the true stroke; taking the median across the edge's length
    (not the single darkest pixel found) keeps one incidental dark crossing
    -- the plotted curve passing through -- from making a light gridline
    register as a dark legend border.
    """
    x0, y0, x1, y1 = box
    height, width = gray.shape[:2]
    band = _BORDER_SAMPLE_BAND
    top = gray[max(0, y0 - band) : y0 + band, x0:x1]
    bottom = gray[y1 - band : min(height, y1 + band), x0:x1]
    left = gray[y0:y1, max(0, x0 - band) : x0 + band]
    right = gray[y0:y1, x1 - band : min(width, x1 + band)]

    mins = [
        side.min(axis=axis)
        for side, axis in ((top, 0), (bottom, 0), (left, 1), (right, 1))
        if side.size > 0
    ]
    if not mins:
        return 255.0
    return float(np.median(np.concatenate(mins)))
