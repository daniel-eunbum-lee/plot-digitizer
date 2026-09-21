"""Detection of discrete data-point markers (o/s/^/D glyphs) inside a color mask.

Charts frequently mark each underlying data point with a filled glyph drawn in
the same color as the connecting line. Those glyphs are the most valuable thing
on the chart -- they are the *actual* data -- but to a column-wise line tracer
they are just a locally very thick stroke that drags the traced position toward
the glyph silhouette instead of its center.

This module finds those glyphs so the tracer can handle them separately. Sizes
are expressed as multiples of the measured stroke thickness rather than absolute
pixel constants, so the same thresholds work on a 96-DPI screenshot and a
600-DPI scan of the same chart.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Fraction of its bounding box a contour must fill to count as a glyph. The
# pointiest glyphs in common use (triangle, diamond) fill exactly 0.5; 0.4
# keeps a margin for rasterization while still rejecting diagonal fragments.
_MIN_EXTENT = 0.4
# A glyph is drawn to be recognized by shape, so its bounding box is close to
# square; a stroke fragment that happens to fill its box is not.
_MAX_ASPECT = 1.5
_MIN_SEPARATION_KERNEL = 3
_SEPARATION_KERNEL_RATIO = 0.7


@dataclass(frozen=True)
class MarkerBlob:
    """One detected marker glyph, in image pixel coordinates.

    `width`/`height` describe the glyph's full bounding box (not the eroded
    core detection actually works on), so callers can use it directly to mask
    the glyph out of the line stroke.
    """

    center_x: float
    center_y: float
    width: float
    height: float


def estimate_stroke_thickness(mask: np.ndarray) -> float:
    """Estimate the curve's stroke thickness, in pixels, from a color mask.

    Measured as the median length of contiguous runs of set pixels, taken both
    down columns and across rows, keeping whichever median is smaller: a run
    only measures *across* the stroke when it is roughly perpendicular to it,
    so a near-horizontal stroke is measured by its column runs and a
    near-vertical one by its row runs. Taking the smaller median picks the
    perpendicular direction automatically.

    Connected components that are already isolated compact glyphs are excluded
    first. Without that, a scatter chart (markers, no connecting line) would
    report its *glyph* diameter as the stroke thickness, and every threshold
    derived from it would then be too large to ever match a glyph. Returns 0.0
    when the mask holds no stroke-like component at all.
    """
    binary = (mask > 0).astype(np.uint8)
    stroke = _stroke_components(binary)
    column_runs = _run_lengths(stroke)
    row_runs = _run_lengths(stroke.T)
    if column_runs.size == 0 or row_runs.size == 0:
        return 0.0
    return float(min(np.median(column_runs), np.median(row_runs)))


def detect_marker_blobs(
    mask: np.ndarray,
    *,
    min_diameter: float,
    max_diameter: float,
) -> list[MarkerBlob]:
    """Find compact marker glyphs in a binary color mask.

    Markers are usually drawn *on* the line, so the glyphs and the stroke form
    a single connected component -- contouring the mask as-is would just return
    the whole curve. The mask is therefore eroded first with a kernel wider than
    the stroke but narrower than an acceptable glyph: the stroke disappears
    entirely and each glyph survives as an isolated, uniformly shrunken core.
    Reported sizes add the erosion back so they describe the original glyph.

    Kept contours must be compact in *both* dimensions (bounding box width and
    height each within [min_diameter, max_diameter], and near-square) and fill
    enough of their bounding box. Those tests are what reject leftover diagonal
    stroke fragments: a line crossing a square window is thin in one dimension
    and fills little of the box, while a glyph is roughly isotropic and fills a
    large fraction of it (>=0.5 even for the pointiest common glyphs, a
    triangle or a diamond).

    A glyph clipped by the plot border (a data point sitting exactly on an axis
    limit) is deliberately *not* reported: only part of it was drawn, so its
    centroid would be pulled inwards. Those fall through to ordinary line
    tracing, which stays centered on whatever is visible.
    """
    if min_diameter <= 0 or max_diameter < min_diameter:
        return []

    binary = (mask > 0).astype(np.uint8)
    kernel_size = _separation_kernel_size(min_diameter)
    eroded = cv2.erode(binary, np.ones((kernel_size, kernel_size), np.uint8))
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Erosion by a k x k kernel pulls a blob's bounding box in by (k - 1) / 2 on
    # every side (a little more for a round glyph, whose edge curves away from
    # the kernel corners), so adding k - 1 back recovers the glyph's own size.
    grow = float(kernel_size - 1)
    blobs: list[MarkerBlob] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        width = box_width + grow
        height = box_height + grow
        if not (min_diameter <= width <= max_diameter):
            continue
        if not (min_diameter <= height <= max_diameter):
            continue
        if max(width, height) / min(width, height) > _MAX_ASPECT:
            continue

        # Moments of the *filled* contour rather than of the contour outline:
        # cv2.contourArea/m00 on an outline is a polygon area, which
        # under-reports a small blob's true pixel area by roughly half its
        # perimeter and would push a genuine triangle glyph below _MIN_EXTENT.
        filled = np.zeros((box_height, box_width), np.uint8)
        cv2.drawContours(filled, [contour], -1, 1, thickness=cv2.FILLED, offset=(-x, -y))
        moments = cv2.moments(filled, binaryImage=True)
        area = moments["m00"]
        if area <= 0 or area / (box_width * box_height) < _MIN_EXTENT:
            continue

        blobs.append(
            MarkerBlob(
                center_x=x + moments["m10"] / area,
                center_y=y + moments["m01"] / area,
                width=width,
                height=height,
            )
        )
    blobs.sort(key=lambda blob: blob.center_x)
    return blobs


def _separation_kernel_size(min_diameter: float) -> int:
    """Odd erosion kernel width that erases the stroke but not an acceptable glyph.

    `min_diameter` is derived by the caller as a multiple of the measured stroke
    thickness, so a fraction of it lands between the two: wide enough that no
    stroke pixel keeps a full neighbourhood, narrow enough that a minimum-size
    glyph still has a core left over.
    """
    size = max(_MIN_SEPARATION_KERNEL, int(round(min_diameter * _SEPARATION_KERNEL_RATIO)))
    return size if size % 2 else size + 1


def _stroke_components(binary: np.ndarray) -> np.ndarray:
    """Copy of `binary` with compact glyph-shaped components removed."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    widths = stats[1:, cv2.CC_STAT_WIDTH].astype(np.float64)
    heights = stats[1:, cv2.CC_STAT_HEIGHT].astype(np.float64)
    areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
    aspects = np.maximum(widths, heights) / np.minimum(widths, heights)
    extents = areas / (widths * heights)

    is_stroke = np.ones(count, dtype=bool)
    is_stroke[0] = False  # label 0 is the background
    is_stroke[1:] = ~((aspects <= _MAX_ASPECT) & (extents >= _MIN_EXTENT))
    result: np.ndarray = is_stroke[labels].astype(np.uint8)
    return result


def _run_lengths(binary: np.ndarray) -> np.ndarray:
    """Lengths of every run of contiguous set pixels down each column."""
    height, width = binary.shape
    # Zero sentinel rows plus a column-major flatten: each column's pixels stay
    # contiguous and are separated by zeros, so no run spans two columns.
    padded = np.zeros((height + 2, width), np.int8)
    padded[1:-1] = binary
    flat = padded.reshape(-1, order="F")
    transitions = np.diff(flat)
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)
    return ends - starts
