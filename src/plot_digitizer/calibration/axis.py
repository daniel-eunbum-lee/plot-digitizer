"""Single-axis pixel<->real-value calibration, supporting linear and log scales."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class CalibrationError(ValueError):
    """Raised when an axis calibration is missing, degenerate, or inconsistent."""


class AxisScale(Enum):
    LINEAR = "linear"
    LOG = "log"


@dataclass
class AxisCalibration:
    """Maps pixel positions along one axis to real-world values, and back.

    Reference points are (pixel, value) pairs the user supplies by clicking a
    known tick and typing its value. Fitting happens in "scale space": on a
    LOG axis, pixel position is linear in log10(value), not in the value
    itself (equal pixel spacing corresponds to a fixed multiplicative step,
    e.g. one decade), so values are log10-transformed before the linear fit
    and the fit's output is un-transformed (10**x) on the way back out.
    """

    scale: AxisScale
    reference_points: list[tuple[float, float]] = field(default_factory=list)

    def add_reference(self, pixel: float, value: float) -> None:
        self.reference_points.append((pixel, value))

    def is_valid(self) -> bool:
        try:
            self._fit()
        except CalibrationError:
            return False
        return True

    def pixel_to_value(self, pixel: float) -> float:
        a, b = self._fit()
        scale_value = a * pixel + b
        return 10**scale_value if self.scale is AxisScale.LOG else scale_value

    def value_to_pixel(self, value: float) -> float:
        scale_value = self._to_scale_space(value)
        a, b = self._fit()
        if a == 0:
            raise CalibrationError("degenerate calibration: zero slope")
        return (scale_value - b) / a

    def _to_scale_space(self, value: float) -> float:
        if self.scale is AxisScale.LOG:
            if value <= 0:
                raise CalibrationError(f"log-scale axis requires positive values, got {value!r}")
            return math.log10(value)
        return value

    def _fit(self) -> tuple[float, float]:
        """Least-squares fit of scale_value = a * pixel + b. Returns (a, b)."""
        if len(self.reference_points) < 2:
            raise CalibrationError(
                f"axis calibration needs at least 2 reference points, got "
                f"{len(self.reference_points)}"
            )
        pixels = [pixel for pixel, _ in self.reference_points]
        scale_values = [self._to_scale_space(value) for _, value in self.reference_points]
        n = len(pixels)
        mean_p = sum(pixels) / n
        mean_v = sum(scale_values) / n
        denominator = sum((p - mean_p) ** 2 for p in pixels)
        if denominator == 0:
            raise CalibrationError("reference points must not share the same pixel position")
        numerator = sum(
            (p - mean_p) * (v - mean_v) for p, v in zip(pixels, scale_values, strict=True)
        )
        a = numerator / denominator
        b = mean_v - a * mean_p
        return a, b
