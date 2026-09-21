"""Export a curve's digitized points to CSV, in real-world data coordinates."""

from __future__ import annotations

import csv
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
