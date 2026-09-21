"""Composes independent per-axis calibrations into a full 2D pixel<->data transform."""

from __future__ import annotations

from dataclasses import dataclass

from plot_digitizer.calibration.axis import AxisCalibration
from plot_digitizer.model.point import DataPoint, Point


@dataclass
class CoordinateTransform:
    """Converts between image pixel coordinates and real-world data coordinates.

    x and y are calibrated fully independently (e.g. a semi-log plot can have
    a linear x-axis and a log y-axis), which is why any perspective/skew
    correction must happen on the image before calibration -- this transform
    assumes pixel x and pixel y each map to one axis on their own.
    """

    x_axis: AxisCalibration
    y_axis: AxisCalibration

    def pixel_to_data(self, point: Point) -> DataPoint:
        return DataPoint(
            x=self.x_axis.pixel_to_value(point.x),
            y=self.y_axis.pixel_to_value(point.y),
        )

    def data_to_pixel(self, x: float, y: float) -> Point:
        return Point(
            x=self.x_axis.value_to_pixel(x),
            y=self.y_axis.value_to_pixel(y),
        )
