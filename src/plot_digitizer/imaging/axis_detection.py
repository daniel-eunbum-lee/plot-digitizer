"""Automatic detection of candidate axis/gridlines via Hough line transform.

Detection only ever *proposes* candidates as plain data -- it never writes
into an AxisCalibration directly. False positives (gridlines, legend
borders, the plotted curve itself) are common enough on real charts that
silently auto-applying a detected line as a calibration reference would
risk corrupting a calibration the user never reviewed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

_ANGLE_TOLERANCE_DEG = 5.0
_DEFAULT_CANNY_LOW = 50
_DEFAULT_CANNY_HIGH = 150
_DEFAULT_MIN_LENGTH_FRACTION = 0.5
_MAX_LINE_GAP = 10


@dataclass(frozen=True)
class LineCandidate:
    """A detected near-horizontal or near-vertical line, in pixel space.

    `position` is the line's x-coordinate for a vertical candidate, or its
    y-coordinate for a horizontal one -- i.e. exactly the pixel value an
    AxisCalibration reference point needs.
    """

    position: float
    length: float


def detect_vertical_lines(
    image: np.ndarray,
    *,
    min_length_fraction: float = _DEFAULT_MIN_LENGTH_FRACTION,
    canny_low: float = _DEFAULT_CANNY_LOW,
    canny_high: float = _DEFAULT_CANNY_HIGH,
) -> list[LineCandidate]:
    return _detect_lines(
        image,
        vertical=True,
        min_length_fraction=min_length_fraction,
        canny_low=canny_low,
        canny_high=canny_high,
    )


def detect_horizontal_lines(
    image: np.ndarray,
    *,
    min_length_fraction: float = _DEFAULT_MIN_LENGTH_FRACTION,
    canny_low: float = _DEFAULT_CANNY_LOW,
    canny_high: float = _DEFAULT_CANNY_HIGH,
) -> list[LineCandidate]:
    return _detect_lines(
        image,
        vertical=False,
        min_length_fraction=min_length_fraction,
        canny_low=canny_low,
        canny_high=canny_high,
    )


def suggest_extremes(
    candidates: list[LineCandidate], *, top_k: int = 6
) -> tuple[LineCandidate, LineCandidate] | None:
    """Guess which two candidates are the axis extremes, from pixel position alone.

    An axis spine (or the outermost gridline) is typically both long and at
    one end of the detected set, so restricting to the `top_k` longest
    candidates -- the list arrives sorted by length descending -- and then
    taking the min/max `position` picks the pair a user most likely wants as
    their two calibration references. This reads no numbers off the chart;
    it is only a ranking hint, and the caller must present it as a proposal
    the user can edit or delete like any other candidate row.

    Returns None when there is no meaningful pair to suggest: fewer than two
    candidates, or every candidate sitting at the same position.
    """
    considered = candidates[:top_k]
    if len(considered) < 2:
        return None
    lowest = min(considered, key=lambda candidate: candidate.position)
    highest = max(considered, key=lambda candidate: candidate.position)
    if lowest.position == highest.position:
        return None
    return lowest, highest


def _detect_lines(
    image: np.ndarray,
    *,
    vertical: bool,
    min_length_fraction: float = _DEFAULT_MIN_LENGTH_FRACTION,
    canny_low: float = _DEFAULT_CANNY_LOW,
    canny_high: float = _DEFAULT_CANNY_HIGH,
) -> list[LineCandidate]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, canny_low, canny_high)
    height, width = gray.shape[:2]
    reference_length = height if vertical else width
    min_length = max(1, int(reference_length * min_length_fraction))

    segments = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(1, min_length // 2),
        minLineLength=min_length,
        maxLineGap=_MAX_LINE_GAP,
    )
    if segments is None:
        return []
    # OpenCV has returned this as either (N, 1, 4) or (N, 4) across versions;
    # normalize so the unpacking below doesn't depend on which.
    segments = segments.reshape(-1, 4)

    # Multiple short Hough segments often lie along the same real line
    # (e.g. a gridline broken by the plotted curve crossing it), so merge
    # segments whose position rounds to the same pixel and keep the
    # longest one seen at that position rather than reporting duplicates.
    best_length_by_position: dict[int, float] = {}
    for x1, y1, x2, y2 in segments:
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
        if vertical:
            matches_orientation = abs(angle - 90) <= _ANGLE_TOLERANCE_DEG
        else:
            matches_orientation = angle <= _ANGLE_TOLERANCE_DEG or angle >= (
                180 - _ANGLE_TOLERANCE_DEG
            )
        if not matches_orientation:
            continue

        length = math.hypot(x2 - x1, y2 - y1)
        position = (x1 + x2) / 2 if vertical else (y1 + y2) / 2
        bucket = round(position)
        if bucket not in best_length_by_position or length > best_length_by_position[bucket]:
            best_length_by_position[bucket] = length

    candidates = [
        LineCandidate(position=float(position), length=length)
        for position, length in best_length_by_position.items()
    ]
    candidates.sort(key=lambda candidate: candidate.length, reverse=True)
    return candidates
