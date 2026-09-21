"""Resample a curve's points onto a regular abscissa (data-x) grid.

Pure math on top of `CoordinateTransform` -- no Qt, no OpenCV -- so the
grid/interpolation behaviour stays unit-testable without a display.
"""

from __future__ import annotations

import math

import numpy as np

from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.point import Point

# Guard against the final grid point being dropped when (stop - start) is an
# exact multiple of step only up to floating-point error (e.g. 0.1 * 3 < 0.3).
_GRID_EPSILON = 1e-9


def resample_curve_to_step(
    points: list[Point], transform: CoordinateTransform, step: float
) -> list[Point]:
    """Resample `points` onto data-x values spaced exactly `step` apart.

    The points are converted to data space, sorted by data-x, linearly
    interpolated onto the grid `min_x, min_x + step, min_x + 2*step, ...`
    (up to and including `max_x`), and converted back to pixel space -- pixel
    coordinates stay the persisted source of truth, per the model invariant.
    The original endpoints are *not* snapped onto the grid: the grid simply
    starts at the first point's data-x.

    Note for a LOG x-axis: `step` is still a fixed *additive* step in data
    space (1, 2, 3, ... for step=1), not a multiplicative/per-decade one, so
    the increment matches what a user reads off the axis labels. That is
    intentional, even though it produces non-uniform *pixel* spacing on a log
    axis -- unlike the log-space fitting in `calibration/axis.py`.

    Raises:
        ValueError: if `step` is not positive, or fewer than 2 points are given.
    """
    if step <= 0:
        raise ValueError(f"resample step must be positive, got {step!r}")
    if len(points) < 2:
        raise ValueError(f"resampling needs at least 2 points, got {len(points)}")

    data_points = [transform.pixel_to_data(point) for point in points]
    ordered = sorted(data_points, key=lambda data_point: data_point.x)
    source_x = np.array([data_point.x for data_point in ordered], dtype=float)
    source_y = np.array([data_point.y for data_point in ordered], dtype=float)

    start = float(source_x[0])
    stop = float(source_x[-1])
    step_count = int(math.floor((stop - start) / step + _GRID_EPSILON))
    grid_x = [start + index * step for index in range(step_count + 1)]

    grid_y = np.interp(grid_x, source_x, source_y)
    return [transform.data_to_pixel(x, float(y)) for x, y in zip(grid_x, grid_y, strict=True)]
