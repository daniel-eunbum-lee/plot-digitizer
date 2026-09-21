"""A named, ordered collection of digitized points."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.point import DataPoint, Point

CurveSource = Literal["manual", "auto"]


@dataclass
class Curve:
    name: str
    points: list[Point] = field(default_factory=list)
    color_hex: str = "#1f77b4"
    source: CurveSource = "manual"

    def add_point(self, point: Point) -> None:
        self.points.append(point)

    def remove_point(self, index: int) -> None:
        del self.points[index]

    def move_point(self, index: int, point: Point) -> None:
        self.points[index] = point

    def to_data_points(self, transform: CoordinateTransform) -> list[DataPoint]:
        return [transform.pixel_to_data(point) for point in self.points]
