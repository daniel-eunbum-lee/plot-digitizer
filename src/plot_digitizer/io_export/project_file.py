"""Project save/load as JSON, so a digitizing session can be resumed later."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.imaging.perspective import PerspectiveTransform
from plot_digitizer.model.curve import Curve, CurveSource
from plot_digitizer.model.point import Point
from plot_digitizer.model.project import Project

_FORMAT_VERSION = 1


def _axis_to_dict(axis: AxisCalibration) -> dict[str, Any]:
    return {
        "scale": axis.scale.value,
        "reference_points": [list(pair) for pair in axis.reference_points],
    }


def _axis_from_dict(data: dict[str, Any]) -> AxisCalibration:
    axis = AxisCalibration(scale=AxisScale(data["scale"]))
    axis.reference_points = [(pair[0], pair[1]) for pair in data["reference_points"]]
    return axis


def _curve_to_dict(curve: Curve) -> dict[str, Any]:
    return {
        "name": curve.name,
        "color_hex": curve.color_hex,
        "source": curve.source,
        "points": [[point.x, point.y] for point in curve.points],
    }


def _curve_from_dict(data: dict[str, Any]) -> Curve:
    source: CurveSource = data["source"]
    return Curve(
        name=data["name"],
        color_hex=data["color_hex"],
        source=source,
        points=[Point(x=xy[0], y=xy[1]) for xy in data["points"]],
    )


def _perspective_to_dict(perspective: PerspectiveTransform | None) -> dict[str, Any] | None:
    if perspective is None:
        return None
    return {
        "src_points": [[point.x, point.y] for point in perspective.src_points],
        "output_size": list(perspective.output_size),
    }


def _perspective_from_dict(data: dict[str, Any] | None) -> PerspectiveTransform | None:
    if data is None:
        return None
    top_left, top_right, bottom_right, bottom_left = (
        Point(x=xy[0], y=xy[1]) for xy in data["src_points"]
    )
    width, height = data["output_size"]
    return PerspectiveTransform(
        src_points=(top_left, top_right, bottom_right, bottom_left),
        output_size=(width, height),
    )


def save_project(project: Project, path: Path) -> None:
    payload = {
        "format_version": _FORMAT_VERSION,
        "image_path": str(project.image_path),
        "x_axis": _axis_to_dict(project.x_axis),
        "y_axis": _axis_to_dict(project.y_axis),
        "curves": [_curve_to_dict(curve) for curve in project.curves],
        "active_curve_index": project.active_curve_index,
        "perspective": _perspective_to_dict(project.perspective),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_project(path: Path) -> Project:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Project(
        image_path=Path(payload["image_path"]),
        x_axis=_axis_from_dict(payload["x_axis"]),
        y_axis=_axis_from_dict(payload["y_axis"]),
        curves=[_curve_from_dict(data) for data in payload["curves"]],
        active_curve_index=payload["active_curve_index"],
        perspective=_perspective_from_dict(payload["perspective"]),
    )
