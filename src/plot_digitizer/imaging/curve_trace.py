"""Color-based curve tracing: turn a sampled curve color into an ordered point list.

Traces column-by-column, taking the median row of matching pixels in each
column. This only handles function-like curves (a single y per x); looping
or near-vertical/parametric curves need a skeleton/graph-walk approach,
which is a documented v1 non-goal (see PLAN.md).

Charts that mark each data point with a glyph (circle/square/triangle/diamond)
are handled separately: a glyph is many columns wide, so the per-column median
inside it follows the glyph silhouette rather than the curve. Detected glyphs
are cut out of the mask before the column scan and contribute one point each,
at their center (see `marker_detect`).

A legend's sample line and glyph are drawn in the exact curve color, so they
are excised from the mask before either step even runs (see `legend_detect`) --
otherwise the legend entry would itself be traced or mistaken for a marker.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from plot_digitizer.imaging.axis_detection import detect_plot_area
from plot_digitizer.imaging.legend_detect import detect_legend_box
from plot_digitizer.imaging.marker_detect import (
    MarkerBlob,
    detect_marker_blobs,
    estimate_stroke_thickness,
)
from plot_digitizer.model.point import Point

_DEFAULT_TOLERANCE = 30.0
_MORPHOLOGY_KERNEL = np.ones((3, 3), np.uint8)
# A genuinely isolated single matched pixel (no matching 8-connected
# neighbor at all) is essentially never a real stroke fragment -- even a
# single dash or dot in a dashed/dotted linestyle spans several connected
# pixels. Deliberately conservative (not a larger multi-pixel-blob
# threshold): a bigger cutoff starts discarding real short dash/dot
# fragments too, trading a general fix for overfitting to any one noisy
# fixture's specific noise statistics.
_MIN_COMPONENT_AREA = 2

# A glyph is only distinguishable from the stroke it sits on if it is clearly
# fatter than that stroke; below this multiple the two are the same size and we
# would start "detecting" line corners and dash ends.
_MARKER_MIN_DIAMETER_RATIO = 1.8
# Second, independent lower bound: a glyph a reader is meant to identify by
# shape is a visible fraction of the chart (matplotlib's default markersize is
# ~1.5% of figure height), while dash fragments are far smaller. This matters
# where the stroke estimate is unusable because the chart has no continuous
# stroke at all -- a scatter plot, or a hairline the mask cleanup erases.
_MARKER_MIN_DIAMETER_IMAGE_FRACTION = 0.01
_MARKER_MAX_DIAMETER_IMAGE_FRACTION = 0.1
# Anti-aliased glyph edges sit just outside the detected box; strip a couple of
# extra pixels so no glyph fringe is left behind to skew the line scan.
_MARKER_CLEAR_PADDING = 2


def trace_curve_by_color(
    image: np.ndarray,
    target_bgr: tuple[int, int, int],
    *,
    tolerance: float = _DEFAULT_TOLERANCE,
    detect_markers: bool = True,
    exclude_legend: bool = True,
) -> list[Point]:
    threshold_mask = _threshold_mask(image, target_bgr, tolerance)
    if exclude_legend:
        # Before any cleanup/marker detection: a legend's sample line and
        # glyph are drawn in the exact curve color, so left in they would
        # otherwise be traced (or detected as a marker) like real data.
        threshold_mask = _mask_without_legend(image, threshold_mask)
    mask = _clean_mask(threshold_mask)
    blobs = _detect_markers(mask, threshold_mask) if detect_markers else []
    # With no glyphs found this is the untouched mask, so a marker-less curve
    # traces exactly as it did before marker support existed.
    line_mask = _mask_without_blobs(mask, blobs)

    points = [Point(x=blob.center_x, y=blob.center_y) for blob in blobs]
    points.extend(_trace_line(line_mask))
    points.sort(key=lambda point: point.x)
    return points


def _mask_without_legend(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    plot_area = detect_plot_area(image)
    legend_box = detect_legend_box(image, plot_area=plot_area)
    if legend_box is None:
        return mask
    x0, y0, x1, y1 = legend_box
    cleared = mask.copy()
    cleared[y0:y1, x0:x1] = 0
    return cleared


def _trace_line(mask: np.ndarray) -> list[Point]:
    _, width = mask.shape
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


def _detect_markers(mask: np.ndarray, threshold_mask: np.ndarray) -> list[MarkerBlob]:
    height, width = mask.shape
    short_side = min(height, width)
    # Thickness comes from the pre-cleanup mask on purpose: the opening in
    # _clean_mask wipes out any stroke thinner than its 3x3 kernel, which would
    # leave only the glyphs behind and make the "stroke" estimate report the
    # glyph size -- exactly the number the thresholds must stay below.
    thickness = estimate_stroke_thickness(threshold_mask)
    min_diameter = max(
        thickness * _MARKER_MIN_DIAMETER_RATIO,
        short_side * _MARKER_MIN_DIAMETER_IMAGE_FRACTION,
    )
    max_diameter = short_side * _MARKER_MAX_DIAMETER_IMAGE_FRACTION
    if max_diameter < min_diameter:
        return []
    return detect_marker_blobs(mask, min_diameter=min_diameter, max_diameter=max_diameter)


def _mask_without_blobs(mask: np.ndarray, blobs: list[MarkerBlob]) -> np.ndarray:
    if not blobs:
        return mask
    height, width = mask.shape
    line_mask = mask.copy()
    for blob in blobs:
        x0 = max(0, math.floor(blob.center_x - blob.width / 2) - _MARKER_CLEAR_PADDING)
        x1 = min(width, math.ceil(blob.center_x + blob.width / 2) + _MARKER_CLEAR_PADDING + 1)
        y0 = max(0, math.floor(blob.center_y - blob.height / 2) - _MARKER_CLEAR_PADDING)
        y1 = min(height, math.ceil(blob.center_y + blob.height / 2) + _MARKER_CLEAR_PADDING + 1)
        line_mask[y0:y1, x0:x1] = 0
    return line_mask


def _threshold_mask(
    image: np.ndarray, target_bgr: tuple[int, int, int], tolerance: float
) -> np.ndarray:
    target = np.array(target_bgr, dtype=np.float64)
    distance = np.linalg.norm(image.astype(np.float64) - target, axis=2)
    mask: np.ndarray = (distance <= tolerance).astype(np.uint8)
    return mask


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    # Open then close: clears single-pixel color-noise speckles, then fills
    # small gaps anti-aliasing leaves along an otherwise-continuous stroke.
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _MORPHOLOGY_KERNEL).astype(np.uint8)
    if not opened.any() and mask.any():
        # Opening requires a full 3x3 same-color neighborhood to survive, so
        # a stroke thinner than that -- a perfectly real 1px hairline, common
        # on screenshots/vector-rendered charts, not just noise -- gets
        # erased entirely rather than just despeckled. Fall back to a
        # connected-component *area* filter instead, which keys on a
        # component's total pixel count: a thin-but-long real stroke (many
        # connected pixels) survives while a truly isolated speck does not.
        # Only used as a fallback (not unconditionally) so every case that
        # already worked under plain opening keeps behaving exactly as before.
        opened = _remove_isolated_pixels(mask)
    cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, _MORPHOLOGY_KERNEL).astype(np.uint8)
    return cleaned


def _remove_isolated_pixels(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.ones(count, dtype=bool)
    keep[0] = False  # background label
    keep[stats[:, cv2.CC_STAT_AREA] < _MIN_COMPONENT_AREA] = False
    result: np.ndarray = keep[labels].astype(np.uint8)
    return result
