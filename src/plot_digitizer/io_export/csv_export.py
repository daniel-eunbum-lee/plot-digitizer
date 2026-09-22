"""Export a curve's digitized points to CSV, in real-world data coordinates."""

from __future__ import annotations

import csv
import itertools
from pathlib import Path

from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.curve import Curve


def export_curve_csv(curve: Curve, transform: CoordinateTransform, path: Path) -> None:
    data_points = curve.to_data_points(transform)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["x", "y"])
        for point in data_points:
            writer.writerow([point.x, point.y])


def export_curves_csv(curves: list[Curve], transform: CoordinateTransform, path: Path) -> None:
    """Export every curve to one CSV, as an `{name}_x, {name}_y` column pair each.

    Curves rarely have the same number of points, so rows are padded to the
    longest curve with blank cells rather than truncated to the shortest --
    truncating would silently drop real digitized points.
    """
    per_curve_points = [curve.to_data_points(transform) for curve in curves]
    header = list(
        itertools.chain.from_iterable((f"{curve.name}_x", f"{curve.name}_y") for curve in curves)
    )
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        for row_points in itertools.zip_longest(*per_curve_points):
            row: list[object] = []
            for point in row_points:
                row.extend(("", "") if point is None else (point.x, point.y))
            writer.writerow(row)
