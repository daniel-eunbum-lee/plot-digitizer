"""Project: holds the working state for one digitizing session."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.imaging.perspective import PerspectiveTransform
from plot_digitizer.model.curve import Curve


def _default_axis() -> AxisCalibration:
    return AxisCalibration(scale=AxisScale.LINEAR)


@dataclass
class Project:
    image_path: Path
    x_axis: AxisCalibration = field(default_factory=_default_axis)
    y_axis: AxisCalibration = field(default_factory=_default_axis)
    curves: list[Curve] = field(default_factory=list)
    active_curve_index: int = -1
    perspective: PerspectiveTransform | None = None

    def is_calibrated(self) -> bool:
        return self.x_axis.is_valid() and self.y_axis.is_valid()

    def transform(self) -> CoordinateTransform:
        return CoordinateTransform(x_axis=self.x_axis, y_axis=self.y_axis)

    @property
    def active_curve(self) -> Curve | None:
        if 0 <= self.active_curve_index < len(self.curves):
            return self.curves[self.active_curve_index]
        return None

    def add_curve(self, name: str, color_hex: str = "#1f77b4") -> Curve:
        curve = Curve(name=name, color_hex=color_hex)
        self.curves.append(curve)
        self.active_curve_index = len(self.curves) - 1
        return curve
